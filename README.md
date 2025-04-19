## Копроративный информационный помощник

- ### Проблема:
- ___Информационная перегрузка___ — в компаниях документы, инструкции, базы знаний распределены по разным каналам (PDF, Wiki, внутренние порталы). 
- ___Трудности поиска___ — сотрудники тратят значительное время на ручной поиск информации. 
- ___Зависимость от экспертов___ — многие вопросы направляются повторно к одним и тем же специалистам. 
- ___Потери времени при онбординге новых сотрудников___ — необходимость в наставничестве и повторяющихся ответах на одни и те же вопросы.  


- ### Задача: 
- Создание корпоративного интеллектуального помощника, способного оперативно и точно отвечать на вопросы сотрудников, 
основываясь на внутренней документации компании. Система призвана сократить время на поиск информации, 
минимизировать влияние «человеческого фактора» и повысить производительность.

- ### Попутно решаемые задачи:  
- ___HR___ Оценка интенсивности погружения нового сотрудника в бизнес-процессы компании
- ___СБ___ Какими именно бизнес-процессами интересуется новый сотрудник

-------------------
- ### Взаимодействия всех компонентов проекта и работы с оценкой, контекстом и диалогом:

1. Пользовательский ввод  
Пользователь отправляет вопрос в Telegram-бот.
2. Обработка вопроса  
Бот:
- Получает текст вопроса. 
- Ищет релевантные документы в ChromaDB по эмбеддингу вопроса (через `SentenceTransformer`). 
- Заружает весь предыдущий контекст (оценённые положительно ответы) из `Redis`. 
- Формирует системный `prompt` и массив messages для модели, включающий:
  - системные инструкции, 
  - ранее сохранённый контекст (`context_memory`), 
  - результат поиска из ChromaDB, 
  - текущий вопрос.
3. Генерация ответа  
- Отправляет messages в `Ollama`, модель `gemma:2b` (или другая, например `mistral` `llama3`, если нужна лёгкая). 
- Получает ответ от модели. 
- Отправляет ответ пользователю в чат реплаем. 
- Просит реплаем пользователя поставить оценку (inline-кнопки от 1 до 5).
4. Оценка после ответа:
- Если пользователь ставит оценку ≥ 4:
  - ответ добавляется в `context_memory`, который используется при следующем вопросе как “подтверждённые факты”. 
- Если пользователь ничего не ставит:
  - отает НЕ добавляется в `context_memory`
- Если пользователь ставит оценку < 4:
  - Бот просит реплаем оставить комментарий. 
  - Если пользователь пишет реплаем ответ, бот на него отвечает реплаем 2 кнопки
    - "это ваш ответ?" и "это наводящий вопрос?"
    - в первом случае ответ записывается в контекст
    - во втором, продолжается цепочка ответов от пункта 3 до тех по пока не будет оценка ответа >= 4 либо ответ пользователя
5. Redis
Хранит:
- `chatlogs`: список всех сообщений с полями `user_id, question, answer, rating, feedback, timestamp`. 
- `context_memory`: только качественные ответы (оценка ≥ 4), используемые как долгосрочная память.
6. ChromaDB
Используется как база знаний (вики и документация). Находятся релевантные куски текста по векторному поиску (top_k=4), чтобы модель могла дополнить контекст.  

-----------

- ### Пошаговое описание проекта:
1. Собираем контейнеры с инфраструктурой  
   - `Ollama` - хранение моделей
   - `CromaDB` - хранение векторной базы
2. Скрипты на `python` будут работать локально. После можно обернуть в отельный контейнер
3. `docker-compose up -d --build` запуск всей инфраструктуры
4. `bash clean.sh`  (оставанливаем и убиваем контейнеры и все что с ними связано, чтобы не занимать ресурсы)
5. ~~Для воссатновления базы в постгрес переходим в контейнер `docker exec -it postgres psql -U postgres -c 'CREATE DATABASE dvdrental;'`~~
6. ~~там восстанавливаем базу `docker exec -it postgres pg_restore -U postgres -d dvdrental --verbose /upload_pg/dvdrental_new.tar`~~
7. Проверяем какие есть модели в контйнере с олламой `docker exec -it ollama ollama list` с первого раза должно быть пусто типо того `{"models":[]} `
8. Загрузка в контейнер модели `docker exec -it ollama ollama pull llama3` `gemma:2b` `mistral...`
9. Собрать всю корпоративную вики:  
   - Если она в виде HTML/Markdown/Confluence/Notion/Google Docs и т.п. — сначала выгрузить текст.   
   - Сохранить все статьи в один или несколько .txt или .md файлов.  в отдельную дирректорию
10. Пофайлово + почанково загрузить все в `cromaDB` скриптом [rag_indexer_chunk.py](scripts/rag_indexer_chunk.py). Предполагается  
что документы будут докладываться, следовательно скрипт будет запускаться по расписанию 1 раз в час
11. Обернуть файл с формированием запроса в приложение работающее в режиме чатбота `telegramm` [tg_info_helper.py](tg/tg_info_helper.py)
