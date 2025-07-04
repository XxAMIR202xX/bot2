import os
import re
import base64
import asyncio
from collections import defaultdict

import google.generativeai as genai
from telegram import Update, File
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from pydub import AudioSegment
import speech_recognition as sr

# دریافت کلیدها
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
DEPLOY_URL = os.environ["DEPLOY_URL"]  # ← آدرس سایت در Render

# پیکربندی Gemini
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("models/gemini-1.5-flash-latest")

# حافظه مکالمه
MAX_MEMORY = 100
chat_memory = defaultdict(lambda: [])

# پاسخ‌دهی به پیام متنی
async def gemini_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_raw = update.message.text
    user_message = user_raw.strip()
    user_name = update.message.from_user.first_name or "دوست من"
    lowered = user_message.lower()
    chat_type = update.message.chat.type
    user_id = str(update.message.from_user.id)

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

    if any(word in lowered for word in ["سلام", "درود"]):
        await update.message.reply_text(f"سلام {user_name} عزیز! 🌷")
        return
    elif any(word in lowered for word in ["خدافظ", "خداحافظ", "بای"]):
        await update.message.reply_text(f"خداحافظ {user_name} نازنین! 👋")
        return
    elif any(word in lowered for word in ["خوبی", "چطوری", "حالت چطوره"]):
        await update.message.reply_text(f"مرسی {user_name} جان، من خوبم 😊 تو چطوری؟")
        return

    memory = chat_memory[user_id][-MAX_MEMORY:]
    history = [{"role": "user", "parts": [msg]} for msg in memory]
    history.append({"role": "user", "parts": [user_message]})

    try:
        response = model.generate_content([
            {"role": "user", "parts": ["تو یک دستیار فارسی‌زبان هستی. شوخ‌طبع باش و از ایموجی استفاده کن. "]}
        ] + history)
        reply = response.text
        chat_memory[user_id].append(user_message)
        chat_memory[user_id].append(reply)
        chat_memory[user_id] = chat_memory[user_id][-MAX_MEMORY:]
    except Exception as e:
        reply = f":x: خطا: {str(e)}"

    await update.message.reply_text(reply)

# تحلیل تصویر
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
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}},
                    {"text": "این تصویر چی نشون میده؟ لطفاً فارسی و دقیق بگو."}
                ]
            }
        ])
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text(f":x: خطا در تحلیل عکس: {str(e)}")

# ساخت و راه‌اندازی ربات
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gemini_reply))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

print("✅ Parsify bot is running...")

# اجرای Webhook برای Render
app.run_webhook(
    listen="0.0.0.0",
    port=int(os.environ.get("PORT", 8080)),
    webhook_url=f"{DEPLOY_URL}/{TELEGRAM_TOKEN}"
)