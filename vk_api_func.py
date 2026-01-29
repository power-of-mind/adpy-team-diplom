"""
Модуль для работы с VK API.

Функционал:
- Получение информации о пользователе (имя, дата рождения, пол, город).
- Получение 3 самых популярных фотографий пользователя по количеству лайков.

Использует токены для авторизации и получения данных о пользователях VK.
"""

import os
import vk_api

from dotenv import load_dotenv

load_dotenv()

access_token_bot = os.getenv('TOKEN_BOT')
access_token_user = os.getenv('TOKEN_APP')
user_id = os.getenv('VK_ID')

vk_user_session = vk_api.VkApi(token=access_token_user)
vk_user = vk_user_session.get_api()

def get_user_info(user_id: int) -> dict:
    """
    Получает информацию о пользователе VK.

    Args:
        user_id (int): VK ID пользователя.

    Returns:
        dict: Словарь с данными пользователя (id, first_name, last_name, sex, city, bdate и др.).
    """
    user_info = vk_user.users.get(user_ids=user_id, fields="bdate,sex,city")[0]
    return user_info

def get_top3_photos_by_likes(user_id: int) -> list[str]:
    """
    Получает 3 самых популярных фотографии пользователя VK по количеству лайков.

    Args:
        user_id (int): VK ID пользователя.

    Returns:
        list[str]: Список attachment-строк для VK API вида 'photo<owner_id>_<id>'.
    """
    photos = vk_user.photos.get(
        owner_id=user_id,
        album_id='profile',  # Альбом профиля
        extended=1,          # Включает лайки
        count=100            # Получаем 100 фото для выбора
    )

    # Сортируем по лайкам
    sorted_photos = sorted(
        photos['items'],
        key=lambda x: x['likes']['count'],
        reverse=True
    )[:3]

    attachments = []
    for photo in sorted_photos:
        attachments.append(f"photo{photo['owner_id']}_{photo['id']}")  # Формат для attachment

    return attachments