"""Obtén tu chat_id de Telegram (paso único de setup).

PASOS:
1. En Telegram, busca a @BotFather, manda /newbot y sigue las instrucciones
   para crear tu bot. Te da un TOKEN — ponlo en data/secrets.json
   (campo "telegram_bot_token") antes de seguir.
2. Busca a TU bot (el que acabas de crear) en Telegram y mándale cualquier
   mensaje, por ejemplo "hola".
3. Corre este script: python get_telegram_chat_id.py
4. Copia el chat_id que te imprime y ponlo en data/secrets.json
   (campo "telegram_chat_id").
"""
import requests
from config import TELEGRAM_BOT_TOKEN


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Falta TELEGRAM_BOT_TOKEN en data/secrets.json. Sigue el paso 1 de este archivo primero.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    resultados = data.get("result", [])
    if not resultados:
        print("No encontré mensajes todavía.")
        print("¿Ya le mandaste un mensaje a tu bot en Telegram? Mándaselo y vuelve a correr este script.")
        return

    chats_vistos = {}
    for update in resultados:
        msg = update.get("message", {})
        chat = msg.get("chat", {})
        if chat.get("id"):
            chats_vistos[chat["id"]] = chat.get("first_name") or chat.get("title") or "?"

    print("Chats encontrados:")
    for chat_id, nombre in chats_vistos.items():
        print(f"  chat_id = {chat_id}   (de: {nombre})")

    print("\nCopia el chat_id de arriba (el tuyo, el de tu conversación con el bot) "
          "y ponlo en data/secrets.json como \"telegram_chat_id\".")


if __name__ == "__main__":
    main()
