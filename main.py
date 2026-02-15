import requests
import time
import random
import sqlite3
import threading
import os
from flask import Flask
from datetime import datetime, timedelta

# --- КОНФИГ ---
TOKEN = '8527378266:AAGFVC1Mk85Thwfozwu2Dx7iMQ9NWGZYHVI'
URL = f"https://api.telegram.org/bot{TOKEN}/"

# --- ВЕБ-СЕРВЕР (Чтобы Render не выключал бота) ---
app = Flask('')

@app.route('/')
def home():
    return "Virus Game Server is Running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- БАЗА ДАННЫХ ---
db = sqlite3.connect('virus_game.db', check_same_thread=False)
sql = db.cursor()
sql.execute('''CREATE TABLE IF NOT EXISTS users 
               (id INTEGER PRIMARY KEY, name TEXT, level INTEGER, dna REAL, last_collect TIMESTAMP)''')
sql.execute('''CREATE TABLE IF NOT EXISTS infections 
               (victim_id INTEGER PRIMARY KEY, infector_id INTEGER, expiry TIMESTAMP)''')
db.commit()

# --- ФУНКЦИИ ТЕЛЕГРАМ ---
def send_msg(chat_id, text, reply_to=None):
    params = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    if reply_to:
        params['reply_to_message_id'] = reply_to
    requests.post(URL + 'sendMessage', data=params)

# --- ЛОГИКА КОМАНД ---
def process_message(msg):
    if 'text' not in msg: return
    
    chat_id = msg['chat']['id']
    user_id = msg['from']['id']
    user_name = msg['from'].get('first_name', 'Герой')
    text = msg['text']

    # Приветствие
    if text.startswith('/start'):
        welcome_text = (
            f" привет, *{user_name}*! 🦠\n\n"
            "Ты попал в лабораторию 'Virus Evolution'.\n"
            "Твоя цель — создать смертельный вирус и доминировать в чате.\n\n"
            "📍 *Команды:*\n"
            "▫️ `/create [Имя]` — создать свой вирус\n"
            "▫️ `/infect` — (ответом на сообщение) заразить цель на 24 часа\n"
            "▫️ `/collect` — собрать энергию с зараженных\n"
            "▫️ `/stats` — состояние твоей заразы"
        )
        send_msg(chat_id, welcome_text)

    # Создание вируса
    elif text.startswith('/create'):
        name = text.replace('/create', '').strip()
        if not name:
            return send_msg(chat_id, "⚠️ Укажи имя вируса! Пример: `/create Эбола`")
        
        try:
            sql.execute("INSERT INTO users (id, name, level, dna) VALUES (?, ?, ?, ?)", (user_id, name, 1, 0.0))
            db.commit()
            send_msg(chat_id, f"✅ Вирус *{name}* успешно создан! Теперь выбери жертву и напиши `/infect` в ответ на её сообщение.")
        except:
            send_msg(chat_id, "❌ У тебя уже есть вирус. Используй `/stats`.")

    # Заражение (Reply)
    elif text == '/infect':
        if 'reply_to_message' not in msg:
            return send_msg(chat_id, "⚠️ Нужно ответить на сообщение человека, которого хочешь заразить!")
        
        victim_id = msg['reply_to_message']['from']['id']
        victim_name = msg['reply_to_message']['from'].get('first_name', 'Цель')
        
        if victim_id == user_id:
            return send_msg(chat_id, "☣️ Ты не можешь заразить сам себя.")

        # Проверка атакующего
        sql.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        attacker = sql.fetchone()
        if not attacker: return send_msg(chat_id, "❌ Сначала создай вирус через `/create`.")

        # Проверка защиты
        now = datetime.now()
        sql.execute("SELECT expiry, infector_id FROM infections WHERE victim_id = ?", (victim_id,))
        current = sql.fetchone()

        if current:
            expiry_time = datetime.strptime(current[0], '%Y-%m-%d %H:%M:%S.%f')
            if now < expiry_time:
                return send_msg(chat_id, f"🛡 *{victim_name}* уже заражен другим вирусом! Доступ заблокирован на 24 часа.")
            else:
                sql.execute("DELETE FROM infections WHERE victim_id = ?", (victim_id,))

        # Успешное заражение
        expiry = now + timedelta(days=1)
        sql.execute("INSERT INTO infections VALUES (?, ?, ?)", (victim_id, user_id, expiry))
        db.commit()
        send_msg(chat_id, f"☣️ *{attacker[0]}* проник в организм *{victim_name}*!\n🔒 Цель заблокирована для других на 24 часа.")

    # Сбор энергии
    elif text == '/collect':
        sql.execute("SELECT COUNT(*) FROM infections WHERE infector_id = ?", (user_id,))
        count = sql.fetchone()[0]
        
        if count == 0:
            return send_msg(chat_id, "💨 Твоему вирусу некого кушать. Зарази кого-нибудь!")

        reward = count * random.randint(15, 40)
        sql.execute("UPDATE users SET dna = dna + ? WHERE id = ?", (reward, user_id))
        db.commit()
        send_msg(chat_id, f"🧪 Собрано *{reward}* энергии иммунитета с твоих жертв ({count} чел.).")

    # Статистика
    elif text == '/stats':
        sql.execute("SELECT name, level, dna FROM users WHERE id = ?", (user_id,))
        v = sql.fetchone()
        if not v: return send_msg(chat_id, "У тебя еще нет вируса.")
        
        sql.execute("SELECT COUNT(*) FROM infections WHERE infector_id = ?", (user_id,))
        victims = sql.fetchone()[0]
        
        status = (
            f"🧬 *Статус вируса: {v[0]}*\n"
            f"━━━━━━━━━━━━━━\n"
            f"📊 Уровень: {v[1]}\n"
            f"⚡ Энергия: {v[2]}\n"
            f"👥 Заражено сейчас: {victims}"
        )
        send_msg(chat_id, status)

# --- ЦИКЛ ---
def bot_loop():
    last_id = 0
    while True:
        try:
            res = requests.get(URL + 'getUpdates', params={'offset': last_id + 1, 'timeout': 20}).json()
            if 'result' in res:
                for upd in res['result']:
                    last_id = upd['update_id']
                    if 'message' in upd: process_message(upd['message'])
        except:
            time.sleep(2)

if __name__ == '__main__':
    threading.Thread(target=run_web_server).start()
    print("Бот запущен...")
    bot_loop()
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
