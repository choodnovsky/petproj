import streamlit as st
import redis
from datetime import datetime, timedelta
import streamlit_cookies_manager
from streamlit_option_menu import option_menu
from info_helper import info_helper


from configparser import ConfigParser

parser = ConfigParser()
parser.read("config.ini")

# Конфигурация cookies
cookies = streamlit_cookies_manager.EncryptedCookieManager(
    prefix="crm_app_",  # Префикс для куки
    password="password",  # Пароль для шифрования cookies
)

# Максимальное количество одновременных сеансов
MAX_SESSIONS = 5

# Установка длительности сессии
SESSION_DURATION = timedelta(minutes=30)  # Время сессии (30 минут)

# Список пользователей и паролей
USER_CREDENTIALS = {user: parser.get('USER_CREDENTIALS', user) for user in parser['USER_CREDENTIALS']}

redis_client = redis.StrictRedis(
    host=parser.get("REDIS", "HOST"),
    port=int(parser.get("REDIS", "PORT")),
    db=0)


# Функция для проверки лимита сессий
def check_session_limit():
    active_sessions = redis_client.smembers("active_sessions")
    if len(active_sessions) >= MAX_SESSIONS:
        st.warning("Достигнуто максимальное количество активных сеансов. Попробуйте позже.")
        st.stop()


# Инициализация cookies (обязательно для корректной работы)
if not cookies.ready():
    st.stop()


# Функция для авторизации с кешированием данных
@st.cache_data
def authenticate_user(username, password):
    if username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password:
        return True
    return False


# Функция для авторизации ции
def login():
    if "logged_in" not in cookies:
        cookies["logged_in"] = "false"
        cookies["username"] = ""  # Сохранение имени пользователя в cookies
        cookies["login_time"] = ""

    if cookies["logged_in"] == "true":
        st.session_state.logged_in = True
        st.session_state.username = cookies.get("username", "")  # Безопасное получение имени пользователя из cookies
        st.session_state.login_time = datetime.fromisoformat(cookies["login_time"])
    else:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.login_time = None

    active_sessions = redis_client.smembers("active_sessions")  # Добавляем пользователя\
    # к числу активных сессий в приложении

    if not st.session_state.logged_in:
        with st.sidebar:  # Форма авторизации
            st.title("Авторизация")
            username = st.text_input("Логин")
            password = st.text_input("Пароль", type="password")

            if st.button("Войти"):
                # Проверяем лимит сессий
                check_session_limit()
                if authenticate_user(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username  # Сохраняем имя пользователя
                    st.session_state.login_time = datetime.now()

                    # Сохраняем состояние сессии в cookies
                    cookies["logged_in"] = "true"
                    cookies["username"] = username  # Сохранение имени пользователя в cookies
                    cookies["login_time"] = st.session_state.login_time.isoformat()
                    cookies.save()  # Сохраняем куки
                    redis_client.sadd("active_sessions", username)  # Добавляем пользователя в активные сессии в Redis

                    st.success(f"Добро пожаловать, {username}!")
                    st.rerun()
                else:
                    st.error("Неправильный логин или пароль")
    else:
        st.sidebar.write(f"Вы авторизованы как {st.session_state.username}!")
        st.sidebar.write(f"Активные сессии: {len(active_sessions)}/{MAX_SESSIONS}")
        st.sidebar.write(f"Пользователи онлайн: {', '.join([session.decode('utf-8') for session in active_sessions]) or 'Никого'}")

        if st.sidebar.button("Выйти"):
            st.session_state.logged_in = False
            redis_client.srem("active_sessions", st.session_state.username)
            cookies["logged_in"] = "false"
            cookies["username"] = ""  # Удаляем имя пользователя из cookies при выходе
            cookies["login_time"] = ""
            cookies.save()  # Сохраняем куки
            st.rerun()


# Функция для проверки времени сессии
def check_session_timeout():
    if st.session_state.logged_in:
        current_time = datetime.now()
        login_time = st.session_state.login_time

        if current_time - login_time > SESSION_DURATION:
            st.warning("Время сессии истекло. Пожалуйста, авторизуйтесь снова.")
            st.session_state.logged_in = False
            cookies["logged_in"] = "false"
            cookies["username"] = ""  # Удаляем имя пользователя из cookies при истечении сессии
            cookies["login_time"] = ""
            cookies.save()  # Сохраняем куки
            redis_client.srem("active_sessions", st.session_state.username)  # Удаляем пользователя из активных сессий в Redis
            st.rerun()


# Основной контент приложения
def show_landing():
    with st.sidebar:
        choice = option_menu(
            menu_title=None,
            options=[
                'Корпопом',
            ],
            icons=[
                'info-circle-fill',
            ], menu_icon="cast",
            default_index=0
        )

    if choice == "Корпопом":
        info_helper()


# Функция для вывода всех значений cookies
def display_cookies():
    st.write("Текущие значения cookies:")
    for key, value in cookies.items():
        st.write(f"{key}: {value}")

# Пример использования


# Основная функция приложения
def main():
    login()  # Проверяем авторизацию

    # Проверяем на истечение времени сессии
    if st.session_state.logged_in:
        check_session_timeout()

    # Показываем основной контент, если пользователь авторизован
    if st.session_state.logged_in:
        show_landing()
    else:
        st.warning("Пожалуйста, авторизуйтесь для доступа к приложению.")

    # display_cookies()


if __name__ == "__main__":
    main()