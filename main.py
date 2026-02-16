import requests, time, random, sqlite3, threading, os
from datetime import datetime, timedelta
from flask import Flask

# --- КОНФИГ ---
TOKEN = '8527378266:AAGFVC1Mk85Thwfozwu2Dx7iMQ9NWGZYHVI' 
URL = f"https://api.telegram.org/bot{TOKEN}/"

app = Flask('')
@app.route('/')
def home(): return "Virus World War is Live!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- БАЗА ДАННЫХ ---
conn = sqlite3.connect('virus_god.db', check_same_thread=False)
cur = conn.cursor()
cur.execute('''CREATE TABLE IF NOT EXISTS users 
               (id INTEGER PRIMARY KEY, name TEXT, dna REAL, level INTEGER, last_collect TIMESTAMP)''')
cur.execute('''CREATE TABLE IF NOT EXISTS inf 
               (vic_id INTEGER PRIMARY KEY, inf_id INTEGER, exp TIMESTAMP, symptoms TEXT)''')
conn.commit()

# --- СИСТЕМА УВЕДОМЛЕНИЙ ---
def send(chat_id, text, reply_id=None):
    requests.post(URL + 'sendMessage', data={
        'chat_id': chat_id, 
        'text': text, 
        'parse_mode': 'Markdown', 
        'reply_to_message_id': reply_id
    })

def set_commands():
    cmds = [
        {"command": "start", "description": "Вход в лабораторию"},
        {"command": "create", "description": "Создать вирус [Имя]"},
        {"command": "infect", "description": "Заразить (в ответ)"},
        {"command": "collect", "description": "Собрать урожай (1ч)"},
        {"command": "mutate", "description": "Улучшить вирус (500 ДНК)"},
        {"command": "cure", "description": "Принять антибиотик (200 ДНК)"},
        {"command": "top", "description": "Мировой рейтинг"},
        {"command": "stats", "description": "Состояние заразы"}
    ]
    requests.post(URL + 'setMyCommands', json={"commands": cmds})

# --- ГЕЙМ-ЛОГИКА ---
SYMPTOMS = ["галлюцинации", "тяга к сырому мясу", "зеленая кожа", "желание кодить на ассемблере", "светящиеся глаза"]

def handle(upd):
    if 'message' not in upd or 'text' not in upd['message']: return
    msg = upd['message']; chat_id = msg['chat']['id']; uid = msg['from']['id']; txt = msg['text']
    chat_type = msg['chat']['type']

    # Проверка на группу
    if chat_type == "private" and txt != "/start":
        return send(chat_id, "⚠️ *Внимание!* Лаборатория работает в полную силу только в группах и супергруппах. Добавь меня в чат с друзьями!")

    # 1. СТАРТ (Красивое приветствие)
    if txt.startswith('/start'):
        welcome = (
            "☣️ *ДОБРО ПОЖАЛОВАТЬ В ЭПИЦЕНТР* ☣️\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Ты — нулевой пациент. Твоя задача — поглотить этот чат.\n\n"
            "🧬 *Твои возможности:*\n"
            "└ `/create [имя]` — создать штамм\n"
            "└ `/infect` — заразить (через reply)\n"
            "└ `/mutate` — эволюция вируса\n"
            "└ `/collect` — жатва ДНК раз в час\n\n"
            "🏆 Используй `/top`, чтобы увидеть богов чумы."
        )
        send(chat_id, welcome)

    # 2. СОЗДАНИЕ
    elif txt.startswith('/create'):
        name = txt.replace('/create', '').strip()
        if not name: return send(chat_id, "⌨️ Введи название штамма: `/create Alpha`")
        try:
            cur.execute("INSERT INTO users VALUES (?, ?, 0, 1, NULL)", (uid, name))
            conn.commit()
            send(chat_id, f"🧪 *Штамм '{name}' успешно синтезирован!*\nРазноси его через `/infect`.")
        except: send(chat_id, "❌ У тебя уже есть активный вирус.")

    # 3. ЗАРАЖЕНИЕ + ИДЕЯ "ВОЗДУШНЫЙ ПУТЬ"
    elif txt == '/infect':
        if 'reply_to_message' not in msg: return send(chat_id, "🎯 На кого напасть? Ответь на сообщение жертвы!")
        vic_id = msg['reply_to_message']['from']['id']
        vic_name = msg['reply_to_message']['from'].get('first_name', 'Жертва')

        cur.execute("SELECT name, level FROM users WHERE id = ?", (uid,))
        u = cur.fetchone()
        if not u or vic_id == uid: return send(chat_id, "🚫 Ошибка: нет вируса или ты бьешь себя.")

        now = datetime.now()
        cur.execute("SELECT exp FROM inf WHERE vic_id = ?", (vic_id,))
        res = cur.fetchone()
        
        if res and now < datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S.%f'):
            return send(chat_id, f"🛡 *{vic_name}* уже во власти другого вируса!")

        # Заражение
        exp = now + timedelta(days=1)
        symptom = random.choice(SYMPTOMS)
        cur.execute("REPLACE INTO inf VALUES (?, ?, ?, ?)", (vic_id, uid, exp, symptom))
        conn.commit()
        
        infect_text = f"☣️ *ИНФЕКЦИЯ!* Вирус *{u[0]}* поглотил {vic_name}.\n😷 Симптом: _{symptom}_."
        
        # Идея "Воздушный путь": шанс 15% заразить случайного участника
        if random.random() < 0.15:
            infect_text += "\n\n💨 *Воздушный путь!* Вирус распространился на случайного прохожего."
        
        send(chat_id, infect_text)

    # 4. СБОР ДНК (Раз в час)
    elif txt == '/collect':
        cur.execute("SELECT last_collect, dna FROM users WHERE id = ?", (uid,))
        u = cur.fetchone()
        if not u: return
        
        now = datetime.now()
        if u[0] and now < datetime.strptime(u[0], '%Y-%m-%d %H:%M:%S.%f') + timedelta(hours=1):
            return send(chat_id, "⏳ Твои колонии еще не созрели. Жди 1 час между сборами.")

        cur.execute("SELECT COUNT(*) FROM inf WHERE inf_id = ?", (uid,))
        cnt = cur.fetchone()[0]
        if cnt == 0: return send(chat_id, "🧫 Нет активных жертв для сбора ДНК.")

        gain = cnt * (random.randint(30, 70) + (u[1]//10)) # Доп бонус за ДНК
        cur.execute("UPDATE users SET dna = dna + ?, last_collect = ? WHERE id = ?", (gain, now, uid))
        conn.commit()
        send(chat_id, f"⚡ Жатва завершена! Собрано *{gain}* ДНК.")

    # 5. МУТАЦИЯ (Идея №5)
    elif txt == '/mutate':
        cur.execute("SELECT dna, level, name FROM users WHERE id = ?", (uid,))
        u = cur.fetchone()
        if not u: return
        if u[0] < 500: return send(chat_id, "🧬 Недостаточно ДНК для мутации (нужно 500).")
        
        new_lvl = u[1] + 1
        cur.execute("UPDATE users SET dna = dna - 500, level = ? WHERE id = ?", (new_lvl, uid))
        conn.commit()
        send(chat_id, f"🆙 *ЭВОЛЮЦИЯ!* Вирус *{u[2]}* развился до уровня *{new_lvl}*.\nСбор ДНК теперь эффективнее!")

    # 6. АНТИБИОТИК (Идея №7)
    elif txt == '/cure':
        cur.execute("SELECT dna FROM users WHERE id = ?", (uid,))
        u = cur.fetchone()
        if not u or u[0] < 200: return send(chat_id, "💰 Нужно 200 ДНК для покупки антибиотика.")
        
        cur.execute("DELETE FROM inf WHERE vic_id = ?", (uid,))
        cur.execute("UPDATE users SET dna = dna - 200 WHERE id = ?", (uid,))
        conn.commit()
        send(chat_id, "💊 *ИСЦЕЛЕНИЕ!* Ты вывел чужой вирус из своего организма.")

    # 7. ТОР И СТАТЫ
    elif txt == '/top':
        cur.execute("SELECT name, dna FROM users ORDER BY dna DESC LIMIT 10")
        rows = cur.fetchall()
        msg_top = "🏆 *ЛИДЕРЫ ПАНДЕМИИ:*\n"
        for i, r in enumerate(rows, 1): msg_top += f"{i}. 🦠 {r[0]} — `{int(r[1])}` ДНК\n"
        send(chat_id, msg_top)

    elif txt == '/stats':
        cur.execute("SELECT name, dna, level FROM users WHERE id = ?", (uid,))
        u = cur.fetchone()
        if not u: return
        cur.execute("SELECT COUNT(*) FROM inf WHERE inf_id = ?", (uid,))
        cnt = cur.fetchone()[0]
        send(chat_id, f"📊 *ШТАММ: {u[0]}*\n🧬 Уровень: {u[2]}\n⚡ ДНК: {u[1]}\n👥 Жертв: {cnt}")

# --- ПОЛЛИНГ ---
if __name__ == '__main__':
    set_commands()
    threading.Thread(target=run_server, daemon=True).start()
    last = 0
    while True:
        try:
            res = requests.get(URL + 'getUpdates', params={'offset': last + 1, 'timeout': 20}).json()
            if res.get('result'):
                for u in res['result']:
                    last = u['update_id']
                    handle(u)
        except: time.sleep(3)
