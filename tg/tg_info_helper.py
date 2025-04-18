import json
import redis
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)

from sentence_transformers import SentenceTransformer
import chromadb
from ollama import Client
from configparser import ConfigParser

# === Конфигурация ===
parser = ConfigParser()
parser.read("config.ini")

redis_client = redis.Redis(
    host=parser.get("REDIS", "HOST"),
    port=int(parser.get("REDIS", "PORT")),
    decode_responses=True
)

chroma = chromadb.HttpClient(
    host=parser.get("CHROMADB", "HOST"),
    port=int(parser.get("CHROMADB", "PORT")),
)
collection = chroma.get_collection("wiki_docs")

ollama = Client(host=f'http://{parser.get("OLLAMA", "HOST")}:{parser.get("OLLAMA", "PORT")}')
model = SentenceTransformer("all-MiniLM-L6-v2")

# === Утилиты ===

def query_chromadb(question, top_k=4):
    embedding = model.encode([question])[0].tolist()
    results = collection.query(query_embeddings=[embedding], n_results=top_k, include=["documents"])
    documents = results["documents"][0] if results and results["documents"] else []
    return "\n".join(documents)

def save_context_to_redis(context_text):
    redis_client.rpush("context_memory", context_text)

def load_full_context():
    return "\n---\n".join(redis_client.lrange("context_memory", 0, -1))

def clear_memory():
    redis_client.delete("context_memory")

def save_chat_log(question, answer, rating=5, feedback=None, user_id=None):
    log_entry = {
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "answer": answer,
        "rating": rating,
    }
    if feedback:
        log_entry["feedback"] = feedback

    redis_client.rpush("chatlogs", json.dumps(log_entry, ensure_ascii=False))

    if rating >= 4:
        save_context_to_redis(f"[Оценка: {rating}] Ответ: {answer}")

# === Telegram Bot ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я информационный помощник, спрашивай 📚")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_memory()
    await update.message.reply_text("Память очищена.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id

    if user_input.strip().lower() == "/clear":
        await clear(update, context)
        return

    await update.message.reply_text("Обрабатываю вопрос...")

    new_context = query_chromadb(user_input)
    full_context = load_full_context()

    messages = [
        {"role": "system", "content": "Ты корпоративный помощник, общающийся строго на русском языке. Отвечай только на основе предоставленного контекста."},
        {"role": "user", "content": f"Вот подтверждённые факты:\n{full_context}"},
        {"role": "user", "content": f"Вот факты по вопросу:\n{new_context}"},
        {"role": "user", "content": user_input},
    ]

    response = ollama.chat(
        # model="llama3",
        model="gemma:2b",
        messages=messages)
    answer = response["message"]["content"]

    context.user_data["last_question"] = user_input
    context.user_data["last_answer"] = answer

    await update.message.reply_text(answer)

    keyboard = [
        [
            InlineKeyboardButton("⭐ 1", callback_data="rate_1"),
            InlineKeyboardButton("⭐ 2", callback_data="rate_2"),
            InlineKeyboardButton("⭐ 3", callback_data="rate_3"),
            InlineKeyboardButton("⭐ 4", callback_data="rate_4"),
            InlineKeyboardButton("⭐ 5", callback_data="rate_5"),
        ]
    ]
    await update.message.reply_text("Пожалуйста, оцени ответ:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    rating = int(query.data.split("_")[1])
    question = context.user_data.get("last_question")
    answer = context.user_data.get("last_answer")
    user_id = query.from_user.id

    if not question or not answer:
        await query.edit_message_text("Не удалось сохранить оценку.")
        return

    if rating >= 4:
        save_chat_log(question, answer, rating, user_id=user_id)
        await query.edit_message_text(f"Спасибо за оценку {rating} ⭐️!")
    else:
        context.user_data["awaiting_feedback"] = True
        context.user_data["rating"] = rating
        context.user_data["user_id"] = user_id
        await query.edit_message_text(f"Спасибо за оценку {rating} ⭐️. Напиши, пожалуйста, что можно улучшить:")

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_input = message.text

    # Если это reply на сообщение от бота — воспринимаем как уточнение
    if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
        context.user_data["last_question"] = user_input
        await handle_message(update, context)
        return

    # Если ожидается фидбэк
    if context.user_data.get("awaiting_feedback"):
        feedback = user_input
        question = context.user_data.get("last_question")
        answer = context.user_data.get("last_answer")
        rating = context.user_data.get("rating", 3)
        user_id = context.user_data.get("user_id")

        save_chat_log(question, answer, rating=rating, feedback=feedback, user_id=user_id)
        await update.message.reply_text("Спасибо! Ваш отзыв сохранён")
        context.user_data["awaiting_feedback"] = False
        return

    # Иначе — обычный вопрос
    await handle_message(update, context)

# === Запуск ===

def main():
    token = parser.get("TELEGRAM", "BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback))
    app.add_handler(CallbackQueryHandler(handle_rating_callback))

    app.run_polling()

if __name__ == "__main__":
    main()