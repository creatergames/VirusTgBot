import requests
import time
import random
import sqlite3
import threading
from flask import Flask
from datetime import datetime, timedelta

# --- КОНФИГ ---
TOKEN = 'ВАШ_ТОКЕН_БОТА'
URL = f"https://api.telegram.org/bot{TOKEN}/"

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Virus Bot is Alive!"

def run_web_server():
    # Render дает порт в переменной окружения PORT
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- ЛОГИКА БОТА ---
db = sqlite3.connect('virus_game.db', check_same_thread=False)
sql = db.cursor()
sql.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, level INTEGER, dna REAL)')
sql.execute('CREATE TABLE IF NOT EXISTS infections (victim_id INTEGER PRIMARY KEY, infector_id INTEGER, expiry TIMESTAMP)')
db.commit()

def send_msg(chat_id, text, reply_to=None):
    requests.post(URL + 'sendMessage', data={'chat_id': chat_id, 'text': text, 'reply_to_message_id': reply_to})

def process_message(msg):
    chat_id = msg['chat']['id']
    user_id = msg['from']['id']
    text = msg.get('text', '')

    if text.startswith('/create'):
        name = text.replace('/create', '').strip()
        if not name: return send_msg(chat_id, "Напиши: /create [Имя]")
        try:
            sql.execute("INSERT INTO users VALUES (?, ?, 1, 0.0)", (user_id, name))
            db.commit()
            send_msg(chat_id, f"🦠 Вирус '{name}' создан!")
        except: send_msg(chat_id, "У тебя уже есть вирус!")

    elif text == '/infect':
        if 'reply_to_message' not in msg:
            return send_msg(chat_id, "⚠️ Ответь на сообщение жертвы!")
        
        victim_id = msg['reply_to_message']['from']['id']
        victim_name = msg['reply_to_message']['from'].get('first_name', 'Юзер')
        now = datetime.now()

        sql.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        attacker = sql.fetchone()
        if not attacker: return send_msg(chat_id, "Сначала /create")

        sql.execute("SELECT expiry FROM infections WHERE victim_id = ?", (victim_id,))
        current = sql.fetchone()

        if current:
            expiry_time = datetime.strptime(current[0], '%Y-%m-%d %H:%M:%S.%f')
            if now < expiry_time:
                return send_msg(chat_id, f"🚫 {victim_name} уже заражен кем-то другим!")
            else:
                sql.execute("DELETE FROM infections WHERE victim_id = ?", (victim_id,))

        expiry = now + timedelta(days=1)
        sql.execute("INSERT INTO infections VALUES (?, ?, ?)", (victim_id, user_id, expiry))
        db.commit()
        send_msg(chat_id, f"☣️ {attacker[0]} заразил {victim_name} на 24 часа! Никто другой его не тронет.")

    elif text == '/stats':
        sql.execute("SELECT name, level, dna FROM users WHERE id = ?", (user_id,))
        v = sql.fetchone()
        if v:
            send_msg(chat_id, f"🧬 Вирус: {v[0]}\nУровень: {v[1]}\nДНК: {v[2]}")

# --- ГЛАВНЫЙ ЦИКЛ ---
def bot_polling():
    last_id = 0
    while True:
        try:
            r = requests.get(URL + 'getUpdates', params={'offset': last_id + 1, 'timeout': 30}).json()
            if r.get('result'):
                for upd in r['result']:
                    last_id = upd['update_id']
                    if 'message' in upd: process_message(upd['message'])
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    # Запускаем веб-сервер в отдельном потоке
    threading.Thread(target=run_web_server).start()
    # Запускаем бота
    bot_polling()
