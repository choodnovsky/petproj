## Пошаговый рецепт

1. Собираем контейнеры с инфраструктурой  
   - `Ollama` - хранение моделей
   - `CromaDB` - хранение векторной базы
2. Скрипты будут работать локально. После можно обернуть в отельный контейнер
3. `docker-compose up -d --build` запуск зоопарка
4. `bash clean.sh`  (оставанливаем и убиваем контейнеры и все что с ними связано, чтобы не занимать ресурсы)
5. ~~Для воссатновления базы в постгрес переходим в контейнер `docker exec -it postgres psql -U postgres -c 'CREATE DATABASE dvdrental;'`~~
6. ~~там восстанавливаем базу `docker exec -it postgres pg_restore -U postgres -d dvdrental --verbose /upload_pg/dvdrental_new.tar`~~
7. Проверяем какие есть модели в контйнере с олламой `docker exec -it ollama ollama list` там должно быть пусто типо того `{"models":[]} `
8. Загрузим в контейнер модель `docker exec -it ollama ollama pull llama3`
------

Шаги:  
1. Соберать всю корпоративную вики:  
- Если она в виде HTML/Markdown/Confluence/Notion/Google Docs и т.п. — сначала выгрузить текст.   
- Сохранить все статьи в один или несколько .txt или .md файлов.  
2. Пофайлово + почанково загрузить все в `cromaDB` скриптом [rag_indexer_chunk.py](scripts/rag_indexer_chunk.py)
3. Добавить JSON с правильными вопрос-ответами для обновления правильного контекста [qa_pairs.json](data/qa_pairs.json)
4. Обернуть файл с формированием запроса в приложение `streamlit` [streamlit_app.py](streamlit/app/streamlit_app.py)