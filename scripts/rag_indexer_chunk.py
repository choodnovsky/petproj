import os
import chromadb
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from tqdm import tqdm

# Настройка моделей
embed_model = SentenceTransformer("all-MiniLM-L6-v2")  # 384-мерные эмбеддинги
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=400)

# Подключение к ChromaDB
client = chromadb.HttpClient(host="localhost", port=8000)
collection_name = "wiki_docs"

# Проверка коллекции
try:
    collection = client.get_collection(collection_name)
    # Получение информации о коллекции
    if collection and collection.metadata and 'dimension' in collection.metadata:
        expected_dim = collection.metadata["dimension"]
    else:
        expected_dim = None

    actual_dim = embed_model.get_sentence_embedding_dimension()

    if expected_dim and actual_dim != expected_dim:
        print(f"Размерность модели ({actual_dim}) не совпадает с размерностью коллекции ({expected_dim})")
        print("Удаляем и пересоздаём коллекцию...")
        client.delete_collection(collection_name)
        collection = client.create_collection(collection_name)
    else:
        print("Размерность эмбеддингов совпадает или коллекция ещё не существует")

except chromadb.errors.NotFoundError:
    print("Коллекция не найдена — создаём новую")
    collection = client.create_collection(collection_name)


# --- Функции ---
def split_text(text):
    return text_splitter.split_text(text)

def add_to_chroma(docs, source_name):
    print(f"Добавляем {len(docs)} чанков из {source_name}")
    for i, doc in tqdm(enumerate(docs), total=len(docs), desc=f"{source_name}"):
        embedding = embed_model.encode(doc).tolist()
        collection.add(
            documents=[doc],
            embeddings=[embedding],
            metadatas=[{"source": source_name, "index": i}],
            ids=[f"{source_name}_{i}"]
        )

def load_and_index_files(folder_path="../data/wiki/"):
    for filename in os.listdir(folder_path):
        filepath = os.path.join(folder_path, filename)
        if filename.endswith((".txt", ".md")):
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
                chunks = split_text(text)
                add_to_chroma(chunks, filename)
                print(f"Загружено: {filename} ({len(chunks)} чанков)")
        else:
            print(f"Пропущен (неподдерживаемый формат): {filename}")


# 🔹 Точка входа
if __name__ == "__main__":
    load_and_index_files()
    print("Индексация завершена!")