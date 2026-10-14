import os
import requests
from datetime import datetime

# --- CONFIGURACIÓN DE CREDENCIALES ---
API_KEY = "0263d119deb33d2831893b185acf7b14"
TELEGRAM_TOKEN = "8860037934:AAGerJjRrT_AD2yWp918_y5xCI8SNj3YPm4"
CHAT_ID = "5811357869"

BANKROLL_TOTAL = 1000000  
STAKE_FIXO_PCT = 0.02     
MIN_EV = 0.03             # 3% mínimo de EV real

SPORTS_TO_SCAN = [
    {"nombre": "Fútbol - Premier League", "key": "soccer_epl"},
    {"nombre": "Fútbol - La Liga", "key": "soccer_spain_la_liga"},
    {"nombre": "Fútbol - Serie A", "key": "soccer_italy_serie_a"},
    {"nombre": "Fútbol - Champions League", "key": "soccer_uefa_champs_league"},
    {"nombre": "Fútbol - Europa League", "key": "soccer_uefa_europa_league"},
    {"nombre": "Fútbol - Copa Libertadores", "key": "soccer_conmebol_copa_libertadores"},
    {"nombre": "Fútbol - Copa Sudamericana", "key": "soccer_conmebol_copa_sudamericana"},
    {"nombre": "Fútbol - Liga Argentina", "key": "soccer_argentina_primera_division"},
    {"nombre": "Fútbol - Liga Colombiana", "key": "soccer_colombia_liga_dimayor"},
    {"nombre": "Baloncesto - NBA", "key": "basketball_nba"},
    {"nombre": "NFL", "key": "americanfootball_nfl"},
    {"nombre": "Esports - League of Legends", "key": "esports_lol"},
    {"nombre": "Esports - Valorant", "key": "esports_valorant"}
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

def formatear_fecha(fecha_str):
    try:
        dt = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y - %H:%M UTC")
    except:
        return fecha_str

def analizar_mercados():
    print("[*] Iniciando escaneo por Consenso de Mercado Real (+EV)...")
    monto_stake = BANKROLL_TOTAL * STAKE_FIXO_PCT
    
    # Conjunto para registrar partidos ya alertados en esta ejecución y evitar duplicados
    partidos_procesados = set()

    for deporte in SPORTS_TO_SCAN:
        nombre_deporte = deporte["nombre"]
        sport_key = deporte["key"]
        
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={API_KEY}&regions=eu&markets=h2h&oddsFormat=decimal"
        
        try:
            res = requests.get(url)
            if res.status_code != 200:
                continue
            
            partidos = res.json()
            for partido in partidos:
                match_id = partido.get('id')
                if not match_id or match_id in partidos_procesados:
                    continue

                home_team = partido['home_team']
                away_team = partido['away_team']
                fecha_juego = formatear_fecha(partido.get('commence_time', ''))
                bookmakers = partido.get('bookmakers', [])
                
                if not bookmakers:
                    continue

                # 1. Calcular la probabilidad justa de mercado (No-Vig Consensus)
                prob_acumulada = {}
                conteo_casas = 0

                for bookmaker in bookmakers:
                    for market in bookmaker.get('markets', []):
                        if market['key'] == 'h2h':
                            outcomes = market['outcomes']
                            suma_inversas = sum(1 / o['price'] for o in outcomes if o['price'] > 1)
                            if suma_inversas > 0:
                                for o in outcomes:
                                    nombre_sel = o['name']
                                    prob_novig = (1 / o['price']) / suma_inversas
                                    if nombre_sel not in prob_acumulada:
                                        prob_acumulada[nombre_sel] = 0.0
                                    prob_acumulada[nombre_sel] += prob_novig
                                conteo_casas += 1

                if conteo_casas == 0:
                    continue

                prob_consenso = {sel: prob / conteo_casas for sel, prob in prob_acumulada.items()}

                # 2. Encontrar la MEJOR cuota absoluta para cada selección del partido
                mejores_opciones = {}

                for bookmaker in bookmakers:
                    casa = bookmaker.get('title', 'Bookmaker')
                    for market in bookmaker.get('markets', []):
                        if market['key'] == 'h2h':
                            for outcome in market['outcomes']:
                                nombre_sel = outcome['name']
                                cuota_ofrecida = outcome['price']
                                
                                if nombre_sel in prob_consenso:
                                    p_real = prob_consenso[nombre_sel]
                                    ev = (p_real * cuota_ofrecida) - 1
                                    
                                    if ev >= MIN_EV:
                                        key_opcion = nombre_sel
                                        # Guardamos únicamente la cuota más alta encontrada en todo el mercado
                                        if key_opcion not in mejores_opciones or cuota_ofrecida > mejores_opciones[key_opcion]['cuota']:
                                            mejores_opciones[key_opcion] = {
                                                'seleccion': nombre_sel,
                                                'cuota': cuota_ofrecida,
                                                'casa': casa,
                                                'prob': p_real,
                                                'ev': ev
                                            }

                # 3. CONSOLIDAR Y ENVIAR UNA SOLA VEZ POR PARTIDO
                if mejores_opciones:
                    partidos_procesados.add(match_id)
                    
                    lineas_mensaje = []
                    for item in mejores_opciones.values():
                        linea = (
                            f"📌 *Selección:* {item['seleccion']}\n"
                            f"📊 *Mejor Cuota:* {item['cuota']} ({item['casa']})\n"
                            f"📈 *Prob. Real (Mercado):* {item['prob']*100:.1f}%\n"
                            f"💡 *EV Real:* +{item['ev']*100:.2f}%\n"
                        )
                        lineas_mensaje.append(linea)
                    
                    mensaje_consolidado = (
                        f"🚨 *¡OPORTUNIDAD +EV REAL DETECTADA!* 🚨\n\n"
                        f"🏆 *Liga:* {nombre_deporte}\n"
                        f"⚔️ *Encuentro:* {home_team} vs {away_team}\n"
                        f"📅 *Fecha:* {fecha_juego}\n"
                        f"💰 *Stake Sugerido:* ${monto_stake:,.0f}\n\n"
                        + "-----------------------------------\n" +
                        "\n-----------------------------------\n".join(lineas_mensaje)
                    )
                    
                    enviar_alerta_telegram(mensaje_consolidado)

        except Exception as e:
            print(f"[-] Error procesando {nombre_deporte}: {e}")

if __name__ == "__main__":
    analizar_mercados()
