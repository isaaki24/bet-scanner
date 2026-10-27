import os
import requests
import csv
from datetime import datetime, timedelta
import hashlib

# --- CONFIGURACIÓN DE CREDENCIALES Y PARÁMETROS ---
API_KEY = "0263d119deb33d2831893b185acf7b14"
TELEGRAM_TOKEN = "8860037934:AAGerJjRrT_AD2yWp918_y5xC-I8SNj3YPm4"
CHAT_ID = "5811357869"

print("--- PRUEBA DE DIAGNÓSTICO EN VIVO ---")

BANKROLL_TOTAL = 1000000  
MIN_EV = 0.025            
MIN_PROB_REAL = 0.35      
MAX_DIAS_FUTURO = 2       
MAX_ODDS_AGE_SECONDS = 300  
MIN_BOOKMAKERS_FOR_CONSENSUS = 3 
CSV_FILE = "historial_apuestas.csv"

SPORTS_TO_SCAN = [
    {"nombre": "Fútbol - Premier League", "key": "soccer_epl"},
    {"nombre": "Fútbol - La Liga", "key": "soccer_spain_la_liga"}
]

def analizar_mercados():
    print("[*] Iniciando prueba de conexión directa con la API...")
    ahora_utc = datetime.utcnow()
    limite_fecha = ahora_utc + timedelta(days=MAX_DIAS_FUTURO)
    mercados_api = "h2h,spreads,totals"

    # Probamos con la primera liga para ver qué responde exactamente la API
    deporte = SPORTS_TO_SCAN[0]
    url = f"https://api.the-odds-api.com/v4/sports/{deporte['key']}/odds/?apiKey={API_KEY}&regions=eu&markets={mercados_api}&oddsFormat=decimal"
    
    print(f"[*] Consultando URL: {deporte['nombre']}")
    res = requests.get(url, timeout=15)
    
    print(f"[*] Código de estado HTTP de la API: {res.status_code}")
    
    if res.status_code != 200:
        print(f"[-] ERROR DE LA API: {res.text}")
        return

    data = res.json()
    print(f"[*] ¡Conexión exitosa! Partidos encontrados para esta liga: {len(data)}")
    if len(data) > 0:
        print(f"[*] Ejemplo de primer partido: {data[0].get('home_team')} vs {data[0].get('away_team')}")
    else:
        print("[-] La API respondió bien, pero devolvió una lista vacía de partidos para esta liga.")

if __name__ == "__main__":
    analizar_mercados()
