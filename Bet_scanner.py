import os
import requests

TELEGRAM_TOKEN = "8860037934:AAGerJjRrT_AD2yWp918_y5xCI8SNj3YPm4"
CHAT_ID = "5811357869"

url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
payload = {"chat_id": CHAT_ID, "text": "🚨 *¡PRUEBA DE CONEXIÓN EXITOSA! El bot de GitHub está vivo.*", "parse_mode": "Markdown"}

res = requests.post(url, json=payload)
print(res.status_code)
print(res.text)
