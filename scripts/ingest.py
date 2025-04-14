import argparse
import chromadb
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import os

# with open("data/lotr.txt", "r+", encoding="utf-8") as f:
#     lines = f.readlines()
#     f.seek(0)
#     f.writelines([line for line in lines if line.strip() != ""])
#     f.truncate()

def clean_text(text: str) -> str:
    lines = text.splitlines()
    return "\n".join([line.strip() for line in lines if line.strip()])


def main(file_path: str):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        text = clean_text(f.read())

    print(f"Загружен файл: {file_path}")
    print(f"Размер текста: {len(text)} символов")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_text(text)
    print(f"Разбито на {len(chunks)} чанков")

    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(chunks, show_progress_bar=True)

    client = chromadb.HttpClient(host="localhost", port=8000)
    collection = client.get_or_create_collection("lotr")

    print(f"Загружаем чанки в ChromaDB...")
    for i, (chunk, emb) in tqdm(enumerate(zip(chunks, embeddings)), total=len(chunks)):
        collection.add(
            documents=[chunk],
            embeddings=[emb.tolist()],
            ids=[f"chunk_{i}"],
            metadatas=[{"source": os.path.basename(file_path), "index": i}]
        )

    print("Готово! Векторы успешно загружены в коллекцию 'lotr'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Индексация текста в ChromaDB")
    parser.add_argument(
        "--file",
        type=str,
        default="../data/lotr.txt",
        help="Путь к текстовому файлу (по умолчанию: data/lotr.txt)"
    )
    args = parser.parse_args()
    main(args.file)