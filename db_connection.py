"""
Модуль для создания подключения к базе данных PostgreSQL.

Параметры подключения загружаются из переменных окружения (.env):
- DB_NAME — имя базы данных;
- DB_USER — пользователь базы данных;
- DB_PASSWORD — пароль пользователя;
- DB_HOST — адрес сервера базы данных;
- DB_PORT — порт базы данных.

Используется для всех операций с базой данных в проекте VK Dating Bot.
"""

import os

import psycopg2
from dotenv import load_dotenv

# Загрузка переменных из .env
load_dotenv()

# Настройка подключения к базе данных
db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")

def create_db_connection() -> psycopg2.extensions.connection:
    """
    Создает подключение к базе данных PostgreSQL.

    Использует параметры из переменных окружения: DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT.

    Returns:
        psycopg2.extensions.connection: Объект подключения к базе данных.

    Raises:
        psycopg2.OperationalError: Если подключение не удалось.
    """
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )
    return conn