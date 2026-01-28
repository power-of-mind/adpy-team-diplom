import os
import vk_api

from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from dotenv import load_dotenv

load_dotenv()

access_token_bot = os.getenv('TOKEN_BOT')
access_token_user = os.getenv('TOKEN_APP')
user_id = os.getenv('VK_ID')

vk_user_session = vk_api.VkApi(token=access_token_user)
vk_user = vk_user_session.get_api()

# Получение данных о пользователе
def get_user_info(user_id):
    user_info = vk_user.users.get(user_ids=user_id, fields="bdate,sex,city")[0]
    return user_info

# Получение 3 самых популярных фотографий пользователя
def get_top3_photos_by_likes(user_id):
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
        max_size = max(photo['sizes'], key=lambda s: s['width'] * s['height'])
        attachments.append(f"photo{photo['owner_id']}_{photo['id']}")  # Формат для attachment

    return attachments