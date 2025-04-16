import streamlit as st
import json
import os
from sentence_transformers import SentenceTransformer
import chromadb
from ollama import Client
from configparser import ConfigParser

# Конфиг
parser = ConfigParser()
parser.read("config.ini")

# Пути к файлам
CONTEXT_FILE = "/usr/src/data/context_memory.txt"
CHAT_LOG_FILE = "/usr/src/data/chat_log.jsonl"

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

def save_context_to_file(context_text):
    os.makedirs(os.path.dirname(CONTEXT_FILE), exist_ok=True)
    with open(CONTEXT_FILE, "a", encoding="utf-8") as f:
        f.write(context_text + "\n---\n")

def load_full_context():
    if os.path.exists(CONTEXT_FILE):
        with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def save_chat_log(question, answer):
    os.makedirs(os.path.dirname(CHAT_LOG_FILE), exist_ok=True)
    log_entry = {"question": question, "answer": answer}
    with open(CHAT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

def clear_memory():
    if os.path.exists(CONTEXT_FILE):
        os.remove(CONTEXT_FILE)
    if os.path.exists(CHAT_LOG_FILE):
        os.remove(CHAT_LOG_FILE)
    st.session_state.chat_history = []
    st.session_state.show_fix_input = False

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
            # Показываем вопрос
            with st.chat_message("user"):
                st.markdown(user_input)

            st.session_state.chat_history.append({"role": "user", "content": user_input})

            new_context = query_chromadb(user_input)
            full_context = load_full_context()

            messages = [
                {
                    "role": "system",
                    "content": (
                        "Ты корпоративный помощник. Всегда отвечай на русском языке. "
                        "Используй цепочку размышлений. Используй информацию из прошлых взаимодействий.\n\n"
                        f"Исторический контекст:\n{full_context}"
                    )
                }
            ] + st.session_state.chat_history

            response = ollama.chat(model="llama3", messages=messages)
            raw_answer = response["message"]["content"]

            st.session_state.chat_history.append({
                "role": "assistant",
                "raw_content": raw_answer,
                "content": raw_answer + "\n\n_Если ответ кажется неточным, нажмите 'Исправить' ниже. Я учту это в будущем._"
            })

            with st.chat_message("assistant"):
                st.markdown(st.session_state.chat_history[-1]["content"])

    # Отображаем историю
    for i, msg in enumerate(st.session_state.chat_history):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            if msg["role"] == "assistant" and i == len(st.session_state.chat_history) - 1:
                col1, col2 = st.columns([1, 3])
                with col1:
                    if st.button("OK", key=f"ok_{i}"):
                        question = st.session_state.chat_history[i - 1]["content"]
                        answer = msg["raw_content"]
                        save_context_to_file(answer)
                        save_chat_log(question, answer)
                        st.success("Ответ подтверждён и добавлен в память.")

                with col2:
                    if st.button("Исправить", key=f"fix_{i}"):
                        st.session_state.show_fix_input = True

                if st.session_state.show_fix_input:
                    fixed = st.text_area("Введите исправленный ответ", key=f"fix_text_{i}")
                    if st.button("💾 Сохранить исправление", key=f"save_fix_{i}"):
                        st.session_state.chat_history[i]["raw_content"] = fixed
                        st.session_state.chat_history[i]["content"] = (
                            fixed + "\n\n_Если ответ кажется неточным, нажмите 'Исправить' ниже. Я учту это в будущем._"
                        )
                        question = st.session_state.chat_history[i - 1]["content"]
                        save_context_to_file(fixed)
                        save_chat_log(question, fixed)
                        st.success("Исправление сохранено.")
                        st.session_state.show_fix_input = False