import streamlit as st
import json
import redis
from sentence_transformers import SentenceTransformer
import chromadb
from ollama import Client
from configparser import ConfigParser

# Конфиг
parser = ConfigParser()
parser.read("config.ini")

# Подключение к Redis
redis_client = redis.Redis(host=parser.get("REDIS", "HOST"), port=int(parser.get("REDIS", "PORT")), decode_responses=True)

# Подключение к Ollama
ollama = Client(host='http://ollama:11434')

# Подключение к ChromaDB
client = chromadb.HttpClient(
    host=parser.get("CHROMADB", "HOST"),
    port=int(parser.get("CHROMADB", "PORT")),
)
collection = client.get_collection("wiki_docs")

# Модель эмбеддингов
model = SentenceTransformer("all-MiniLM-L6-v2")

# === Утилиты ===

def query_chromadb(question, top_k=4):
    question_embedding = model.encode([question])[0].tolist()
    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=top_k,
        include=["documents"]
    )
    documents = results["documents"][0] if results and results["documents"] else []
    return "\n".join(documents)

def save_context_to_redis(context_text):
    redis_client.rpush("context_memory", context_text)

def load_full_context():
    return "\n---\n".join(redis_client.lrange("context_memory", 0, -1))

def clear_memory():
    redis_client.delete("context_memory")
    keys = redis_client.keys("chatlog:*")
    for key in keys:
        redis_client.delete(key)
    st.session_state.chat_history = []
    st.session_state.show_fix_input = False

def save_chat_log(question, answer, rating=5, feedback=None):
    log_entry = {
        "question": question,
        "answer": answer,
        "rating": rating,
    }
    if feedback:
        log_entry["feedback"] = feedback

    redis_key = f"chatlog:{question[:100]}"
    redis_value = json.dumps(log_entry, ensure_ascii=False)
    redis_client.set(redis_key, redis_value)

    if rating >= 4:
        context_block = f"[Оценка: {rating}] Ответ: {answer}"
        save_context_to_redis(context_block)

# === Основная логика ===

def info_helper():
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "show_fix_input" not in st.session_state:
        st.session_state.show_fix_input = False

    if st.button("Очистить память"):
        clear_memory()
        st.success("Память очищена.")

    user_input = st.chat_input("Введите вопрос")

    if user_input:
        if user_input.strip().lower() == "/clear":
            clear_memory()
            st.success("Память полностью очищена.")
        else:
            with st.chat_message("user"):
                st.markdown(user_input)

            st.session_state.chat_history.append({"role": "user", "content": user_input})

            new_context = query_chromadb(user_input)
            full_context = load_full_context()

            messages = [
                {
                    "role": "system",
                    "content": (
                        "Ты корпоративный помощник, общающийся строго на русском языке. "
                        "Отвечай только на основе предоставленного контекста и предыдущих взаимодействий. "
                        "Если в базе нет информации для ответа — прямо скажи об этом, не выдумывай."
                    )
                },
                {
                    "role": "user",
                    "content": f"Вот подтверждённые факты, сохранённые в памяти:\n{full_context}"
                },
                {
                    "role": "user",
                    "content": f"А вот факты, извлечённые из базы знаний по текущему вопросу:\n{new_context}"
                },
                {
                    "role": "user",
                    "content": user_input
                }
            ] + st.session_state.chat_history

            response = ollama.chat(model="llama3", messages=messages)
            raw_answer = response["message"]["content"]

            st.session_state.chat_history.append({
                "role": "assistant",
                "raw_content": raw_answer,
                "content": raw_answer
            })

            with st.chat_message("assistant"):
                st.markdown(raw_answer)

    for i, msg in enumerate(st.session_state.chat_history):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            if msg["role"] == "assistant" and i == len(st.session_state.chat_history) - 1:
                col1, col2 = st.columns([1, 3])
                with col1:
                    if st.button("OK", key=f"ok_{i}"):
                        question = st.session_state.chat_history[i - 1]["content"]
                        answer = msg["raw_content"]
                        save_chat_log(question, answer, rating=5)
                        st.success("Ответ подтверждён и добавлен в память.")

                with col2:
                    st.markdown("### Оценка:")
                    score = st.slider("Насколько полезен ответ?", 1, 5, 5, key=f"rating_{i}")
                    feedback = None
                    if score < 4:
                        feedback = st.text_area("Что было не так?", key=f"feedback_{i}")

                    if st.button("📎 Сохранить оценку", key=f"confirm_rating_{i}"):
                        question = st.session_state.chat_history[i - 1]["content"]
                        answer = msg["raw_content"]
                        save_chat_log(question, answer, rating=score, feedback=feedback)
                        st.success("Оценка сохранена.")
