from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from sentence_transformers import SentenceTransformer
import chromadb
from ollama import Client
from configparser import ConfigParser
import redis
from datetime import datetime, timezone
import json

# === Настройка ===
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

ollama = Client(
    host=f'http://{parser.get("OLLAMA", "HOST")}:{parser.get("OLLAMA", "PORT")}'
)
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

def save_chat_log(question, answer, rating=5, feedback=None, user_id=None, username=None):
    log_entry = {
        "user_id": user_id,
        "username": username,
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
def is_new_question(message):
    return message.reply_to_message is None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Я информационный помощник, чем помочь?")

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_input = message.text

    # Новый вопрос (без реплая)
    if is_new_question(message):
        new_context = query_chromadb(user_input)
        full_context = load_full_context()

        messages = [
            {"role": "system", "content": "Ты корпоративный помощник, общающийся строго на русском языке. Отвечай только на основе предоставленного контекста."},
            {"role": "user", "content": f"Вот подтверждённые факты:\n{full_context}"},
            {"role": "user", "content": f"Вот факты по вопросу:\n{new_context}"},
            {"role": "user", "content": user_input},
        ]

        response = ollama.chat(model="gemma:2b", messages=messages)
        answer = response["message"]["content"]

        context.user_data.update({
            "last_question": user_input,
            "last_answer": answer,
            "user_id": message.from_user.id,
            "username": message.from_user.full_name or message.from_user.username,
            "state": "awaiting_rating"
        })

        reply_msg = await message.reply_text(answer, reply_to_message_id=message.message_id)

        keyboard = [[
            InlineKeyboardButton("⭐ 1", callback_data="rate_1"),
            InlineKeyboardButton("⭐ 2", callback_data="rate_2"),
            InlineKeyboardButton("⭐ 3", callback_data="rate_3"),
            InlineKeyboardButton("⭐ 4", callback_data="rate_4"),
            InlineKeyboardButton("⭐ 5", callback_data="rate_5"),
        ]]
        await message.reply_text("Пожалуйста, оцени ответ:", reply_markup=InlineKeyboardMarkup(keyboard), reply_to_message_id=reply_msg.message_id)
        return

    # Пользователь отвечает на сообщение бота
    if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
        keyboard = [[
            InlineKeyboardButton("Это мой ответ", callback_data="user_answer"),
            InlineKeyboardButton("Это наводящий вопрос", callback_data="follow_up"),
        ]]
        await message.reply_text("Как это трактовать?", reply_markup=InlineKeyboardMarkup(keyboard), reply_to_message_id=message.message_id)

async def handle_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    rating = int(query.data.split("_")[1])
    question = context.user_data.get("last_question")
    answer = context.user_data.get("last_answer")
    user_id = context.user_data.get("user_id")
    username = context.user_data.get("username")

    if not question or not answer:
        await query.edit_message_text("Не удалось сохранить оценку.")
        return

    if rating >= 4:
        save_chat_log(question, answer, rating, user_id=user_id, username=username)
        await query.edit_message_text(f"Спасибо за оценку {rating} ⭐️!")
        context.user_data["state"] = "awaiting_reply"
    else:
        await query.edit_message_text("Спасибо за оценку.")
        context.user_data["state"] = None

async def handle_reply_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "user_answer":
        user_text = query.message.reply_to_message.text
        question = context.user_data.get("last_question")
        user_id = context.user_data.get("user_id")
        username = context.user_data.get("username")
        save_chat_log(question, user_text, rating=5, user_id=user_id, username=username)
        save_context_to_redis(f"[Оценка: 5] Ответ: {user_text}")
        await query.edit_message_text("Спасибо! Ваш ответ сохранён")
        context.user_data["state"] = None

    elif action == "follow_up":
        fake_update = Update(update.update_id, message=query.message.reply_to_message)
        await handle_user_message(update=fake_update, context=context)

async def setup_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Начать")
    ])

# === Запуск ===
def main():
    token = parser.get("TELEGRAM", "BOT_TOKEN")
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))
    app.add_handler(CallbackQueryHandler(handle_rating_callback, pattern="rate_"))
    app.add_handler(CallbackQueryHandler(handle_reply_action))

    app.run_polling()

if __name__ == "__main__":
    main()