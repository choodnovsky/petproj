import streamlit as st
import json
from sentence_transformers import SentenceTransformer
import chromadb
import ollama


# Инициализация глобального контекста
context = ""  # Начальный пустой контекст


# Загрузка данных из JSON файла
def load_qa_pairs(json_file):
    with open(json_file, "r", encoding="utf-8") as file:
        qa_pairs = json.load(file)
    return qa_pairs


# Функция для обновления контекста
def update_context(question, answer):
    global context
    context += f"Вопрос: {question}\nОтвет: {answer}\n---\n"  # Добавляем новый вопрос и ответ


# Запрос в ChromaDB
def query_chromadb(collection_name, question, top_k=4):
    global context

    client = chromadb.HttpClient(host="localhost", port=8000)
    collection = client.get_collection(collection_name)

    model = SentenceTransformer("all-MiniLM-L6-v2")
    question_embedding = model.encode([question])[0].tolist()

    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=top_k,
        include=["documents", "distances"]
    )

    if not results or "documents" not in results or not results["documents"]:
        return "Нет релевантных документов.", []

    documents = results["documents"][0]
    distances = results.get("distances", [None])[0]

    chunks_info = []
    context_parts = []
    for i, doc in enumerate(documents):
        distance = distances[i] if distances else "N/A"
        chunks_info.append(f"🔹 Чанк #{i+1} (расстояние: {distance:.4f}):\n{doc}\n")
        context_parts.append(doc.strip())

    context += "\n".join(context_parts)
    return "\n".join(chunks_info), context_parts


# Функция для запроса к модели с цепочкой размышлений
def query_with_thought_chain(question):
    global context
    prompt = f"""
    Ты — корпоративный помощник. Ответь на вопрос как можно точнее, используя исключительно информацию из предоставленного текста.
    Если ответа нет — так и скажи.
    
    Всегда отвечай на русском языке.
    
    Контекст:
    {context}
    Вопрос:
    {question}
    Ответ (с пояснением):
    """

    response = ollama.chat(
        model="llama3",
        messages=[{"role": "user", "content": prompt}]
    )

    answer = response["message"]["content"]
    update_context(question, answer)
    return answer


# Интеграция с правильными вопросами и ответами из JSON
def integrate_qa_pairs(qa_pairs):
    global context
    for pair in qa_pairs:
        question = pair["question"]
        answer = pair["answer"]
        update_context(question, answer)


qa_pairs = load_qa_pairs("./data/qa_pairs.json")
integrate_qa_pairs(qa_pairs)

# Streamlit UI
st.subheader("RAG-вопрос к корпоративной базе")

collection = st.selectbox("Коллекция в ChromaDB", options=["wiki_docs", "payments", "reports"])
question = st.text_area("Введите вопрос")

if st.button("Получить ответ"):
    with st.spinner("Ищем релевантные документы..."):
        chunks_info, _ = query_chromadb(collection, question)
        # st.markdown("### Найденные чанки")
        # st.text(chunks_info)

    with st.spinner("Генерируем ответ..."):
        answer = query_with_thought_chain(question)
        st.markdown("### Ответ")
        st.write(answer)
