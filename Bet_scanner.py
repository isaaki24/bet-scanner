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
                        
