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

def create_db_connection():
    """Функция для создания подключения к базе данных."""
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )
    return conn