from sentence_transformers import SentenceTransformer
import chromadb
from tqdm import tqdm
import argparse
import ollama


def query_chromadb(question: str, top_k: int = 7):
    # Подключение к Chroma
    client = chromadb.HttpClient(host="localhost", port=8000)
    collection = client.get_collection("lotr")

    # Эмбеддинг вопроса
    model = SentenceTransformer("all-MiniLM-L6-v2")
    question_embedding = model.encode([question])[0].tolist()

    # Поиск похожих чанков
    print("🔎 Ищем релевантные чанки...")
    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=top_k,
        include=["documents"]
    )

    documents = results["documents"][0]
    print(f"📚 Найдено {len(documents)} релевантных фрагментов\n")

    # Объединяем все чанки в один контекст
    print("🧩 Собираем контекст...")
    context_parts = []
    for doc in tqdm(documents):
        context_parts.append(doc.strip())

    context = "\n---\n".join(context_parts)

    # Промпт к модели
    prompt = f"""Ответь на вопрос, используя контекст ниже.
Если в контексте нет ответа, скажи честно, что не знаешь.

Контекст:
{context}

Вопрос: {question}
Ответ:"""

    print("🤖 Запрашиваем ответ у модели...\n")
    response = ollama.chat(
        model="llama3",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    print("📝 Ответ модели:\n")
    print(response["message"]["content"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG-вопрос к базе знаний по LOTR")
    parser.add_argument("--question", type=str, required=True, help="Вопрос на русском")
    args = parser.parse_args()
    query_chromadb(args.question)