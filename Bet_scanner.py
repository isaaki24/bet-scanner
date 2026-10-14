import os
import requests
import math

# --- CONFIGURACIÓN DE CREDENCIALES ---
API_KEY = "0263d119deb33d2831893b185acf7b14"
TELEGRAM_TOKEN = "8860037934:AAGerJjRrT_AD2yWp918_y5xCI8SNj3YPm4"
CHAT_ID = "5811357869"

BANKROLL_TOTAL = 1000000  
STAKE_FIXO_PCT = 0.02     
MIN_EV = 0.03             

# Lista completa de deportes y ligas a escanear en cada ejecución
SPORTS_TO_SCAN = [
    # Top Ligas Europeas
    {"nombre": "Fútbol - Premier League", "key": "soccer_epl", "tipo": "futbol"},
    {"nombre": "Fútbol - La Liga", "key": "soccer_spain_la_liga", "tipo": "futbol"},
    {"nombre": "Fútbol - Serie A", "key": "soccer_italy_serie_a", "tipo": "futbol"},
    
    # Torneos Internacionales Europeos
    {"nombre": "Fútbol - Champions League", "key": "soccer_uefa_champs_league", "tipo": "futbol"},
    {"nombre": "Fútbol - Europa League", "key": "soccer_uefa_europa_league", "tipo": "futbol"},
    
    # Torneos Internacionales Sudamericanos
    {"nombre": "Fútbol - Copa Libertadores", "key": "soccer_conmebol_copa_libertadores", "tipo": "futbol"},
    {"nombre": "Fútbol - Copa Sudamericana", "key": "soccer_conmebol_copa_sudamericana", "tipo": "futbol"},
    
    # Ligas Locales Sudamericanas
    {"nombre": "Fútbol - Liga Argentina", "key": "soccer_argentina_primera_division", "tipo": "futbol"},
    {"nombre": "Fútbol - Liga Colombiana", "key": "soccer_colombia_liga_dimayor", "tipo": "futbol"},
    
    # Deportes Estadounidenses
    {"nombre": "Baloncesto - NBA", "key": "basketball_nba", "tipo": "general"},
    {"nombre": "NFL", "key": "americanfootball_nfl", "tipo": "general"}
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

def simular_partido_futbol(lambda_home, lambda_away, max_goles=10):
    prob_home_win, prob_draw, prob_away_win = 0.0, 0.0, 0.0
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
    return {"Home": prob_home_win, "Draw": prob_draw, "Away": prob_away_win}

def analizar_mercados():
    print("[*] Iniciando escaneo multideporte y multiliga...")
    monto_stake = BANKROLL_TOTAL * STAKE_FIXO_PCT

    for deporte in SPORTS_TO_SCAN:
        nombre_deporte = deporte["nombre"]
        sport_key = deporte["key"]
        tipo = deporte["tipo"]
        
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={API_KEY}&regions=eu&markets=h2h&oddsFormat=decimal"
        
        try:
            res = requests.get(url)
            if res.status_code != 200:
                print(f"[-] No hay eventos disponibles o no se pudo consultar {nombre_deporte}: Código {res.status_code}")
                continue
            
            partidos = res.json()
            print(f"[*] Analizando {len(partidos)} eventos en {nombre_deporte}...")

            for partido in partidos:
                home_team = partido['home_team']
                away_team = partido['away_team']
                
                if tipo == "futbol":
                    lambda_home, lambda_away = 1.65, 1.10
                    prob_dict = simular_partido_futbol(lambda_home, lambda_away)
                    
                    for bookmaker in partido.get('bookmakers', []):
                        for market in bookmaker.get('markets', []):
                            if market['key'] == 'h2h':
                                for outcome in market['outcomes']:
                                    nombre_cuota = outcome['name']
                                    cuota_ofrecida = outcome['price']
                                    
                                    if nombre_cuota == home_team:
                                        prob_modelo = prob_dict["Home"]
                                    elif nombre_cuota == away_team:
                                        prob_modelo = prob_dict["Away"]
                                    else:
                                        prob_modelo = prob_dict["Draw"]
                                    
                                    ev = (prob_modelo * cuota_ofrecida) - 1
                                    if ev >= MIN_EV:
                                        enviar_alerta_telegram(
                                            f"🚨 *¡+EV DETECTADO!* 🚨\n\n"
                                            f"🏆 {nombre_deporte}\n"
                                            f"⚔️ {home_team} vs {away_team}\n"
                                            f"🎯 Selección: {nombre_cuota}\n"
                                            f"📊 Cuota: {cuota_ofrecida}\n"
                                            f"💡 EV: {ev*100:.2f}%\n"
                                            f"💰 Stake: ${monto_stake:,.0f}"
                                        )
                else:
                    for bookmaker in partido.get('bookmakers', []):
                        for market in bookmaker.get('markets', []):
                            if market['key'] == 'h2h':
                                outcomes = market['outcomes']
                                if len(outcomes) == 2:
                                    for outcome in outcomes:
                                        cuota_ofrecida = outcome['price']
                                        prob_modelo = 0.52
                                        ev = (prob_modelo * cuota_ofrecida) - 1
                                        
                                        if ev >= MIN_EV:
                                            enviar_alerta_telegram(
                                                f"🚨 *¡+EV DETECTADO!* 🚨\n\n"
                                                f"🏆 {nombre_deporte}\n"
                                                f"⚔️ {home_team} vs {away_team}\n"
                                                f"🎯 Selección: {outcome['name']}\n"
                                                f"📊 Cuota: {cuota_ofrecida}\n"
                                                f"💡 EV: {ev*100:.2f}%\n"
                                                f"💰 Stake: ${monto_stake:,.0f}"
                                            )
        except Exception as e:
            print(f"[-] Error procesando {nombre_deporte}: {e}")

if __name__ == "__main__":
    analizar_mercados()
