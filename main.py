import requests, time, random, sqlite3, threading, os
from datetime import datetime, timedelta
from flask import Flask

# --- КОНФИГ ---
TOKEN = 'ВАШ_ТОКЕН_БОТА' 
URL = f"https://api.telegram.org/bot{TOKEN}/"

app = Flask('')
@app.route('/')
def home(): return "Бот работает 24/7"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- БД ---
conn = sqlite3.connect('virus.db', check_same_thread=False)
cur = conn.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, dna REAL)')
cur.execute('CREATE TABLE IF NOT EXISTS inf (vic_id INTEGER PRIMARY KEY, inf_id INTEGER, exp TIMESTAMP)')
conn.commit()

def send(chat_id, text, reply_id=None):
    requests.post(URL + 'sendMessage', data={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown', 'reply_to_message_id': reply_id})

# --- ГЛАВНАЯ ЛОГИКА ---
def handle(upd):
    if 'message' not in upd or 'text' not in upd['message']: return
    
    msg = upd['message']
    chat_id = msg['chat']['id']
    uid = msg['from']['id']
    uname = msg['from'].get('first_name', 'Друг')
    txt = msg['text']

    if txt.startswith('/start'):
        send(chat_id, f"🦠 *Привет, {uname}!*\nСоздай вирус: `/create Имя`\nЗарази (ответ на сообщение): `/infect`\nСбор: `/collect`")

    elif txt.startswith('/create'):
        vname = txt.replace('/create', '').strip()
        if vname:
            try:
                cur.execute("INSERT INTO users VALUES (?, ?, 0)", (uid, vname))
                conn.commit()
                send(chat_id, f"✅ Вирус *{vname}* создан!")
            except:
                send(chat_id, "❌ Вирус уже есть.")
        else:
            send(chat_id, "⚠️ Напиши имя!")

    elif txt == '/infect':
        if 'reply_to_message' in msg:
            vic_id = msg['reply_to_message']['from']['id']
            vic_name = msg['reply_to_message']['from'].get('first_name', 'Цель')
            
            cur.execute("SELECT name FROM users WHERE id = ?", (uid,))
            user = cur.fetchone()
            
            if user and vic_id != uid:
                cur.execute("SELECT exp FROM inf WHERE vic_id = ?", (vic_id,))
                res = cur.fetchone()
                now = datetime.now()
                
                ready = True
                if res:
                    if now < datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S.%f'):
                        ready = False
                
                if ready:
                    exp = now + timedelta(days=1)
                    cur.execute("REPLACE INTO inf VALUES (?, ?, ?)", (vic_id, uid, exp))
                    conn.commit()
                    send(chat_id, f"☣️ *{user[0]}* заразил {vic_name} на 24 часа!")
                else:
                    send(chat_id, "🛡 Цель уже заражена!")
            else:
                send(chat_id, "❌ Ошибка: нет вируса или заражаешь себя.")
        else:
            send(chat_id, "⚠️ Ответь на сообщение жертвы!")

    elif txt == '/collect':
        cur.execute("SELECT COUNT(*) FROM inf WHERE inf_id = ?", (uid,))
        cnt = cur.fetchone()[0]
        if cnt > 0:
            up = cnt * random.randint(10, 30)
            cur.execute("UPDATE users SET dna = dna + ? WHERE id = ?", (up, uid))
            conn.commit()
            send(chat_id, f"🧪 Собрано {up} ДНК с {cnt} жертв!")
        else:
            send(chat_id, "💨 Нет жертв.")

    elif txt == '/stats':
        cur.execute("SELECT name, dna FROM users WHERE id = ?", (uid,))
        u = cur.fetchone()
        if u:
            cur.execute("SELECT COUNT(*) FROM inf WHERE inf_id = ?", (uid,))
            send(chat_id, f"🦠 *{u[0]}*\n🧬 ДНК: {u[1]}\n👥 Жертв: {cur.fetchone()[0]}")

# --- ЗАПУСК ---
if __name__ == '__main__':
    threading.Thread(target=run_server, daemon=True).start()
    last = 0
    while True:
        try:
            res = requests.get(URL + 'getUpdates', params={'offset': last + 1, 'timeout': 20}).json()
            if res.get('result'):
                for u in res['result']:
                    last = u['update_id']
                    handle(u)
        except:
            time.sleep(3)
