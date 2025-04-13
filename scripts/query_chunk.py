import json
from sentence_transformers import SentenceTransformer
import chromadb
from tqdm import tqdm
import argparse
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
def query_chromadb(collection: str, question: str, top_k: int = 4):
    # Подключение к Chroma
    client = chromadb.HttpClient(host="localhost", port=8000)
    collection = client.get_collection(collection)

    # Эмбеддинг вопроса
    model = SentenceTransformer("all-MiniLM-L6-v2")
    question_embedding = model.encode([question])[0].tolist()

    # Поиск похожих чанков
    print("🔎 Ищем релевантные чанки...")
    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=top_k,
        include=["documents", "distances"]
    )

    # Проверка, что результаты не пустые
    if not results or "documents" not in results or not results["documents"]:
        print("⚠️ Нет релевантных документов.")
        return

    documents = results["documents"][0]
    distances = results.get("distances", [None])[0]

    print(f"📚 Найдено {len(documents)} релевантных фрагментов\n")

    # Объединяем все чанки в один контекст
    print("🧩 Собираем контекст...")
    context_parts = []
    for i, doc in tqdm(enumerate(documents)):
        distance = distances[i] if distances else "N/A"
        print(f"🔹 Чанк #{i + 1} (расстояние: {distance}):\n{doc}\n")
        context_parts.append(doc.strip())

    global context
    context += "\n".join(context_parts)  # Обновляем контекст с найденными фрагментами


# Функция для запроса к модели с цепочкой размышлений
def query_with_thought_chain(question):
    global context
    prompt = f"""
    Ты — корпоративный помощник. Ответь на вопрос с подробным пояснением. Разбей процесс на шаги, если необходимо.
    Контекст:
    {context}
    Вопрос:
    {question}
    Ответ (с пояснением):
    """

    print("\n🤖 Запрашиваем ответ у модели...\n")
    response = ollama.chat(
        model="llama3",  # Используем модель LLaMA3
        messages=[{"role": "user", "content": prompt}]
    )

    answer = response["message"]["content"]

    # Обновляем контекст с ответом
    update_context(question, answer)

    return answer


# Интеграция с правильными вопросами и ответами из JSON
def integrate_qa_pairs(qa_pairs):
    global context
    for pair in qa_pairs:
        question = pair["question"]
        answer = pair["answer"]
        update_context(question, answer)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG-вопрос к базе знаний компании")
    parser.add_argument("--collection", type=str, required=True, help="Название коллекции в ChromaDB")
    parser.add_argument("--question", type=str, required=True, help="Вопрос на русском")
    parser.add_argument("--qa-file", type=str, required=False, help="Путь к файлу с парами вопрос-ответ в формате JSON",
                        default="./data/qa_pairs.json")

    args = parser.parse_args()

    # Загружаем правильные пары вопрос-ответ из JSON
    qa_pairs = load_qa_pairs(args.qa_file)

    # Интегрируем пары в контекст
    integrate_qa_pairs(qa_pairs)

    # Сначала ищем релевантные фрагменты в ChromaDB
    query_chromadb(args.collection, args.question)

    # Теперь задаем вопрос с учетом всего контекста
    answer = query_with_thought_chain(args.question)

    print("📝 Ответ модели:")
    print(answer)