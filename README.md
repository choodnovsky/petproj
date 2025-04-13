## Пошаговый рецепт

1. `docker-compose up -d --build` запуск зоопарка
2. `bash clean.sh`  (оставанливаем и убиваем контейнеры и все что с ними связано, чтобы не занимать ресурсы)
3. Для воссатновления базы в постгрес переходим в контейнер `docker exec -it postgres psql -U postgres -c 'CREATE DATABASE dvdrental;'`
4. там восстанавливаем базу `docker exec -it postgres pg_restore -U postgres -d dvdrental --verbose /upload_pg/dvdrental_new.tar`
где:
- -U это пользователь
- -d это имя базы
5. Проверяем какие есть модели в контйнере с олламой `docker exec -it ollama ollama list` там должно быть пусто типо того `{"models":[]} `
6. Загрузим в контейнер модель `docker exec -it ollama ollama pull mistral`

____
Как усилить RAG:
1.	📥 Ингест новых документов (из вики).
2.  🧠 Улучшение chunking — адаптация размера к смыслу.
3.	🔍 Настройка топ-k поиска и reranking.
4.	📊 Логирование + валидация ответов (например, с помощью метрик или фидбэка).
5.	🛡️ Фильтры: по категориям, правам доступа и т.д.

##### 1.Подготовка данных (замена lotr.txt на корпоративную вики)  

Цель: заменить data/lotr.txt на загрузку всех нужных корпоративных документов.

---

Шаги:  
а) Соберать всю корпоративную вики:  
- Если она в виде HTML/Markdown/Confluence/Notion/Google Docs и т.п. — сначала выгрузить текст.   
- Сохранить все статьи в один или несколько .txt или .md файлов.  
б) Объединить всё в один файл data/wiki_corpus.txt или сохранить пофайлово — Chroma поддрживает оба варианта.  
в) Убедиться, что в ingest.py используем правильный путь к этим файлам. Пример:

```angular2html
persist_directory = "chroma_db"
source_directory = "data/wiki"

loader = TextLoader(source_directory)
documents = loader.load()
```
Или через LangChain DirectoryLoader, если файлов много:

```angular2html
from langchain.document_loaders import DirectoryLoader
loader = DirectoryLoader(source_directory, glob="**/*.txt")
```
##### 2. Индексация в ChromaDB (добавляем векторные представления корпоративной вики)   
Цель: превратить текстовые документы из корпоративной вики в векторы и сохранить их в ChromaDB.

----
Шаги:  
а) Убедиться, что используем правильный код для загрузки и индексации документов. Например:  
```angular2html
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# 1. Загружаем документы
loader = DirectoryLoader("data/wiki", glob="**/*.txt")
documents = loader.load()

# 2. Разбиваем текст на чанки
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
docs = text_splitter.split_documents(documents)

# 3. Векторизуем с помощью модели
embedding = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# 4. Индексируем в Chroma
db = Chroma.from_documents(
    documents=docs,
    embedding=embedding,
    persist_directory="chroma_db"
)
db.persist()
```
🧠 Важно:  
- Убедиться, что `persist_directory="chroma_db"` — совпадает с директорией, которую монтирует твой Docker-контейнер chroma.  
- Убедиться, что модель `all-MiniLM-L6-v2` скачивается при первом запуске — она нужна для эмбеддингов.  
---- 


✅ После выполнения этого шага, в ChromaDB будут сохранены векторные представления всей корпоративной вики.  

##### 3. Извлечение релевантной информации из ChromaDB по запросу   
Цель: при получении запроса — найти наиболее релевантные фрагменты из корпоративной вики и передать их модели.

-------
```angular2html
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings

# 1. Подключаемся к уже сохранённой базе
embedding = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
db = Chroma(
    persist_directory="chroma_db",
    embedding_function=embedding
)

# 2. Выполняем поиск
def get_relevant_docs(query, k=3):
    results = db.similarity_search_with_score(query, k=k)
    docs = [doc.page_content for doc, score in results]
    return "\n".join(docs)

# Пример запроса
query = "Как устроена система согласований в нашей компании?"
context = get_relevant_docs(query)
print(context)
```
🧠 На что обратить внимание:  
- `similarity_search_with_score` возвращает пары (Document, score) — текст + расстояние.  
- Метод `page_content` достаёт текст из документа.  
- `k-3` — количество наиболее релевантных фрагментов, можно увеличивать.  

✅ После этого шага у нас будет текст-контекст, который можно отдать в промпт Ollama.  

##### 4. Формируем промпт и отправляем его в модель Ollama   
Цель: сформировать качественный промпт, куда подставим релевантный контекст (из ChromaDB) и сам вопрос пользователя, чтобы Ollama могла дать обоснованный ответ.

---

📌 Шаблон промпта:  
```angular2html
def build_prompt(context: str, question: str) -> str:
    return f"""Ты ассистент, отвечающий на вопросы на основе внутренней документации компании.

Контекст:
\"\"\"
{context}
\"\"\"

Вопрос: {question}
Ответ:"""
```
📌 Отправка запроса в Ollama:  
```angular2html
import requests
import json

def ask_ollama(prompt: str, model_name="llama3"):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model_name,
            "prompt": prompt,
            "stream": False
        }
    )
    if response.status_code == 200:
        return response.json().get("response", "")
    else:
        raise Exception(f"Ошибка при запросе к Ollama: {response.status_code} - {response.text}")
```
✅ Итоговая связка:

```angular2html
query = "Какие этапы включает процедура найма новых сотрудников?"
context = get_relevant_docs(query)
prompt = build_prompt(context, query)
response = ask_ollama(prompt)
print(response)
```

📎 Результат: Модель отвечает не “из головы”, а на основе корпоративной документации.  

##### 5. Как загрузить корпоративную вики в ChromaDB  

---

✅ Что нужно сделать:  
1. Собрать тексты из вики в одном месте (файлы .md, .txt, .html, .pdf, или даже .docx)
2. Разбить их на удобные чанки (для эмбеддингов)
3. Создать эмбеддинги 
4. Сохранить всё это в ChromaDB
5. Подтянуть данные из JSON, который будет содержать пары вопрос-ответ. Будем использовать эти пары для обучения или  
подбора контекста. Мы можем включить эти данные как дополнительный контекст или даже напрямую использовать для улучшения ответов.
----
🧱 Шаг 1: Сбор данных  
Собери всё, что есть из вики, в одну папку, например ./data/wiki/.  
Формат файлов: .txt, .md, .docx, .pdf — всё подходит. Чем чище, тем лучше.   

🧹 Шаг 2: Разбиение на чанки  
```angular2html
from langchain.text_splitter import RecursiveCharacterTextSplitter

def split_text(text, chunk_size=1000, chunk_overlap=300):
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_text(text)
```
🧠 Шаг 3: Получение эмбеддингов  
```angular2html
from sentence_transformers import SentenceTransformer

embed_model = SentenceTransformer("all-MiniLM-L6-v2")  # или "all-mpnet-base-v2"
```
📦 Шаг 4: Добавление в ChromaDB  
```angular2html
import os

def load_and_index_files(folder_path):
    for filename in os.listdir(folder_path):
        filepath = os.path.join(folder_path, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
            chunks = split_text(text)
            add_to_chroma(chunks, filename)

# Загрузка
load_and_index_files("./data/wiki/")
```
✅ Cкрипт для загрузки корпоративной вики в ChromaDB  
```angular2html
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
        print(f"⚠️ Размерность модели ({actual_dim}) не совпадает с размерностью коллекции ({expected_dim})")
        print("🔁 Удаляем и пересоздаём коллекцию...")
        client.delete_collection(collection_name)
        collection = client.create_collection(collection_name)
    else:
        print("✅ Размерность эмбеддингов совпадает или коллекция ещё не существует")

except chromadb.errors.NotFoundError:
    print("📁 Коллекция не найдена — создаём новую")
    collection = client.create_collection(collection_name)


# --- Функции ---
def split_text(text):
    return text_splitter.split_text(text)

def add_to_chroma(docs, source_name):
    print(f"🔹 Добавляем {len(docs)} чанков из {source_name}")
    for i, doc in tqdm(enumerate(docs), total=len(docs), desc=f"📥 {source_name}"):
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
                print(f"✅ Загружено: {filename} ({len(chunks)} чанков)")
        else:
            print(f"⚠️ Пропущен (неподдерживаемый формат): {filename}")


# 🔹 Точка входа
if __name__ == "__main__":
    load_and_index_files()
    print("✅ Индексация завершена!")
```
✅ Cкрипт для получения ответов от модели
```angular2html
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
```
