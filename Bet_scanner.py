import os
import requests
import csv
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE CREDENCIALES ---
API_KEY = "0263d119deb33d2831893b185acf7b14"
TELEGRAM_TOKEN = "8860037934:AAGerJjRrT_AD2yWp918_y5xCI8SNj3YPm4"
CHAT_ID = "5811357869"

BANKROLL_TOTAL = 1000000  
MIN_EV = 0.03             
MIN_PROB_REAL = 0.35      
MAX_DIAS_FUTURO = 2       
CSV_FILE = "historial_apuestas.csv"

# Ligas ampliadas con mercados múltiples (Ganador, Spreads/Hándicaps y Totales Over/Under)
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

def registrar_en_csv(data_apuesta):
    file_exists = os.path.isfile(CSV_FILE)
    try:
        with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Fecha_Alerta", "Deporte", "Encuentro", "Mercado", "Seleccion", "Cuota", "Casa", "Prob_Real", "EV", "Stake_Sugerido"])
            writer.writerow(data_apuesta)
    except Exception as e:
        print(f"Error escribiendo en CSV: {e}")

def formatear_fecha(fecha_str):
    try:
        dt = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y - %H:%M UTC"), dt
    except:
        return fecha_str, None

def calcular_stake_kelly(prob, cuota, bankroll):
    b = cuota - 1
    if b <= 0:
        return bankroll * 0.01
    kelly_fraction = (b * prob - (1 - prob)) / b
    kelly_seguro = kelly_fraction * 0.25  # Kelly fraccional al 25%
    stake_pct = max(0.01, min(kelly_seguro, 0.05))
    return bankroll * stake_pct

def analizar_mercados():
    print("[*] Iniciando escaneo masivo multimercado (+EV)...")
    partidos_procesados = set()
    ahora = datetime.utcnow()
    limite_fecha = ahora + timedelta(days=MAX_DIAS_FUTURO)

    # Solicitamos múltiples mercados clave de golpe: h2h (ganador), spreads (hándicaps), totals (altas/bajas)
    mercados_api = "h2h,spreads,totals"

    for deporte in SPORTS_TO_SCAN:
        nombre_deporte = deporte["nombre"]
        sport_key = deporte["key"]
        
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={API_KEY}&regions=eu&markets={mercados_api}&oddsFormat=decimal"
        
        try:
            res = requests.get(url)
            if res.status_code != 200:
                continue
            
            partidos = res.json()
            for partido in partidos:
                match_id = partido.get('id')
                if not match_id or match_id in partidos_procesados:
                    continue

                commence_time_str = partido.get('commence_time', '')
                fecha_formateada, dt_obj = formatear_fecha(commence_time_str)
                
                if dt_obj:
                    dt_naive = dt_obj.replace(tzinfo=None)
                    if dt_naive > limite_fecha or dt_naive < ahora:
                        continue

                home_team = partido['home_team']
                away_team = partido['away_team']
                bookmakers = partido.get('bookmakers', [])
                
                if not bookmakers:
                    continue

                # Agruparemos los mercados por su tipo y línea específica (ej: h2h, totals_2.5, spreads_-1.5)
                # Para calcular el consenso No-Vig de cada mercado individualmente.
                mercados_datos = {}

                for bookmaker in bookmakers:
                    for market in bookmaker.get('markets', []):
                        m_key = market['key']
                        outcomes = market.get('outcomes', [])
                        
                        for o in outcomes:
                            # Identificador único para cada sub-mercado (ej: total de 2.5 goles o hándicap de -3.5 puntos)
                            sub_id = m_key
                            if 'point' in o:
                                sub_id = f"{m_key}_{o['point']}"
                            
                            if sub_id not in mercados_datos:
                                mercados_datos[sub_id] = {'outcomes_keys': [x['name'] for x in outcomes], 'casas': []}
                    
                # Recopilar cuotas por sub-mercado de todas las casas
                consenso_mercados = {}

                for sub_id in mercados_datos:
                    # Calcular probabilidades No-Vig por cada casa y promediarlas
                    prob_acumulada = {}
                    conteo_casas = 0

                    for bookmaker in bookmakers:
                        for market in bookmaker.get('markets', []):
                            m_key = market['key']
                            outcomes = market.get('outcomes', [])
                            
                            # Validar que coincida el sub_id
                            has_matching_point = any('point' in x and f"{m_key}_{x['point']}" == sub_id for x in outcomes)
                            if m_key == sub_id or has_matching_point:
                                suma_inversas = sum(1 / o['price'] for o in outcomes if o['price'] > 1)
                                if suma_inversas > 0:
                                    for o in outcomes:
                                        # Identificador único de selección incluyendo línea (puntos/hándicap)
                                        sel_key = f"{o['name']}_{o.get('point', '')}"
                                        prob_novig = (1 / o['price']) / suma_inversas
                                        if sel_key not in prob_acumulada:
                                            prob_acumulada[sel_key] = 0.0
                                        prob_acumulada[sel_key] += prob_novig
                                    conteo_casas += 1

                    if conteo_casas > 0:
                        consenso_mercados[sub_id] = {sel: prob / conteo_casas for sel, prob in prob_acumulada.items()}

                # Evaluar valor (EV) en todos los mercados y casas
                mejores_opciones = {}

                for bookmaker in bookmakers:
                    casa = bookmaker.get('title', 'Bookmaker')
                    for market in bookmaker.get('markets', []):
                        m_key = market['key']
                        for o in market.get('outcomes', []):
                            sub_id = m_key
                            if 'point' in o:
                                sub_id = f"{m_key}_{o['point']}"
                            
                            sel_key = f"{o['name']}_{o.get('point', '')}"
                            cuota_ofrecida = o['price']

                            if sub_id in consenso_mercados and sel_key in consenso_mercados[sub_id]:
                                p_real = consenso_mercados[sub_id][sel_key]
                                ev = (p_real * cuota_ofrecida) - 1

                                # Filtros estrictos de calidad +EV y probabilidad real mínima
                                if ev >= MIN_EV and p_real >= MIN_PROB_REAL:
                                    key_opcion = sel_key
                                    if key_opcion not in mejores_opciones or cuota_ofrecida > mejores_opciones[key_opcion]['cuota']:
                                        monto_stake = calcular_stake_kelly(p_real, cuota_ofrecida, BANKROLL_TOTAL)
                                        
                                        # Nombre limpio del mercado para la alerta
                                        nombre_mercado_limpio = "Ganador (1X2 / H2H)"
                                        if "spreads" in sub_id:
                                            nombre_mercado_limpio = f"Hándicap (Spreads {o.get('point', '')})"
                                        elif "totals" in sub_id:
                                            nombre_mercado_limpio = f"Totales (Over/Under {o.get('point', '')})"

                                        mejores_opciones[key_opcion] = {
                                            'mercado': nombre_mercado_limpio,
                                            'seleccion': o['name'],
                                            'cuota': cuota_ofrecida,
                                            'casa': casa,
                                            'prob': p_real,
                                            'ev': ev,
                                            'stake': monto_stake
                                        }

                # Consolidar y enviar una única alerta por partido si hay valor en cualquier mercado
                if mejores_opciones:
                    partidos_procesados.add(match_id)
                    lineas_mensaje = []
                    
                    for item in mejores_opciones.values():
                        linea = (
                            f"🎯 *Mercado:* {item['mercado']}\n"
                            f"📌 *Apuesta:* {item['seleccion']}\n"
                            f"📊 *Mejor Cuota:* {item['cuota']} ({item['casa']})\n"
                            f"📈 *Prob. Real:* {item['prob']*100:.1f}%\n"
                            f"💡 *EV Real:* +{item['ev']*100:.2f}%\n"
                            f"💰 *Stake (Kelly):* ${item['stake']:,.0f}\n"
                        )
                        lineas_mensaje.append(linea)
                        
                        # Registrar en CSV histórico
                        registrar_en_csv([
                            datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                            nombre_deporte,
                            f"{home_team} vs {away_team}",
                            item['mercado'],
                            item['seleccion'],
                            item['cuota'],
                            item['casa'],
                            f"{item['prob']*100:.1f}%",
                            f"+{item['ev']*100:.2f}%",
                            f"${item['stake']:,.0f}"
                        ])
                    
                    mensaje_consolidado = (
                        f"🚨 *¡OPORTUNIDAD +EV MULTIMERCADO!* 🚨\n\n"
                        f"🏆 *Liga:* {nombre_deporte}\n"
                        f"⚔️ *Encuentro:* {home_team} vs {away_team}\n"
                        f"📅 *Fecha:* {fecha_formateada}\n\n"
                        + "-----------------------------------\n" +
                        "\n-----------------------------------\n".join(lineas_mensaje)
                    )
                    
                    enviar_alerta_telegram(mensaje_consolidado)

        except Exception as e:
            print(f"[-] Error procesando {nombre_deporte}: {e}")

if __name__ == "__main__":
    analizar_mercados()
