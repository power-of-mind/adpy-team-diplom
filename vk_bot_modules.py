"""
Модуль взаимодействия с VK API и логики работы бота VK Dating Bot.

Функционал:
- Авторизация через токен группы (бот) и пользовательский токен VK.
- Получение информации о пользователях и их фотографий.
- Формирование и отправка сообщений пользователю.
- Создание клавиатуры VK.
- Хранение состояния последнего показанного кандидата.
- Основные функции запуска бота и обработки сообщений.

Модуль инкапсулирует всю логику взаимодействия с VK API и
используется вместе с модулем работы с базой данных.
"""

import os
import vk_api

from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from dotenv import load_dotenv

from db_modules import (get_next_candidate_from_db, add_to_status,
                        get_favorites, add_user_to_db)

load_dotenv()

access_token_bot = os.getenv('TOKEN_BOT')
access_token_user = os.getenv('TOKEN_APP')
user_id = os.getenv('VK_ID')

# Авторизация через токен пользователя (для получения данных)
vk_user_session = vk_api.VkApi(token=access_token_user)
vk_user = vk_user_session.get_api()

# Авторизация через токен группы (для бота)
vk_bot_session = vk_api.VkApi(token=access_token_bot)
vk_bot = vk_bot_session.get_api()
longpoll = VkLongPoll(vk_bot_session)

# Словарь для хранения последнего показанного кандидата для каждого пользователя
user_last_candidate = {}

def create_keyboard():
    """
    Создает клавиатуру для взаимодействия пользователя с ботом.

    Returns:
        str: JSON-код клавиатуры для VK API.
    """
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("Следующий", VkKeyboardColor.PRIMARY)
    keyboard.add_button("В избранное", VkKeyboardColor.POSITIVE)
    keyboard.add_button("В черный список", VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("Список избранных", VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def send_message(user_id: int, message: str, attachment: str = None, keyboard: str = None):
    """
    Отправляет сообщение пользователю VK с опциональной клавиатурой и вложениями.

    Args:
        user_id (int): VK ID пользователя.
        message (str): Текст сообщения.
        attachment (str, optional): Строка с фотографиями или медиа.
        keyboard (str, optional): JSON-код клавиатуры VK.
    """
    vk_bot.messages.send(
        user_id=user_id,
        message=message,
        random_id=get_random_id(),
        attachment=attachment,
        keyboard=keyboard
    )

def send_user_info(user_id: int, first_name: str, last_name: str, vk_link: str, photos: list[str]):
    """
    Отправляет пользователю информацию о кандидате.

    Args:
        user_id (int): VK ID пользователя.
        first_name (str): Имя кандидата.
        last_name (str): Фамилия кандидата.
        vk_link (str): Ссылка на профиль кандидата.
        photos (list[str]): Список фотографий кандидата.
    """
    name = f"{first_name} {last_name}"
    profile_link = vk_link
    send_message(user_id, f"Имя: {name}\nСсылка на профиль: {profile_link}",
                 attachment=",".join([p for p in photos if p]),
                 keyboard=create_keyboard())

def start_bot():
    """
    Основной цикл бота VK LongPoll.

    Обрабатывает события новых сообщений, добавляет пользователей в базу,
    отвечает на команды пользователя и отправляет кандидатов с фото.
    """
    print("Бот запущен...")
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.user_id
            text = event.text.lower()

            # Добавляем пользователя в БД, если его еще нет
            add_user_to_db(user_id)

            if text == "привет":
                send_message(user_id,
                             "Привет! Я помогу тебе найти людей для знакомства.\n"
                             "Используй кнопки ниже для взаимодействия.",
                             keyboard=create_keyboard())

            elif text == "следующий":
                last_id = user_last_candidate.get(user_id)
                candidate = get_next_candidate_from_db(user_id, last_id)
                if candidate:
                    user_last_candidate[user_id] = candidate[0]  # id кандидата
                    send_user_info(user_id, candidate[1], candidate[2],
                                   candidate[3], candidate[4])
                else:
                    send_message(user_id, "Больше кандидатов нет.")

            elif text == "в избранное":
                last_id = user_last_candidate.get(user_id)
                if last_id:
                    add_to_status(user_id, last_id, "") # Нужно добавить статус
                    send_message(user_id, "Пользователь добавлен в избранное!")
                else:
                    send_message(user_id, "Сначала выберите кандидата.")

            elif text == "в черный список":
                last_id = user_last_candidate.get(user_id)
                if last_id:
                    add_to_status(user_id, last_id, "") # Нужно добавить статус
                    send_message(user_id, "Пользователь добавлен в черный список!")
                else:
                    send_message(user_id, "Сначала выберите кандидата.")

            elif text == "список избранных":
                favorites = get_favorites(user_id)
                if favorites:
                    message = "\n".join([f"{idx+1}. {f[0]} {f[1]} — {f[2]}"
                                         for idx, f in enumerate(favorites)])
                else:
                    message = "Список избранных пуст."
                send_message(user_id, message)

            else:
                send_message(user_id, "Не понимаю команду. Используй кнопки для взаимодействия.")
