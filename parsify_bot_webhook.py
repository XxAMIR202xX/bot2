
import os
import re
import base64
import asyncio
from collections import defaultdict
from flask import Flask, request
import google.generativeai as genai
from telegram import Update, File
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# کلیدها
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]

# تنظیم Gemini
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("models/gemini-1.5-flash-latest")

# حافظه مکالمه
MAX_MEMORY = 100
chat_memory = defaultdict(lambda: [])

# پردازش پیام متنی
async def gemini_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_raw = update.message.text
    user_message = user_raw.strip()
    user_name = update.message.from_user.first_name or "دوست من"
    lowered = user_message.lower()
    chat_type = update.message.chat.type
    user_id = str(update.message.from_user.id)

    # فقط در گروه: بررسی وجود نام ربات
    if chat_type in ["group", "supergroup"]:
        if "parsify" not in lowered:
            return
        lowered = lowered.replace("parsify", "")
        user_message = user_message.replace("parsify", "")
        if not user_message.strip():
            await update.message.reply_text("بله؟ 😊")
            return

    if lowered.strip() == "parsify":
        await update.message.reply_text("بله؟ :smile:")
        return

    memory = chat_memory[user_id][-MAX_MEMORY:]
    history = [{"role": "user", "parts": [msg]} for msg in memory]
    history.append({"role": "user", "parts": [user_message]})

    try:
        response = model.generate_content([
            {
                "role": "user",
                "parts": ["تو یک دستیار فارسی‌زبان هستی. شوخ ‌طبع باش.از ایموجی در حرف هات استفاده کن"]
            }
        ] + history)
        reply = response.text
        chat_memory[user_id].append(user_message)
        chat_memory[user_id].append(reply)
        chat_memory[user_id] = chat_memory[user_id][-MAX_MEMORY:]
    except Exception as e:
        reply = f":x: خطا در پاسخ: {str(e)}"

    await update.message.reply_text(reply)

# پردازش عکس
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        photo = update.message.photo[-1]
        file: File = await photo.get_file()
        file_path = await file.download_to_drive()

        with open(file_path, "rb") as img:
            b64_img = base64.b64encode(img.read()).decode("utf-8")

        await update.message.reply_text("🖼️ در حال بررسی تصویر هستم...")

        response = model.generate_content([
            {
                "role": "user",
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": b64_img
                        }
                    },
                    {
                        "text": "این عکس چی نشون می‌ده؟ لطفاً با زبان فارسی توضیح بده."
                    }
                ]
            }
        ])
        await update.message.reply_text(response.text)

    except Exception as e:
        await update.message.reply_text(f":x: خطا در تحلیل عکس: {str(e)}")

# ساخت Flask برای وب‌هوک
flask_app = Flask(__name__)

@flask_app.route('/' + TELEGRAM_TOKEN, methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = Update.de_json(json_str, context.bot)
    context.bot.process_update(update)
    return 'ok'

def set_webhook():
    url = f'https://{os.environ["RENDER_URL"]}/{TELEGRAM_TOKEN}'
    context.bot.set_webhook(url)

# تنظیمات ربات
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gemini_reply))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

# شروع Flask و تنظیم وب‌هوک
set_webhook()
flask_app.run(host='0.0.0.0', port=8080)
print("✅ Parsify bot is running...")
