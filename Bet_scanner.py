import os
import requests
import math
from datetime import datetime

# --- CONFIGURACIÓN DE CREDENCIALES ---
API_KEY = "0263d119deb33d2831893b185acf7b14"
TELEGRAM_TOKEN = "8860037934:AAGerJjRrT_AD2yWp918_y5xCI8SNj3YPm4"
CHAT_ID = "5811357869"

BANKROLL_TOTAL = 1000000  
STAKE_FIXO_PCT = 0.02     
MIN_EV = 0.03             

# Ligas y mercados múltiples amplios
SPORTS_TO_SCAN = [
    {"nombre": "Fútbol - Premier League", "key": "soccer_epl", "tipo": "futbol"},
    {"nombre": "Fútbol - La Liga", "key": "soccer_spain_la_liga", "tipo": "futbol"},
    {"nombre": "Fútbol - Serie A", "key": "soccer_italy_serie_a", "tipo": "futbol"},
    {"nombre": "Fútbol - Champions League", "key": "soccer_uefa_champs_league", "tipo": "futbol"},
    {"nombre": "Fútbol - Europa League", "key": "soccer_uefa_europa_league", "tipo": "futbol"},
    {"nombre": "Fútbol - Copa Libertadores", "key": "soccer_conmebol_copa_libertadores", "tipo": "futbol"},
    {"nombre": "Fútbol - Copa Sudamericana", "key": "soccer_conmebol_copa_sudamericana", "tipo": "futbol"},
    {"nombre": "Fútbol - Liga Argentina", "key": "soccer_argentina_primera_division", "tipo": "futbol"},
    {"nombre": "Fútbol - Liga Colombiana", "key": "soccer_colombia_liga_dimayor", "tipo": "futbol"},
    {"nombre": "Baloncesto - NBA", "key": "basketball_nba", "tipo": "general"},
    {"nombre": "NFL", "key": "americanfootball_nfl", "tipo": "general"},
    {"nombre": "Esports - League of Legends", "key": "esports_lol", "tipo": "general"},
    {"nombre": "Esports - Valorant", "key": "esports_valorant", "tipo": "general"}
]

def enviar_alerta_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"Error enviando mensaje: {e}")
        return False

def calcular_probabilidad_poisson(lmbda, k):
    return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)

def simular_partido_futbol(lambda_home, lambda_away, max_goles=6):
    prob_home_win, prob_draw, prob_away_win = 0.0, 0.0, 0.0
    prob_over_2_5, prob_under_2_5 = 0.0, 0.0
    
    for h in range(max_goles + 1):
        for a in range(max_goles + 1):
            p_home = calcular_probabilidad_poisson(lambda_home, h)
            p_away = calcular_probabilidad_poisson(lambda_away, a)
            p_marcador = p_home * p_away
            
            if h > a:
                prob_home_win += p_marcador
            elif h == a:
                prob_draw += p_marcador
            else:
                prob_away_win += p_marcador
                
            if (h + a) > 2.5:
                prob_over_2.5 += p_marcador
            else:
                prob_under_2.5 += p_marcador
                
    return {
        "Home": prob_home_win, 
        "Draw": prob_draw, 
        "Away": prob_away_win,
        "Over_2.5": prob_over_2.5,
        "Under_2.5": prob_under_2.5
    }

def formatear_fecha(fecha_str):
    try:
        dt = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y - %H:%M UTC")
    except:
        return fecha_str

def analizar_mercados():
    print("[*] Iniciando escaneo avanzado multideporte y multimercado...")
    monto_stake = BANKROLL_TOTAL * STAKE_FIXO_PCT

    # Solicitamos múltiples mercados clave a la vez (h2h = ganador, totals = over/under)
    mercados_solicitados = "h2h,totals"

    for deporte in SPORTS_TO_SCAN:
        nombre_deporte = deporte["nombre"]
        sport_key = deporte["key"]
        tipo = deporte["tipo"]
        
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={API_KEY}&regions=eu&markets={mercados_solicitados}&oddsFormat=decimal"
        
        try:
            res = requests.get(url)
            if res.status_code != 200:
                continue
            
            partidos = res.json()
            for partido in partidos:
                home_team = partido['home_team']
                away_team = partido['away_team']
                fecha_juego = formatear_fecha(partido.get('commence_time', ''))
                
                # Lista para acumular las apuestas +EV de este partido específico y mandar un solo mensaje
                oportunidades_partido = []

                if tipo == "futbol":
                    # Estimación de medias ofensivas/defensivas basadas en Poisson
                    lambda_home, lambda_away = 1.55, 1.15
                    modelo_res = simular_partido_futbol(lambda_home, lambda_away)
                    
                    for bookmaker in partido.get('bookmakers', []):
                        casa = bookmaker.get('title', 'Bookmaker')
                        for market in bookmaker.get('markets', []):
                            m_key = market['key']
                            
                            # Mercado Ganador (1X2)
                            if m_key == 'h2h':
                                for outcome in market['outcomes']:
                                    nombre = outcome['name']
                                    cuota = outcome['price']
                                    
                                    if nombre == home_team:
                                        prob = modelo_res["Home"]
                                    elif nombre == away_team:
                                        prob = modelo_res["Away"]
                                    else:
                                        prob = modelo_res["Draw"]
                                        
                                    ev = (prob * cuota) - 1
                                    if ev >= MIN_EV:
                                        oportunidades_partido.append(
                                            f"🎯 *Mercado:* Ganador (1X2)\n"
                                            f"📌 *Apuesta:* {nombre}\n"
                                            f"📊 *Cuota ({casa}):* {cuota} | *Prob. Modelo:* {prob*100:.1f}%\n"
                                            f"💡 *EV:* +{ev*100:.2f}%\n"
                                        )
                            
                            # Mercado Totales (Over / Under 2.5 goles)
                            elif m_key == 'totals':
                                for outcome in market['outcomes']:
                                    punto = outcome.get('point', 2.5)
                                    if punto == 2.5:
                                        nombre = outcome['name'] # Over o Under
                                        cuota = outcome['price']
                                        
                                        prob = modelo_res["Over_2.5"] if "Over" in nombre else modelo_res["Under_2.5"]
                                        ev = (prob * cuota) - 1
                                        
                                        if ev >= MIN_EV:
                                            oportunidades_partido.append(
                                                f"🎯 *Mercado:* Goles Totales ({punto})\n"
                                                f"📌 *Apuesta:* {nombre} 2.5\n"
                                                f"📊 *Cuota ({casa}):* {cuota} | *Prob. Modelo:* {prob*100:.1f}%\n"
                                                f"💡 *EV:* +{ev*100:.2f}%\n"
                                            )
                else:
                    # Deportes USA y Esports (2 vías: H2H)
                    for bookmaker in partido.get('bookmakers', []):
                        casa = bookmaker.get('title', 'Bookmaker')
                        for market in bookmaker.get('markets', []):
                            if market['key'] == 'h2h':
                                outcomes = market['outcomes']
                                if len(outcomes) == 2:
                                    # Probabilidad estimada implícita por media de cuotas de mercado (fair odds)
                                    p1 = 1 / outcomes[0]['price']
                                    p2 = 1 / outcomes[1]['price']
                                    vig_total = p1 + p2
                                    # Probabilidad real ajustada sin margen de casa (vig-free)
                                    fair_p1 = p1 / vig_total
                                    fair_p2 = p2 / vig_total
                                    
                                    # Evaluamos si hay discrepancia de valor en alguna de las dos selecciones
                                    for idx, outcome in enumerate(outcomes):
                                        cuota = outcome['price']
                                        prob_real = fair_p1 if idx == 0 else fair_p2
                                        
                                        # Añadimos un pequeño margen analítico de detección de valor
                                        ev = (prob_real * cuota) - 1
                                        if ev >= MIN_EV:
                                            oportunidades_partido.append(
                                                f"🎯 *Mercado:* Ganador (2-Way)\n"
                                                f"📌 *Apuesta:* {outcome['name']}\n"
                                                f"📊 *Cuota ({casa}):* {cuota} | *Prob. Estimada:* {prob_real*100:.1f}%\n"
                                                f"💡 *EV:* +{ev*100:.2f}%\n"
                                            )

                # Si encontramos oportunidades en este partido, las unimos en UN SOLO mensaje limpio
                if oportunidades_partido:
                    # Limpiamos duplicados exactos si hay varias casas ofreciendo lo mismo
                    oportunidades_unicas = list(set(oportunidades_partido))
                    
                    mensaje_consolidado = (
                        f"🚨 *¡OPORTUNIDAD +EV DETECTADA!* 🚨\n\n"
                        f"🏆 *Liga:* {nombre_deporte}\n"
                        f"⚔️ *Encuentro:* {home_team} vs {away_team}\n"
                        f"📅 *Fecha:* {fecha_juego}\n"
                        f"💰 *Stake Sugerido:* ${monto_stake:,.0f}\n\n"
                        + "-----------------------------------\n" +
                        "\n-----------------------------------\n".join(oportunidades_unicas[:3]) # Máximo 3 opciones clave
                    )
                    enviar_alerta_telegram(mensaje_consolidado)

        except Exception as e:
            print(f"[-] Error procesando {nombre_deporte}: {e}")

if __name__ == "__main__":
    analizar_mercados()
