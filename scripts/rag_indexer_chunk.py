import os
import chromadb
import logging
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from chromadb.errors import NotFoundError

# Настройки
CHROMA_HOST = "localhost"
CHROMA_PORT = 8000
COLLECTION_NAME = "wiki_docs"
FOLDER_PATH = "../data/wiki/"
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 400

# Логгирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Модель и клиент
embed_model = SentenceTransformer("all-MiniLM-L6-v2")
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP
)
client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)


# Получение или создание коллекции
def get_or_create_collection(name):
    try:
        collection = client.get_collection(name)

        actual_dim = embed_model.get_sentence_embedding_dimension()
        expected_dim = None

        # Проверка безопасная: metadata может быть None
        if collection.metadata and "dimension" in collection.metadata:
            expected_dim = collection.metadata["dimension"]

        if expected_dim and expected_dim != actual_dim:
            logging.warning(f"Размерность модели ({actual_dim}) ≠ коллекции ({expected_dim}). Пересоздаём.")
            client.delete_collection(name)
            return client.create_collection(name)
        else:
            return collection

    except NotFoundError:
        logging.info("Коллекция не найдена. Создаём новую.")
        return client.create_collection(name)


collection = get_or_create_collection(COLLECTION_NAME)


# Разделение текста
def split_text(text):
    chunks = text_splitter.split_text(text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


# Проверка, был ли уже загружен файл
def is_file_already_indexed(filename):
    try:
        results = collection.get(where={"source": filename}, limit=1)
        return len(results["documents"]) > 0
    except Exception as e:
        logging.warning(f"Ошибка при проверке наличия файла {filename}: {e}")
        return False


# Добавление в ChromaDB
def add_to_chroma(docs, source_name):
    for i, doc in enumerate(docs):
        doc_id = f"{source_name}_{i}"
        embedding = embed_model.encode(doc).tolist()
        collection.add(
            documents=[doc],
            embeddings=[embedding],
            metadatas=[{"source": source_name, "chunk": i}],
            ids=[doc_id]
        )


# Индексация файлов
def load_and_index_files(folder_path):
    files = [f for f in os.listdir(folder_path) if f.endswith((".txt", ".md"))]

    for filename in tqdm(files, desc="Индексация файлов"):
        if is_file_already_indexed(filename):
            logging.info(f"Пропущен (уже в базе): {filename}")
            continue

        filepath = os.path.join(folder_path, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                text = file.read()
                chunks = split_text(text)

                if chunks:
                    add_to_chroma(chunks, filename)
                    logging.info(f"Загружено: {filename} ({len(chunks)} чанков)")
                else:
                    logging.warning(f"Пустой или короткий файл: {filename}")

        except Exception as e:
            logging.error(f"Ошибка при обработке {filename}: {e}")


# Точка входа
if __name__ == "__main__":
    load_and_index_files(FOLDER_PATH)
    logging.info("Индексация завершена.")