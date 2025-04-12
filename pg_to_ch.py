import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv
import clickhouse_connect


# Загружаем переменные окружения из .env
load_dotenv()

PG_HOST = "localhost"
PG_PORT = "5433"
PG_USER = os.getenv("POSTGRES_USER")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD")
PG_DB = os.getenv("POSTGRES_DB")

CH_HOST = "localhost"
CH_PORT = "8123"
CH_USER = os.getenv("CLICKHOUSE_USER")
CH_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD")
CH_DB = "dvdrental"

# Подключение к PostgreSQL
pg_conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)
pg_cursor = pg_conn.cursor()

# Подключение к ClickHouse
ch_client = clickhouse_connect.get_client(host=CH_HOST, port=CH_PORT, user=CH_USER, password=CH_PASSWORD)

# Создаём базу dvdrental в ClickHouse, если её нет
ch_client.command(f"CREATE DATABASE IF NOT EXISTS {CH_DB}")


# Получаем список всех таблиц в PostgreSQL
pg_cursor.execute("""SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'""")
tables = [row[0] for row in pg_cursor.fetchall()]

# Конвертируем типы данных из PostgreSQL в ClickHouse
type_mapping = {
    16: "Bool",  # BOOLEAN -> Bool
    17: "String",  # BYTEA -> String (хранение бинарных данных)
    18: "String",  # CHAR (1 символ) -> String
    19: "String",  # NAME -> String
    20: "Int64",  # BIGINT (INT8) -> Int64
    21: "Int16",  # SMALLINT (INT2) -> Int16
    22: "Array(Int16)",  # INT2VECTOR -> Массив маленьких чисел
    23: "Int32",  # INTEGER (INT4) -> Int32
    24: "UInt32",  # REGPROC (OID функции) -> UInt32
    25: "String",  # TEXT -> String
    26: "UInt32",  # OID -> UInt32
    27: "UInt64",  # TID -> UInt64 (уникальный идентификатор кортежа)
    28: "UInt32",  # XID -> UInt32 (ID транзакции)
    29: "UInt32",  # CID -> UInt32 (ID команды)
    30: "Array(UInt32)",  # OIDVECTOR -> Массив UInt32
    114: "String",  # JSON -> String
    142: "String",  # XML -> String
    194: "String",  # PG_NODE_TREE -> String
    600: "Tuple(Float64, Float64)",  # POINT -> Кортеж (X, Y)
    601: "Tuple(Tuple(Float64, Float64), Tuple(Float64, Float64))",  # LSEG -> Два POINT
    602: "Array(Tuple(Float64, Float64))",  # PATH -> Массив POINT
    603: "Tuple(Tuple(Float64, Float64), Tuple(Float64, Float64))",  # BOX -> Два POINT (прямоугольник)
    604: "Array(Tuple(Float64, Float64))",  # POLYGON -> Массив POINT
    700: "Float32",  # REAL (FLOAT4) -> Float32
    701: "Float64",  # DOUBLE PRECISION (FLOAT8) -> Float64
    705: "String",  # UNKNOWN -> String
    829: "String",  # MACADDR -> String
    869: "String",  # INET -> String
    1009: "Array(String)",
    1042: "String",  # CHAR(n) -> String
    1043: "String",  # VARCHAR(n) -> String
    1082: "Date",  # DATE -> Date
    1083: "String",  # TIME -> String (ClickHouse не поддерживает TIME)
    1114: "DateTime",  # TIMESTAMP -> DateTime
    1184: "DateTime64(3)",  # TIMESTAMPTZ -> DateTime64 с миллисекундами
    1186: "Interval",  # INTERVAL -> Interval (примерный аналог)
    1231: "Array(Float64)",  # NUMERIC[] -> Массив чисел
    1266: "String",  # TIMETZ -> String (ClickHouse не поддерживает TIME с часовыми поясами)
    1700: "Decimal(38, 10)",  # NUMERIC -> Decimal (с максимальной точностью)
    2278: "Nothing",  # VOID -> Nothing (аналог NULL в CH)
    2950: "UUID",  # UUID -> UUID
    3802: "String",  # JSONB -> String
    3904: "String",  # INT4RANGE -> String (ClickHouse не поддерживает диапазоны)
    3906: "String",  # NUMRANGE -> String
    3908: "String",  # TSRANGE -> String
    3910: "String",  # TSTZRANGE -> String
    3912: "String",  # DATERANGE -> String
}

def migrate(table):
    pg_cursor.execute(f"SELECT * FROM {table}")
    columns = [(desc[0], desc[1]) for desc in pg_cursor.description]
    columns
    ch_columns = []
    ch_columns_name = []

    for col_name, pg_type in columns:
        ch_type = type_mapping.get(pg_type, "String")
        ch_columns.append(f"`{col_name}` {ch_type}")
        ch_columns_name.append(f"{col_name}")
    # Создаём таблицу в ClickHouse внутри базы dvdrental
    ch_table = f"{CH_DB}.{table}"
    # ch_client.command(f"DROP TABLE IF EXISTS {ch_table}")
    ch_client.command(f"CREATE TABLE IF NOT EXISTS {ch_table} ({', '.join(ch_columns)}) ENGINE = MergeTree() ORDER BY tuple()")
    ch_client.command(f"TRUNCATE TABLE IF EXISTS {ch_table}")
    pg_cursor.execute(f"SELECT * FROM {table}")
    row = pg_cursor.fetchall()
    df = pd.DataFrame(row, columns=ch_columns_name)
    for col in df.select_dtypes(include=['object']):
        if col == 'picture':
            df[col] = ""
        else:
            df[col] = df[col].fillna("")
    for col in df.select_dtypes(include=['datetime64']):
        df[col] = df[col].fillna(pd.to_datetime('1970-01-01'))

    # Загружаем данные
    ch_client.insert_df(table=f"{ch_table}", df = df)
    print(f"✅ Таблица {ch_table} загружена в ClickHouse!")

for table in tables:
    migrate(table)

print("🎉 Все таблицы успешно перенесены в ClickHouse (dvdrental)!")
pg_conn.close()