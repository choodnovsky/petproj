## Пошаговый рецепт clickhouse
____

1. docker-compose up -d (собираем контейнеры, где моунтим папку restore и на компе и в контейнере)
2. docker ps (проверяем что контйнеры запущены)
3. docker exec -it clickhouse_click_server_1 /bin/bash (переходим в контейнер)
4. clickhouse client (внутри контейнера запускаем клиент)
5. CREATE DATABASE work; (обычной командой создаем базу)
6. CREATE TABLE work.metrika  
                (  
                    `EventDate` Date,  
                    `CounterID` UInt32,  
                    `UserID` UInt64,  
                    `RegionID` UInt32  
                )  
                ENGINE = MergeTree()  
                PARTITION BY toYYYYMM(EventDate)  
                ORDER BY (CounterID, EventDate, intHash32(UserID));  
                (обычной командой создаем таблицу)
7. exit (на время выходим из режима клиента обратно в контейнер)
8. cat /restore/metrika_sample.tsv | clickhouse-client --database work --query "INSERT INTO metrika FORMAT TSV" (файл csv или tsv должен быть в папке restore соответсвенно он будет в папке restore в контейнере. Bash командой читаем содержимое файла и клиентом заливаем его в ранее подготовленную таблицу)
9. clickhouse client (снова переходим в клиент)
10. SELECT  
        UserID,  
        COUNT(UserID) as `cnt`  
        FROM homework.metrika m  
        GROUP BY UserID  
        ORDER BY `cnt` DESC  
        LIMIT 1  
        (мутим какойньть запрос и получаем резузьтат)  
11. exit (выходим из режима клиента)
12. exit (выходим из контейнера)
13. docker-compose down --volumes --remove-orphans  (оставанливаем и убиваем контейнеры и все что с ними связано, чтобы не занимать ресурсы)
- должен запуститься контейнер
8. переходим в контейнер `docker exec -it postgres psql -U postgres -c 'CREATE DATABASE dvdrental;'`
9. там восстанавливаем базу `docker exec -it postgres pg_restore -U postgres -d dvdrental --verbose /upload_pg/dvdrental_new.tar`
где:
- -U это пользователь
- -d это имя базы
10. Проверяем какие есть модели в контйнере с олламой `docker exec -it ollama ollama list` там должно быть пусто типо того `{"models":[]} `
11. Загрузим в контейнер модель `docker exec -it ollama ollama pull mistral`
12. Перезгружаем контейнер с вебмордой `docker-compose restart open-webui`
