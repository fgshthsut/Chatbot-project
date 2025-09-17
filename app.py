import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify, session # เพิ่ม session
import sqlite3
import datetime
import uuid # เพิ่ม uuid สำหรับสร้าง ID ที่ไม่ซ้ำกัน

# --- ตั้งค่า Flask App ---
app = Flask(__name__)
# **สำคัญมาก!** เพิ่ม Secret Key สำหรับการใช้งาน Session
# ให้ตั้งเป็นข้อความอะไรก็ได้ที่เดายากๆ
app.secret_key = 'my-super-secret-key-for-chatbot-project'

# --- ตั้งค่า Gemini API ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') 
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-pro')

# ---- [เปลี่ยนแปลง] ----
# เราจะไม่ใช้ตัวแปร chat กลางแล้ว แต่จะใช้ dictionary เพื่อเก็บ session ของแต่ละคนแทน
chat_sessions = {} 

# --- ตั้งค่าฐานข้อมูล (Database) ---
DB_NAME = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # ---- [เปลี่ยนแปลง] ---- เพิ่มคอลัมน์ session_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL, 
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# ---- [เปลี่ยนแปลง] ---- เพิ่ม session_id เข้าไปตอนบันทึก
def add_message_to_db(session_id, sender, message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.datetime.now()
    cursor.execute("INSERT INTO chat_history (session_id, sender, message, timestamp) VALUES (?, ?, ?, ?)", 
                   (session_id, sender, message, timestamp))
    conn.commit()
    conn.close()

# --- สร้างหน้าเว็บ (Routes) ---

@app.route('/')
def index():
    # ---- [เปลี่ยนแปลง] ---- สร้าง session id ให้ผู้ใช้ใหม่ถ้ายังไม่มี
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return render_template('index.html')

@app.route('/send_message', methods=['POST'])
def send_message():
    user_message = request.json['message']
    
    # ---- [เปลี่ยนแปลง] ---- ดึง session_id ของผู้ใช้ปัจจุบัน
    session_id = session.get('session_id')
    if not session_id:
        # กรณีฉุกเฉินถ้า session หายไป
        return jsonify({'reply': 'เกิดข้อผิดพลาด: ไม่พบ Session ID'}), 400

    # ดึง session การแชทของ user คนนี้ขึ้นมา หรือสร้างใหม่ถ้ายังไม่มี
    user_chat = chat_sessions.get(session_id)
    if user_chat is None:
        user_chat = model.start_chat(history=[])
        chat_sessions[session_id] = user_chat

    # บันทึกข้อความจากผู้ใช้ลง DB พร้อม session_id
    add_message_to_db(session_id, 'user', user_message)

    try:
        # ส่งข้อความไปที่ Gemini (ใน session ของ user คนนี้)
        response = user_chat.send_message(user_message)
        bot_message = response.text
        
        # บันทึกข้อความจากบอทลง DB พร้อม session_id
        add_message_to_db(session_id, 'bot', bot_message)

        return jsonify({'reply': bot_message})
    except Exception as e:
        error_message = f"เกิดข้อผิดพลาด: {e}"
        add_message_to_db(session_id, 'bot', error_message)
        return jsonify({'reply': error_message})

@app.route('/history')
def history():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # ---- [เปลี่ยนแปลง] ---- ดึงข้อมูลโดยเรียงตาม session_id ก่อน แล้วค่อยเรียงตามเวลา
    cursor.execute("SELECT session_id, sender, message, timestamp FROM chat_history ORDER BY session_id, timestamp ASC")
    messages = cursor.fetchall()
    conn.close()

    # จัดกลุ่มข้อความตาม session_id
    grouped_messages = {}
    for msg in messages:
        sid = msg['session_id']
        if sid not in grouped_messages:
            grouped_messages[sid] = []
        grouped_messages[sid].append(dict(msg))
    
    return render_template('history.html', conversations=grouped_messages)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)