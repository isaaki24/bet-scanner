import os
import requests
import math

# Credenciales leídas desde las variables secretas de GitHub
API_KEY = os.environ.get("0263d119deb33d2831893b185acf7b14")
TELEGRAM_TOKEN = os.environ.get("8860037934: AAGerJjRrT_AD2yWp918_y5×CI8SNj3YPm4")
CHAT_ID = os.environ.get("5811357869")
BANKROLL_TOTAL = 1000000  
STAKE_FIXO_PCT = 0.02     
MIN_EV = 0.03             
SPORTS_KEY = "soccer_epl" 

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
    prob_home_win = 0.0
    prob_draw = 0.0
    prob_away_win = 0.0
    
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

def analizar_mercado_futbol():
    print("[*] Consultando cuotas y aplicando modelo de Poisson...")
    monto_stake = BANKROLL_TOTAL * STAKE_FIXO_PCT
    url = f"https://api.the-odds-api.com/v4/sports/{SPORTS_KEY}/odds/?apiKey={API_KEY}&regions=eu&markets=h2h&oddsFormat=decimal"
    
    try:
        res = requests.get(url)
        if res.status_code != 200:
            print(f"[-] Error en la API: {res.status_code}")
            return
        
        partidos = res.json()
        print(f"[*] Analizando {len(partidos)} partidos...")

        for partido in partidos:
            home_team = partido['home_team']
            away_team = partido['away_team']
            lambda_home, lambda_away = 1.65, 1.10 
            prob_dict = simular_partido_futbol(lambda_home, lambda_away)
            
            for bookmaker in partido.get('bookmakers', []):
                for market in bookmaker.get('markets', []):
                    if market['key'] == 'h2h':
                        for outcome in market['outcomes']:
                            nombre_cuota = outcome['name']
                            cuota_ofrecida = outcome['price']
                            
                            if nombre_cuota == home_team:
                                tipo_apuesta, prob_modelo = "Local", prob_dict["Home"]
                            elif nombre_cuota == away_team:
                                tipo_apuesta, prob_modelo = "Visitante", prob_dict["Away"]
                            else:
                                tipo_apuesta, prob_modelo = "Empate", prob_dict["Draw"]
                            
                            ev = (prob_modelo * cuota_ofrecida) - 1
                            if ev >= MIN_EV:
                                mensaje = (
                                    f"🚨 *¡OPORTUNIDAD +EV DETECTADA!* 🚨\n\n"
                                    f"⚔️ {home_team} vs {away_team}\n"
                                    f"🎯 Selección: {nombre_cuota}\n"
                                    f"📊 Cuota: {cuota_ofrecida}\n"
                                    f"💡 EV: {ev*100:.2f}%\n"
                                    f"💰 Stake: ${monto_stake:,.0f}"
                                )
                                enviar_alerta_telegram(mensaje)
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    analizar_mercado_futbol()
