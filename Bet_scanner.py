import os
import requests
import csv
from datetime import datetime, timedelta
import hashlib

# --- CONFIGURACIÓN DE CREDENCIALES Y PARÁMETROS ---
API_KEY = "0263d119deb33d2831893b185acf7b14"
TELEGRAM_TOKEN = "8860037934:AAGerJjRrT_AD2yWp918_y5xC-I8SNj3YPm4"
CHAT_ID = "5811357869"

# --- PRUEBA DE FUEGO PARA LOS LOGS ---
print("--- EL BOT ACABA DE ARRANCAR CORRECTAMENTE ---")
print(f"API Key configurada: SÍ (Largo: {len(API_KEY)})")
print(f"Token Telegram configurado: SÍ")
print(f"Chat ID configurado: SÍ")

BANKROLL_TOTAL = 1000000  
MIN_EV = 0.025            # Ajustado al 2.5% para mayor dinamismo
MIN_PROB_REAL = 0.35      
MAX_DIAS_FUTURO = 2       
MAX_ODDS_AGE_SECONDS = 300  
MIN_BOOKMAKERS_FOR_CONSENSUS = 3 
CSV_FILE = "historial_apuestas.csv"

# Ligas ampliadas con mayor volumen de partidos y mercados múltiples
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
    # Nuevas ligas agregadas para más volumen:
    {"nombre": "Fútbol - Liga MX (México)", "key": "soccer_mexico_ligamx"},
    {"nombre": "Fútbol - Brasileirão (Brasil)", "key": "soccer_brazil_campeonato"},
    {"nombre": "Fútbol - Eredivisie (Países Bajos)", "key": "soccer_netherlands_eredivisie"},
    {"nombre": "Fútbol - Primeira Liga (Portugal)", "key": "soccer_portugal_primeira_liga"},
    {"nombre": "Fútbol - Süper Lig (Turquía)", "key": "soccer_turkey_super_league"},
    {"nombre": "Baloncesto - NBA", "key": "basketball_nba"},
    {"nombre": "NFL", "key": "americanfootball_nfl"},
    {"nombre": "Esports - League of Legends", "key": "esports_lol"},
    {"nombre": "Esports - Valorant", "key": "esports_valorant"}
]

def enviar_alerta_telegram(mensaje):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error enviando mensaje a Telegram: {e}")
        return False

def obtener_claves_registradas():
    claves = set()
    if os.path.isfile(CSV_FILE):
        try:
            with open(CSV_FILE, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if row and len(row) >= 12:
                        claves.add(row[11])
        except Exception as e:
            print(f"Error leyendo CSV de claves: {e}")
    return claves

def registrar_en_csv(data_apuesta):
    file_exists = os.path.isfile(CSV_FILE)
    try:
        with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "Fecha_Alerta", "Expira", "Deporte", "Encuentro", "Mercado", 
                    "Seleccion", "Cuota", "Casa", "Prob_Estimada", "EV", 
                    "Stake_Sugerido", "Signal_Key"
                ])
            writer.writerow(data_apuesta)
    except Exception as e:
        print(f"Error escribiendo en CSV: {e}")

def calcular_stake_kelly(prob, cuota, bankroll):
    if prob <= 0 or cuota <= 1:
        return 0.0
    
    b = cuota - 1
    q = 1 - prob
    kelly_raw = ((b * prob) - q) / b
    
    if kelly_raw <= 0:
        return 0.0
        
    kelly_seguro = kelly_raw * 0.10
    stake_pct = min(kelly_seguro, 0.005)
    return bankroll * stake_pct

def analizar_mercados():
    print("[*] Iniciando escaneo ampliado con EV al 2.5% y nuevas ligas...")
    ahora_utc = datetime.utcnow()
    limite_fecha = ahora_utc + timedelta(days=MAX_DIAS_FUTURO)
    
    claves_enviadas = obtener_claves_registradas()
    mercados_api = "h2h,spreads,totals"

    for deporte in SPORTS_TO_SCAN:
        nombre_deporte = deporte["nombre"]
        sport_key = deporte["key"]
        
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={API_KEY}&regions=eu&markets={mercados_api}&oddsFormat=decimal"
        
        try:
            res = requests.get(url, timeout=15)
            if res.status_code != 200:
                continue
            
            partidos = res.json()
            for partido in partidos:
                match_id = partido.get('id')
                if not match_id:
                    continue

                commence_time_str = partido.get('commence_time', '')
                try:
                    dt_obj = datetime.fromisoformat(commence_time_str.replace("Z", "+00:00")).replace(tzinfo=None)
                except:
                    continue
                
                if dt_obj > limite_fecha or dt_obj < ahora_utc:
                    continue

                home_team = partido['home_team']
                away_team = partido['away_team']
                bookmakers = partido.get('bookmakers', [])
                
                if len(bookmakers) < MIN_BOOKMAKERS_FOR_CONSENSUS:
                    continue

                mercados_agrupados = {}

                for bookmaker in bookmakers:
                    book_key = bookmaker.get('key')
                    for market in bookmaker.get('markets', []):
                        m_key = market.get('key')
                        outcomes = market.get('outcomes', [])
                        
                        for o in outcomes:
                            price = o.get('price', 0)
                            if price <= 1.0:
                                continue
                                
                            sub_id = m_key
                            if 'point' in o:
                                sub_id = f"{m_key}_{o['point']}"
                            
                            if sub_id not in mercados_agrupados:
                                mercados_agrupados[sub_id] = {}
                            if book_key not in mercados_agrupados[sub_id]:
                                mercados_agrupados[sub_id][book_key] = []
                                
                            mercados_agrupados[sub_id][book_key].append({
                                'name': o.get('name'),
                                'price': price,
                                'point': o.get('point')
                            })

                mejores_opciones = {}

                for sub_id, books_dict in mercados_agrupados.items():
                    valid_books = {b_key: outcomes for b_key, outcomes in books_dict.items() if len(outcomes) >= 2}
                    if len(valid_books) < MIN_BOOKMAKERS_FOR_CONSENSUS:
                        continue

                    for eval_book_key, eval_outcomes in valid_books.items():
                        prob_acumulada = {}
                        conteo_casas = 0

                        for b_key, outcomes in valid_books.items():
                            if b_key == eval_book_key:
                                continue
                            
                            suma_inversas = sum(1.0 / o['price'] for o in outcomes)
                            if suma_inversas <= 0:
                                continue
                                
                            for o in outcomes:
                                sel_key = f"{o['name']}_{o.get('point', '')}"
                                prob_novig = (1.0 / o['price']) / suma_inversas
                                if sel_key not in prob_acumulada:
                                    prob_acumulada[sel_key] = 0.0
                                prob_acumulada[sel_key] += prob_novig
                            conteo_casas += 1

                        if conteo_casas == 0:
                            continue

                        consenso_prob = {sel: prob / conteo_casas for sel, prob in prob_acumulada.items()}

                        for o in eval_outcomes:
                            sel_key = f"{o['name']}_{o.get('point', '')}"
                            cuota_ofrecida = o['price']
                            
                            if sel_key in consenso_prob:
                                p_estimada = consenso_prob[sel_key]
                                ev = (p_estimada * cuota_ofrecida) - 1.0

                                if ev >= MIN_EV and p_estimada >= MIN_PROB_REAL:
                                    raw_signal_string = f"{match_id}|{sub_id}|{sel_key}|{eval_book_key}|{cuota_ofrecida:.3f}"
                                    signal_key = hashlib.sha256(raw_signal_string.encode()).hexdigest()

                                    if signal_key in claves_enviadas:
                                        continue

                                    stake = calcular_stake_kelly(p_estimada, cuota_ofrecida, BANKROLL_TOTAL)
                                    
                                    if stake > 0:
                                        nombre_mercado = "Ganador (1X2 / H2H)"
                                        if "spreads" in sub_id:
                                            nombre_mercado = f"Hándicap (Spread {o.get('point', '')})"
                                        elif "totals" in sub_id:
                                            nombre_mercado = f"Totales (Over/Under {o.get('point', '')})"

                                        key_opcion = f"{sub_id}_{sel_key}"
                                        if key_opcion not in mejores_opciones or cuota_ofrecida > mejores_opciones[key_opcion]['cuota']:
                                            mejores_opciones[key_opcion] = {
                                                'mercado': nombre_mercado,
                                                'seleccion': o['name'],
                                                'cuota': cuota_ofrecida,
                                                'casa': eval_book_key,
                                                'prob_estimada': p_estimada,
                                                'ev': ev,
                                                'stake': stake,
                                                'signal_key': signal_key,
                                                'captura': ahora_utc,
                                                'expiracion': ahora_utc + timedelta(seconds=MAX_ODDS_AGE_SECONDS)
                                            }

                if mejores_opciones:
                    lineas_mensaje = []
                    
                    for item in mejores_opciones.values():
                        linea = (
                            f"🎯 <b>Mercado:</b> {item['mercado']}\n"
                            f"📌 <b>Selección:</b> {item['seleccion']}\n"
                            f"📊 <b>Cuota:</b> {item['cuota']} ({item['casa']})\n"
                            f"📈 <b>Prob. Estimada:</b> {item['prob_estimada']*100:.1f}%\n"
                            f"💡 <b>EV Real:</b> +{item['ev']*100:.2f}%\n"
                            f"💰 <b>Stake (Kelly):</b> ${item['stake']:,.0f}\n"
                            f"⏳ <b>Válida hasta:</b> {item['expiracion'].strftime('%H:%M:%S')} UTC\n"
                        )
                        lineas_mensaje.append(linea)
                        
                        registrar_en_csv([
                            item['captura'].strftime("%Y-%m-%d %H:%M:%S"),
                            item['expiracion'].strftime("%Y-%m-%d %H:%M:%S"),
                            nombre_deporte,
                            f"{home_team} vs {away_team}",
                            item['mercado'],
                            item['seleccion'],
                            item['cuota'],
                            item['casa'],
                            f"{item['prob_estimada']*100:.1f}%",
                            f"+{item['ev']*100:.2f}%",
                            f"${item['stake']:,.0f}",
                            item['signal_key']
                        ])
                        
                        claves_enviadas.add(item['signal_key'])
                    
                    mensaje_consolidado = (
                        f"🚨 <b>¡OPORTUNIDAD +EV RIGUROSA DETECTADA!</b> 🚨\n\n"
                        f"🛡️ <i>Modo: SIMULACIÓN (PAPER TRADING)</i>\n"
                        f"🏆 <b>Liga:</b> {nombre_deporte}\n"
                        f"⚔️ <b>Encuentro:</b> {home_team} vs {away_team}\n"
                        f"📅 <b>Fecha del Juego:</b> {dt_obj.strftime('%d/%m/%Y - %H:%M UTC')}\n\n"
                        + "-----------------------------------\n" +
                        "\n-----------------------------------\n".join(lineas_mensaje)
                    )
                    
                    enviar_alerta_telegram(mensaje_consolidado)

        except Exception as e:
            print(f"[-] Error procesando {nombre_deporte}: {e}")

if __name__ == "__main__":
    analizar_mercados()
