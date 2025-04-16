# Используем более конкретную версию базового образа Python
FROM python:3.11-slim-buster

# Устанавливаем переменную окружения PYTHONUNBUFFERED для вывода
# вывода Python в реальном времени без буферизации
ENV PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

# Обновляем пакетный менеджер и устанавливаем зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    wget \
    libreadline-dev \
    libsqlite3-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем SQLite 3.41.2 вручную
RUN wget https://www.sqlite.org/2023/sqlite-autoconf-3410200.tar.gz && \
    tar xvfz sqlite-autoconf-3410200.tar.gz && \
    cd sqlite-autoconf-3410200 && \
    ./configure && make && make install && \
    cd .. && rm -rf sqlite-autoconf-3410200*

# Обновляем переменные окружения, чтобы Python использовал новую версию SQLite
ENV LD_LIBRARY_PATH="/usr/local/lib"
ENV PATH="/usr/local/bin:$PATH"

COPY app .
# VOLUME ${PWD}/config.ini: ${PWD}/config.ini


# Устанавливаем зависимости Python из файла requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
# В пекете streamlit_cookies_manager используется декоратор @st.cache нам надо заменить его на @st.cache_data
COPY encrypted_cookie_manager.py /usr/local/lib/python3.11/site-packages/streamlit_cookies_manager/

# Открываем порт 8501 для доступа к серверу Streamlit
EXPOSE 8501

# Устанавливаем проверку состояния контейнера с помощью команды curl
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Запускаем приложение Streamlit при запуске контейнера
CMD ["streamlit", "run", "streamlit_app_auth.py", "--server.port=8501", "--server.address=0.0.0.0"]

