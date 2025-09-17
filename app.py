import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
import sqlite3
import datetime

# --- ตั้งค่า Flask App ---
app = Flask(__name__)

# --- ตั้งค่า Gemini API ---
# **สำคัญมาก!** ใส่ API Key ของคุณตรงนี้
# บรรทัดใหม่
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')
chat = model.start_chat(history=[]) # เริ่ม session การแชท

# --- ตั้งค่าฐานข้อมูล (Database) ---
DB_NAME = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # สร้างตารางถ้ายังไม่มี
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def add_message_to_db(sender, message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.datetime.now()
    cursor.execute("INSERT INTO chat_history (sender, message, timestamp) VALUES (?, ?, ?)", 
                   (sender, message, timestamp))
    conn.commit()
    conn.close()

# --- สร้างหน้าเว็บ (Routes) ---

# หน้าหลักสำหรับแชท
@app.route('/')
def index():
    return render_template('index.html')

# API สำหรับรับส่งข้อความ
@app.route('/send_message', methods=['POST'])
def send_message():
    user_message = request.json['message']
    
    # บันทึกข้อความจากผู้ใช้ลง DB
    add_message_to_db('user', user_message)

    try:
        # ส่งข้อความไปที่ Gemini
        response = chat.send_message(user_message)
        bot_message = response.text
        
        # บันทึกข้อความจากบอทลง DB
        add_message_to_db('bot', bot_message)

        return jsonify({'reply': bot_message})
    except Exception as e:
        error_message = f"เกิดข้อผิดพลาด: {e}"
        add_message_to_db('bot', error_message) # บันทึกข้อผิดพลาด
        return jsonify({'reply': error_message})

# หน้าสำหรับดูประวัติการสนทนา
@app.route('/history')
def history():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # ทำให้เข้าถึงข้อมูลแบบ dict ได้
    cursor = conn.cursor()
    cursor.execute("SELECT sender, message, timestamp FROM chat_history ORDER BY timestamp ASC")
    messages = cursor.fetchall()
    conn.close()
    return render_template('history.html', messages=messages)


if __name__ == '__main__':
    init_db() # สร้างไฟล์และตารางในฐานข้อมูลก่อนรัน
    app.run(debug=True) # debug=True สำหรับตอนพัฒนา, ตอนส่งครูเอาออกได้