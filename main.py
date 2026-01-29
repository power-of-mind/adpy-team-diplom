"""
Главный модуль интеграционного VK Dating Bot.

Отвечает за:
- запуск бота и прослушивание событий через VK LongPoll;
- обработку сообщений пользователей;
- показ кандидатов и управление их статусами (избранное / черный список);
- интеграцию с базой данных (создание таблиц, добавление пользователей, получение кандидатов);
- хранение состояния последнего показанного кандидата для каждого пользователя.

Использует функции из vk_bot_modules и db_modules.
"""


from vk_bot_modules import (
    longpoll,
    VkEventType,
    send_message,
    create_keyboard,
    user_last_candidate  # используем глобальное состояние из модуля
)
from db_modules import (
    add_user_to_db,
    get_next_candidate_from_db,
    add_to_status,
    get_favorites,
    create_tables
)

def safe_add_to_status(vk_user_id: int, candidate_profile_id: int, status: str):
    """
    Добавляет статус (like/dislike) кандидату для пользователя, безопасно преобразуя
    внутренний ID профиля в VK ID.

    Обертка над функции add_to_status из db_modules.

    Args:
        vk_user_id (int): VK ID пользователя.
        candidate_profile_id (int): Внутренний ID кандидата в таблице vk_profiles.
        status (str): Статус для записи, "like" или "dislike".

    Raises:
        ValueError: Если профиль с указанным ID не найден в БД.
    """
    from db_connection import create_db_connection
    with create_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT vk_id FROM vk_profiles WHERE id = %s", (candidate_profile_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Профиль с id={candidate_profile_id} не найден")
            vk_candidate_id = row[0]
    # Вызываем оригинальную функцию, которая ожидает VK ID кандидата как last_id
    add_to_status(vk_user_id, vk_candidate_id, status)

def handle_message(event):
    """
    Обрабатывает входящее сообщение от пользователя VK.

    В зависимости от текста сообщения выполняет:
    - Приветствие и отправку клавиатуры;
    - Показ следующего кандидата;
    - Добавление кандидата в избранное или черный список;
    - Вывод списка избранных;
    - Сообщение о неизвестной команде.

    Args:
        event (VkEventType): Событие нового сообщения от VK LongPoll.
    """
    user_id = event.user_id
    text = event.text.strip().lower()

    # Гарантируем, что пользователь в БД
    try:
        add_user_to_db(user_id)
    except Exception as e:
        send_message(user_id, "Ошибка при регистрации. Попробуйте позже.")
        print(f"Ошибка регистрации пользователя {user_id}: {e}")
        return

    if text in ("привет", "начать", "start"):
        send_message(
            user_id,
            "Привет! Я помогу тебе найти людей для знакомства.\n"
            "Используй кнопки ниже для взаимодействия.",
            keyboard=create_keyboard()
        )

    elif text == "следующий":
        last_id = user_last_candidate.get(user_id)
        candidate = get_next_candidate_from_db(user_id, last_id)
        if candidate:
            # candidate — это СЛОВАРЬ (согласно реальному db_modules.py)
            user_last_candidate[user_id] = candidate["id"]  # сохраняем внутренний id
            name = f"{candidate['first_name']} {candidate['last_name']}"
            link = candidate["vk_link"]
            photos = ",".join(candidate["photos"])
            send_message(
                user_id,
                f"Имя: {name}\nСсылка на профиль: {link}",
                attachment=photos,
                keyboard=create_keyboard()
            )
        else:
            send_message(user_id, "Больше кандидатов нет.")

    elif text == "в избранное":
        last_id = user_last_candidate.get(user_id)  # это внутренний id из vk_profiles.id
        if last_id:
            try:
                safe_add_to_status(user_id, last_id, "like")
                send_message(user_id, "Пользователь добавлен в избранное!")
            except Exception as e:
                send_message(user_id, "Не удалось добавить в избранное.")
                print(f"Ошибка like: {e}")
        else:
            send_message(user_id, "Сначала выберите кандидата.")

    elif text == "в черный список":
        last_id = user_last_candidate.get(user_id)
        if last_id:
            try:
                safe_add_to_status(user_id, last_id, "dislike")
                send_message(user_id, "Пользователь добавлен в черный список!")
            except Exception as e:
                send_message(user_id, "Не удалось добавить в чёрный список.")
                print(f"Ошибка dislike: {e}")
        else:
            send_message(user_id, "Сначала выберите кандидата.")

    elif text == "список избранных":
        favorites = get_favorites(user_id)
        if favorites:
            message = "\n".join([
                f"{idx+1}. {f[0]} {f[1]} — {f[2]}"
                for idx, f in enumerate(favorites)
            ])
        else:
            message = "Список избранных пуст."
        send_message(user_id, message)

    else:
        send_message(
            user_id,
            "Не понимаю команду. Используй кнопки для взаимодействия.",
            keyboard=create_keyboard()
        )

def main():
    """
    Главная функция запуска интеграционного бота.

    Выполняет:
    - Создание таблиц в базе данных;
    - Прослушивание новых сообщений через VK LongPoll;
    - Вызов handle_message для обработки каждого сообщения.
    """
    print("Запуск интеграционного бота...")
    create_tables()  # создаём таблицы при старте
    print("Бот запущен и ожидает сообщений...")
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            handle_message(event)

if __name__ == "__main__":
    main()