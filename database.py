import aiosqlite
from config import DB_URL


async def init_db():
    async with aiosqlite.connect(DB_URL.replace("sqlite+aiosqlite:///", "")) as db:
        # Таблица пользователей и их настроек
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                sub_expires DATETIME,
                geo_mode TEXT DEFAULT 'all',
                spam_filter INTEGER DEFAULT 1
            )
        """)
        # Таблица ключевых слов пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                word TEXT,
                UNIQUE(user_id, word)
            )
        """)
        # Таблица стоп-слов пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS stop_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                word TEXT,
                UNIQUE(user_id, word)
            )
        """)
        # Таблица чатов, которые добавляет только админ
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tracked_chats (
                chat_id INTEGER PRIMARY KEY,
                chat_username TEXT,
                chat_title TEXT
            )
        """)
        # Таблица истории сообщений (для защиты от дублей)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS msg_history (
                msg_hash TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


# --- ФУНКЦИИ ДЛЯ АДМИНА ---
async def add_tracked_chat(chat_id: int, username: str, title: str):
    async with aiosqlite.connect(DB_URL.replace("sqlite+aiosqlite:///", "")) as db:
        await db.execute(
            "INSERT OR IGNORE INTO tracked_chats (chat_id, chat_username, chat_title) VALUES (?, ?, ?)",
            (chat_id, username, title)
        )
        await db.commit()


async def get_tracked_chats():
    async with aiosqlite.connect(DB_URL.replace("sqlite+aiosqlite:///", "")) as db:
        async with db.execute("SELECT chat_id, chat_username, chat_title FROM tracked_chats") as cursor:
            return await cursor.fetchall()


async def remove_tracked_chat(chat_id: int):
    async with aiosqlite.connect(DB_URL.replace("sqlite+aiosqlite:///", "")) as db:
        await db.execute("DELETE FROM tracked_chats WHERE chat_id = ?", (chat_id,))
        await db.commit()


# --- ФУНКЦИИ ДЛЯ ЮЗЕРОВ ---
async def get_user_profile(user_id: int):
    async with aiosqlite.connect(DB_URL.replace("sqlite+aiosqlite:///", "")) as db:
        # Проверяем или создаем запись юзера
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()
        async with db.execute("SELECT sub_expires, geo_mode, spam_filter FROM users WHERE user_id = ?",
                              (user_id,)) as cursor:
            return await cursor.fetchone()


async def update_user_geo(user_id: int, geo_mode: str):
    async with aiosqlite.connect(DB_URL.replace("sqlite+aiosqlite:///", "")) as db:
        await db.execute("UPDATE users SET geo_mode = ? WHERE user_id = ?", (geo_mode, user_id))
        await db.commit()


async def toggle_spam_filter(user_id: int, current_status: int):
    new_status = 0 if current_status == 1 else 1
    async with aiosqlite.connect(DB_URL.replace("sqlite+aiosqlite:///", "")) as db:
        await db.execute("UPDATE users SET spam_filter = ? WHERE user_id = ?", (new_status, user_id))
        await db.commit()
        return new_status


async def add_keyword(user_id: int, word: str):
    async with aiosqlite.connect(DB_URL.replace("sqlite+aiosqlite:///", "")) as db:
        try:
            await db.execute("INSERT INTO keywords (user_id, word) VALUES (?, ?)", (user_id, word.lower().strip()))
            await db.commit()
            return True
        except:
            return False


async def get_keywords(user_id: int):
    async with aiosqlite.connect(DB_URL.replace("sqlite+aiosqlite:///", "")) as db:
        async with db.execute("SELECT word FROM keywords WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]


async def delete_keyword(user_id: int, word: str):
    async with aiosqlite.connect(DB_URL.replace("sqlite+aiosqlite:///", "")) as db:
        await db.execute("DELETE FROM keywords WHERE user_id = ? AND word = ?", (user_id, word.lower().strip()))
        await db.commit()


# Функции для стоп-слов
async def add_stop_word(user_id: int, word: str):
    async with aiosqlite.connect(DB_URL.replace("sqlite+aiosqlite:///", "")) as db:
        try:
            await db.execute("INSERT INTO stop_words (user_id, word) VALUES (?, ?)", (user_id, word.lower().strip()))
            await db.commit()
            return True
        except:
            return False


async def get_stop_words(user_id: int):
    async with aiosqlite.connect(DB_URL.replace("sqlite+aiosqlite:///", "")) as db:
        async with db.execute("SELECT word FROM stop_words WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]


async def clear_stop_words(user_id: int):
    async with aiosqlite.connect(DB_URL.replace("sqlite+aiosqlite:///", "")) as db:
        await db.execute("DELETE FROM stop_words WHERE user_id = ?", (user_id,))
        await db.commit()


# --- ФУНКЦИЯ ДЛЯ КРОСС-ПАРСИНГА ОДНИМ ЗАПРОСОМ ---
async def get_matching_users(text: str):
    """Возвращает список user_id, чьи ключевые слова совпали, с учетом ГЕО и стоп-слов"""
    text_lower = text.lower()
    matched_users = []

    async with aiosqlite.connect(DB_URL.replace("sqlite+aiosqlite:///", "")) as db:
        # Получаем всех активных пользователей (для теста берем всех, фильтр подписки можно накрутить позже)
        async with db.execute("SELECT user_id, geo_mode, spam_filter FROM users") as cursor:
            users = await cursor.fetchall()

        for user_id, geo_mode, spam_filter in users:
            # 1. Проверяем стоп-слова
            async with db.execute("SELECT word FROM stop_words WHERE user_id = ?", (user_id,)) as cur:
                stops = [r[0] for r in await cur.fetchall()]
            if any(stop in text_lower for stop in stops):
                continue

            # 2. Проверяем ГЕО-режим (простая текстовая фильтрация локаций)
            if geo_mode == 'msk' and not any(x in text_lower for x in ['москва', 'мск', 'питер', 'спб']):
                # Если у юзера режим 'msk' (Москва), но в тексте нет привязки
                if not any(x in text_lower for x in ['москва', 'мск']): continue
            if geo_mode == 'spb' and not any(x in text_lower for x in ['питер', 'спб']):
                continue

            # 3. Проверяем ключевые слова
            async with db.execute("SELECT word FROM keywords WHERE user_id = ?", (user_id,)) as cur:
                keywords = [r[0] for r in await cur.fetchall()]

            if any(kw in text_lower for kw in keywords):
                matched_users.append(user_id)

    return matched_users


async def is_duplicate_msg(msg_hash: str) -> bool:
    async with aiosqlite.connect(DB_URL.replace("sqlite+aiosqlite:///", "")) as db:
        try:
            await db.execute("INSERT INTO msg_history (msg_hash) VALUES (?)", (msg_hash,))
            await db.commit()
            return False  # Не дубликат, успешно записали
        except:
            return True  # Дубликат, такой хэш уже существует
