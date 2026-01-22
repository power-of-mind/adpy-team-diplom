from datetime import datetime, timezone

from psycopg2.extras import RealDictCursor

from db_connection import create_db_connection
from vk_bot_modules import get_user_info, get_top3_photos_by_likes


def create_tables():
    """
    Создаёт таблицы в базе данных
    """
    with create_db_connection() as conn:
        with conn.cursor() as cur:
            # Создаем таблицу с анкетами vk_profiles
            cur.execute("""
                CREATE TABLE IF NOT EXISTS vk_profiles (
                    id BIGSERIAL PRIMARY KEY,
                    vk_id BIGINT UNIQUE NOT NULL,
                    first_name TEXT,
                    last_name TEXT,
                    sex SMALLINT,
                    city_id INTEGER,
                    birth_date TEXT,
                    profile_url TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)

            # Создаем таблицу пользователей users
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    vk_user_id BIGINT UNIQUE NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    update_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    current_profile_id BIGINT,
                    CONSTRAINT fk_users_current_profile
                        FOREIGN KEY (current_profile_id)
                        REFERENCES vk_profiles(id)
                        ON DELETE SET NULL
                        ON UPDATE CASCADE
                );
            """)

            # Создаем таблицу с фотографиями vk_photos
            cur.execute("""
                CREATE TABLE IF NOT EXISTS vk_photos (
                    id BIGSERIAL PRIMARY KEY,
                    vk_profiles_id BIGINT NOT NULL,
                    photo_id TEXT NOT NULL,
                    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT fk_vkphotos_profile
                        FOREIGN KEY (vk_profiles_id)
                        REFERENCES vk_profiles(id)
                        ON DELETE CASCADE
                        ON UPDATE CASCADE,
                    UNIQUE (vk_profiles_id, photo_id)
                );
            """)

            # Создаем таблицу связей like_dislike
            cur.execute("""
                CREATE TABLE IF NOT EXISTS like_dislike (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    vk_profiles_id BIGINT NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    CONSTRAINT fk_ld_user
                        FOREIGN KEY (user_id)
                        REFERENCES users (id)
                        ON DELETE CASCADE
                        ON UPDATE CASCADE,
                    CONSTRAINT fk_ld_vkprofile
                        FOREIGN KEY (vk_profiles_id)
                        REFERENCES vk_profiles (id)
                        ON DELETE CASCADE
                        ON UPDATE CASCADE,
                    UNIQUE (user_id, vk_profiles_id)
                );
            """)

            conn.commit()

def add_user_to_db(user_id):
    """
    Добавляет пользователя в БД, если его еще нет.
    user_id: ID пользователя ВК (int).
    Использует get_user_info(user_id) и get_top3_photos_by_likes(user_id).
    Возвращает id записи в users
    """
    user_info = get_user_info(user_id)
    if not user_info:
        raise ValueError(f"Пользователь {user_id} не найден")

    # Вытаскиваем поля из user_info
    vk_id = int(user_info.get('id') or user_id)
    first_name = user_info.get('first_name')
    last_name = user_info.get('last_name')
    sex = user_info.get('sex')
    city = user_info.get('city') or {}
    city_id = city.get('id') if isinstance(city, dict) else None
    birth_date = user_info.get('bdate')
    profile_url = f"https://vk.com/id{vk_id}"

    top_photos = get_top3_photos_by_likes(user_id) or []

    now = datetime.now(timezone.utc)

    with create_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1) Вставить или обновить vk_profiles (UPSERT по vk_id)
            cur.execute("""
                INSERT INTO vk_profiles (vk_id, first_name, last_name, sex, city_id, birth_date, profile_url, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (vk_id) DO UPDATE
                    SET first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        sex = EXCLUDED.sex,
                        city_id = EXCLUDED.city_id,
                        birth_date = EXCLUDED.birth_date,
                        profile_url = EXCLUDED.profile_url,
                        updated_at = EXCLUDED.updated_at
                RETURNING id;
            """, (vk_id, first_name, last_name, sex, city_id, birth_date, profile_url, now, now))

            vk_profile_row = cur.fetchone()
            if not vk_profile_row:
                raise RuntimeError("Не удалось вставить/обновить vk_profiles")
            vk_profiles_id = vk_profile_row['id']

            # 2) Вставить пользователя в users если нет
            # проверяем наличие пользователя по vk_user_id
            cur.execute("SELECT id, current_profile_id FROM users WHERE vk_user_id = %s;", (vk_id,))
            user_row = cur.fetchone()
            if user_row:
                user_db_id = user_row['id']
                # обновим current_profile_id и update_at (если нужно)
                cur.execute("""
                        UPDATE users SET current_profile_id = %s, update_at = %s WHERE id = %s;
                    """, (vk_profiles_id, now, user_db_id))
            else:
                cur.execute("""
                        INSERT INTO users (vk_user_id, created_at, update_at, current_profile_id)
                        VALUES (%s,%s,%s,%s) RETURNING id;
                    """, (vk_id, now, now, vk_profiles_id))
                user_db_id = cur.fetchone()['id']

            # 3) Сохранить топ-3 фото
            for attachment in top_photos:
                key = attachment
                if attachment.startswith('photo'):
                    key = attachment[5:]
                # проверим, есть ли уже такое фото для данного vk_profiles_id
                cur.execute("""
                        SELECT id FROM vk_photos WHERE vk_profiles_id = %s AND photo_id = %s;
                    """, (vk_profiles_id, key))
                if cur.fetchone():
                    continue
                cur.execute("""
                        INSERT INTO vk_photos (vk_profiles_id, photo_id, fetched_at)
                        VALUES (%s,%s,%s,%s);
                    """, (vk_profiles_id, key, now))

            conn.commit()

    return user_db_id

def get_next_candidate_from_db(user_id, last_id=None):
    """
    Берет следующего кандидата из БД, исключая профили из like_dislike данного пользователя.
    Возвращает dict или None, если кандидат не найден.
    """
    with create_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1) Получаем внутренний users.id по vk_user_id
            cur.execute("SELECT id FROM users WHERE vk_user_id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                return None

            local_user_id = row['id']

            # 2) Формируем список исключаемых анкет (like/dislike)
            cur.execute("""
                SELECT vk_profiles_id
                FROM like_dislike
                WHERE user_id = %s
            """, (local_user_id,))
            excluded = {r['vk_profiles_id'] for r in cur.fetchall()}

            # 3) Исключаем текущий профиль пользователя
            cur.execute("SELECT current_profile_id FROM users WHERE id = %s", (local_user_id,))
            row = cur.fetchone()
            if row and row.get('current_profile_id'):
                excluded.add(row['current_profile_id'])

            # 4) Строим WHERE-условия
            params = []
            where_clauses = []

            if excluded:
                where_clauses.append("id NOT IN %s")
                params.append(tuple(excluded))

            if last_id is not None:
                where_clauses.append("id > %s")
                params.append(last_id)

            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)

            qry = f"""
                SELECT id, vk_id, first_name, last_name, profile_url
                FROM vk_profiles
                {where_sql}
                ORDER BY id ASC
                LIMIT 1
            """

            cur.execute(qry, tuple(params))
            candidate = cur.fetchone()
            if not candidate:
                return None

            vk_profiles_id = candidate['id']

            # 5) Получаем до 3 фотографий
            cur.execute("""
                SELECT photo_id
                FROM vk_photos
                WHERE vk_profiles_id = %s
                ORDER BY fetched_at DESC
                LIMIT 3
            """, (vk_profiles_id,))
            photos_rows = cur.fetchall()
            photos = []
            for r in photos_rows:
                pid = r['photo_id']
                if pid and not pid.startswith('photo'):
                    photos.append(f"photo{pid}")
                elif pid:
                    photos.append(pid)

            result = {
                "id": vk_profiles_id,
                "first_name": candidate.get('first_name'),
                "last_name": candidate.get('last_name'),
                "vk_link": candidate.get('profile_url') or f"https://vk.com/id{candidate.get('vk_id')}",
                "photos": photos
            }

            return result

def add_to_status(user_id, last_id, status):
    """
    Добавляет или обновляет статус (like/dislike) для кандидата last_id от пользователя user_id.
    user_id: VK id пользователя.
    last_id: VK id кандидата в таблице vk_profiles.
    status: 'like'|'dislike'.
    """

    if not user_id:
        raise ValueError("Необходимо передать user_id")
    if not last_id:
        raise ValueError("Необходимо передать last_id")
    if not status:
        raise ValueError("Необходимо передать status")

    now = datetime.now(timezone.utc)

    with create_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1) Получаем локальный users.id по vk_user_id. Если пользователя нет — создаём
            cur.execute("SELECT id FROM users WHERE vk_user_id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                try:
                    add_user_to_db(user_id)
                except Exception:
                    cur.execute(
                        "INSERT INTO users (vk_user_id, created_at, update_at) VALUES (%s, %s, %s) RETURNING id",
                        (user_id, now, now)
                    )
                    new = cur.fetchone()
                    if not new:
                        conn.rollback()
                        raise RuntimeError("Не удалось создать пользователя")
                    local_user_id = new['id']
                else:
                    cur.execute("SELECT id FROM users WHERE vk_user_id = %s", (user_id,))
                    new = cur.fetchone()
                    if not new:
                        conn.rollback()
                        raise RuntimeError("Пользователь создан, но не найден")
                    local_user_id = new['id']
            else:
                local_user_id = row['id']

            # 2) Находим внутренний vk_profiles.id по vk_id = last_id
            cur.execute("SELECT id FROM vk_profiles WHERE vk_id = %s", (last_id,))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                raise ValueError(f"vk_profiles with vk_id={last_id} not found")
            vk_profiles_id = row['id']

            # 3) UPSERT в like_dislike
            cur.execute("""
                INSERT INTO like_dislike (user_id, vk_profiles_id, status, added_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, vk_profiles_id) DO UPDATE
                    SET status = EXCLUDED.status,
                        added_at = EXCLUDED.added_at
                RETURNING id, status;
            """, (local_user_id, vk_profiles_id, status, now))
            ld_row = cur.fetchone()
            if not ld_row:
                conn.rollback()
                raise RuntimeError("Не удалось вставить/обновить запись в like_dislike")

            # 4) Обновляем users.current_profile_id и update_at
            cur.execute("""
                UPDATE users
                SET current_profile_id = %s, update_at = %s
                WHERE id = %s
            """, (vk_profiles_id, now, local_user_id))

            conn.commit()

            return {
                "ok": True,
                "user_id": local_user_id,
                "vk_profiles_id": vk_profiles_id,
                "like_dislike_id": ld_row['id'],
                "status": ld_row['status']
            }

def get_favorites(user_id):
    """
    Возвращает список избранных профилей для пользователя user_id.
    Формат результата: [(first_name, last_name, profile_url), ...]
    Если пользователь не найден — возвращает пустой список.
    """
    if not user_id:
        return []

    with create_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1) Получаем локальный users.id по vk_user_id
            cur.execute("SELECT id FROM users WHERE vk_user_id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                return []

            local_user_id = row['id']

            # 2) Выбираем профили, которые пользователь пометил как 'like'
            cur.execute("""
                SELECT p.first_name, p.last_name, COALESCE(p.profile_url, ('https://vk.com/id' || p.vk_id)) AS profile_url
                FROM like_dislike ld
                JOIN vk_profiles p ON p.id = ld.vk_profiles_id
                WHERE ld.user_id = %s
                  AND ld.status = %s
                ORDER BY ld.added_at DESC
            """, (local_user_id, 'like'))

            rows = cur.fetchall()

            # 3) Конвертируем в список кортежей (first_name, last_name, profile_url)
            favorites = []
            for r in rows:
                first_name = r.get('first_name') or ''
                last_name = r.get('last_name') or ''
                url = r.get('profile_url') or ''
                favorites.append((first_name, last_name, url))

            return favorites
