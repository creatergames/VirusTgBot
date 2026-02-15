import requests
import time
import random
import sqlite3
import threading
import os
from datetime import datetime, timedelta
from flask import Flask

# --- КОНФИГ ---
# Вставь сюда свой токен от @BotFather
TOKEN = '8527378266:AAGFVC1Mk85Thwfozwu2Dx7iMQ9NWGZYHVI' 
URL = f"https://api.telegram.org/bot{TOKEN}/"

# --- ВЕБ-СЕРВЕР ---
app = Flask('')

@app.route('/')
def home():
    return "Virus Game Bot is Online!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- БАЗА ДАННЫХ ---
def get_db_connection():
    conn = sqlite3.connect('virus_game.db', check_same_thread=False)
    return conn

# Создаем таблицы при запуске
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (id INTEGER PRIMARY KEY, name TEXT, level INTEGER, dna REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS infections 
                      (victim_id INTEGER PRIMARY KEY, infector_id INTEGER, expiry TIMESTAMP)''')
    conn.commit()
    conn.close()

# --- ФУНКЦИИ ТЕЛЕГРАМ ---
def send_msg(chat_id, text, reply_to=None):
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    if reply_to:
        data['reply_to_message_id'] = reply_to
    try:
        requests.post(URL + 'sendMessage', data=data)
    except Exception as e:
        print(f"Ошибка отправки: {e}")

# --- ЛОГИКА КОМАНД ---
def handle_update(update):
    if 'message' not in update:
        return
    
    msg = update['message']
    if 'text' not in msg:
        return

    chat_id = msg['chat']['id']
    user_id = msg['from']['id']
    user_name = msg['from'].get('first_name', 'Игрок')
    text = msg['text']

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. СТАРТ
    if text.startswith('/start'):
        welcome = (
            f"🦠 *Добро пожаловать, {user_name}!* 🦠\n\n"
            "Ты — создатель вируса. Твоя цель: заразить всех!\n"
            "📍 *Как играть:*\n"
            "1️⃣ Назови вирус: `/create [Имя]`\n"
            "2️⃣ Зарази цель: Ответь на чьё-то сообщение командой `/infect`\n"
            "3️⃣ Собери энергию: Команда `/collect` даст ДНК\n\n"
            "⚠️ *Зараженный блокируется на 24 часа!*"
        )
        send_msg(chat_id, welcome)

    # 2. СОЗДАНИЕ
    elif text.startswith('/create'):
        virus_name = text.replace('/create', '').strip()
        if not virus_name:
            send_msg(chat_id, "⚠️ Напиши: `/create Название`")
        else:
            try:
                cursor.execute("INSERT INTO users VALUES (?, ?, 1, 0.0)", (user_id, virus_name))
                conn.commit()
                send_msg(chat_id, f"✅ Вирус *{virus_name}* готов к биологической войне!")
            except sqlite3.IntegrityError:
                send_msg(chat_id, "❌ У тебя уже есть вирус.")

    # 3. ЗАРАЖЕНИЕ
    elif text == '/infect':
        if 'reply_to_message' not in msg:
            send_msg(chat_id, "⚠️ Ответь на сообщение того, кого хочешь заразить!")
        else:
            victim_id = msg['reply_to_message']['from']['id']
            victim_name = msg['reply_to_message']['from'].get('first_name', 'Цель')

            if victim_id == user_id:
                send_msg(chat_id, "☣️ Нельзя заражать себя.")
            else:
                # Проверяем нападающего
                cursor.execute("SELECT name FROM users WHERE id = ?", (user_id,))
                attacker = cursor.fetchone()
                if not attacker:
                    send_msg(chat_id, "❌ Сначала создай вирус: `/create`")
                else:
                    # Проверяем жертву
                    now = datetime.now()
                    cursor.execute("SELECT expiry FROM infections WHERE victim_id = ?", (victim_id,))
                    current = cursor.fetchone()

                    if current:
                        expiry_time = datetime.strptime(current[0], '%Y-%m-%d %H:%M:%S.%f')
                        if now < expiry_time:
                            send_msg(chat_id, f"🛡 *{victim_name}* уже кем-то заражен! Жди 24 часа.")
                        else:
                            cursor.execute("DELETE FROM infections WHERE victim_id = ?", (victim_id,))
                            # Заражаем
                            expiry = now + timedelta(days=1)
                            cursor.execute("INSERT INTO infections VALUES (?, ?, ?)", (victim_id, user_id, expiry))
                            conn.commit()
                            send_msg(chat_id, f"☣️ *{attacker[0]}* успешно заразил *{victim_name}* на сутки!")
                    else:
                        expiry = now + timedelta(days=1)
                        cursor.execute("INSERT INTO infections VALUES (?, ?, ?)", (victim_id, user_id, expiry))
                        conn.commit()
                        send_msg(chat_id, f"☣️ *{attacker[0]}* успешно заразил *{victim_name}* на сутки!")

    # 4. СБОР
    elif text == '/collect':
        cursor.execute("SELECT COUNT(*) FROM infections WHERE infector_id = ?", (user_id,))
        count = cursor.fetchone()[0]
        if count == 0:
            send_msg(chat_id, "💨 Нет активных заражений.")
        else:
            reward = count * random.randint(10, 50)
            cursor.execute("UPDATE users SET dna = dna + ? WHERE id = ?", (reward, user_id))
            conn.commit()
            send_msg(chat_id, f"⚡ Ты собрал *{reward}* ДНК с *{count}* жертв!")

    # 5. СТАТЫ
    elif text == '/stats':
        cursor.execute("SELECT name, level, dna FROM users WHERE id = ?", (user_id,))
        v = cursor.fetchone()
        if v:
            cursor.execute("SELECT COUNT(*) FROM infections WHERE infector_id = ?", (user_id,))
            v_count = cursor.fetchone()[0]
            send_msg(chat_id, f"🦠 *{v[0]}*\n🧬 Уровень: {v[1]}\n⚡ ДНК: {v[2]}\n👥 Жертв: {v_count}")
        else:
            send_msg(chat_id, "Вируса нет.")

    conn.close()

# --- ПОЛЛИНГ ---
def start_bot():
    last_id = 0
    init_db()
    while True:
        try:
            response = requests.get(URL + 'getUpdates', params={'offset': last_id + 1, 'timeout': 30}).json()
            if response.get('result'):
                for update in response['result']:
                    last_id = update['update_id']
                    handle_update(update)
        except Exception as e:
            print(f"Ошибка сети: {e}")
            time.sleep(5)

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    print("Бот запускается...")
    start_bot()

# --- ФУНКЦИИ ТЕЛЕГРАМ ---
def send_msg(chat_id, text, reply_to=None):
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    if reply_to:
        data['reply_to_message_id'] = reply_to
    try:
        requests.post(URL + 'sendMessage', data=data)
    except Exception as e:
        print(f"Error sending message: {e}")

# --- ЛОГИКА ОБРАБОТКИ СООБЩЕНИЙ ---
def process_message(msg):
    if 'text' not in msg:
        return

    chat_id = msg['chat']['id']
    user_id = msg['from']['id']
    user_name = msg['from'].get('first_name', 'Герой')
    text = msg['text']
    sql = db_conn.cursor()

    # 1. ПРИВЕТСТВИЕ
    if text.startswith('/start'):
        welcome = (
            f"👋 *Приветствую в лаборатории, {user_name}!* 🦠\n\n"
            "Здесь ты можешь создать свой уникальный вирус и заражать других людей в группе.\n\n"
            "🎮 *Твой план действий:*\n"
            "1️⃣ Назови вирус: `/create [Имя]`\n"
            "2️⃣ Зарази цель: Ответь (reply) на сообщение человека командой `/infect`\n"
            "3️⃣ Собирай ДНК: Команда `/collect` даст тебе ресурсы с жертв\n\n"
            "🛡 *Правило:* Зараженный человек защищен от других вирусов на 24 часа."
        )
        send_msg(chat_id, welcome)

    # 2. СОЗДАНИЕ ВИРУСА
    elif text.startswith('/create'):
        name = text.replace('/create', '').strip()
        if not name:
            send_msg(chat_id, "⚠️ Ошибка! Напиши `/create Название` (например: `/create Ebola`)")
            return
        
        try:
            sql.execute("INSERT INTO users VALUES (?, ?, 1, 0.0)", (user_id, name))
            db_conn.commit()
            send_msg(chat_id, f"🧪 *Вирус '{name}' создан!* Теперь иди в чат и зарази кого-нибудь через `/infect`.")
        except sqlite3.IntegrityError:
            send_msg(chat_id, "❌ У тебя уже есть вирус! Используй `/stats`, чтобы на него посмотреть.")

    # 3. ЗАРАЖЕНИЕ (С ТВОИМИ УСЛОВИЯМИ)
    elif text == '/infect':
        if 'reply_to_message' not in msg:
            send_msg(chat_id, "⚠️ Чтобы заразить, ты должен *ответить* своим сообщением на сообщение жертвы!")
            return
        
        victim_id = msg['reply_to_message']['from']['id']
        victim_name = msg['reply_to_message']['from'].get('first_name', 'Жертва')

        if victim_id == user_id:
            send_msg(chat_id, "😒 Ты не можешь заразить самого себя.")
            return

        # Проверка, есть ли вирус у игрока
        sql.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        attacker = sql.fetchone()
        if not attacker:
            send_msg(chat_id, "❌ Сначала создай вирус: `/create [Имя]`")
            return

        # Проверка: не заражен ли уже?
        now = datetime.now()
        sql.execute("SELECT expiry, infector_id FROM infections WHERE victim_id = ?", (victim_id,))
        current = sql.fetchone()

        if current:
            expiry_time = datetime.strptime(current[0], '%Y-%m-%d %H:%M:%S.%f')
            if now < expiry_time:
                send_msg(chat_id, f"🛡 *{victim_name}* уже заражен! Его иммунитет сопротивляется. Попробуй через 24 часа.")
                return
            else:
                sql.execute("DELETE FROM infections WHERE victim_id = ?", (victim_id,))

        # Успешное заражение на 1 день
        expiry = now + timedelta(days=1)
        sql.execute("INSERT INTO infections VALUES (?, ?, ?)", (victim_id, user_id, expiry))
        db_conn.commit()
        send_msg(chat_id, f"☣️ *Успех!* Твой вирус *{attacker[0]}* заразил *{victim_name}*.\n🔐 Жертва заблокирована для других вирусов на 24 часа!")

    # 4. СБОР ЭНЕРГИИ
    elif text == '/collect':
        sql.execute("SELECT COUNT(*) FROM infections WHERE infector_id = ?", (user_id,))
        victims_count = sql.fetchone()[0]
        
        if victims_count == 0:
            send_msg(chat_id, "⚠️ Тебе не с кого собирать энергию. Сначала зарази людей через `/infect`!")
            return

        reward = victims_count * random.randint(10, 30)
        sql.execute("UPDATE users SET dna = dna + ? WHERE id = ?", (reward, user_id))
        db_conn.commit()
        send_msg(chat_id, f"🔋 Ты собрал *{reward} ДНК* с своих жертв ({victims_count} чел.)!")

    # 5. СТАТИСТИКА
    elif text == '/stats':
        sql.execute("SELECT name, level, dna FROM users WHERE id = ?", (user_id,))
        v = sql.fetchone()
        if v:
            sql.execute("SELECT COUNT(*) FROM infections WHERE infector_id = ?", (user_id,))
            v_count = sql.fetchone()[0]
            send_msg(chat_id, f"🦠 *Вирус:* {v[0]}\n🧬 *Уровень:* {v[1]}\n⚡ *Энергия ДНК:* {v[2]}\n👥 *Твои жертвы:* {v_count}")
        else:
            send_msg(chat_id, "У тебя еще нет вируса. Создай его: `/create`.")

# --- ГЛАВНЫЙ ЦИКЛ БОТА ---
def bot_polling():
    last_id = 0
    while True:
        try:
            r = requests.get(URL + 'getUpdates', params={'offset': last_id + 1, 'timeout': 30}).json()
            if r.get('result'):
                for upd in r['result']:
                    last_id = upd['update_id']
                    if 'message' in upd:
                        process_message(upd['message'])
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    # Запускаем веб-сервер в фоне
    threading.Thread(target=run_web_server, daemon=True).start()
    print("Bot is starting...")
    bot_polling()
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
