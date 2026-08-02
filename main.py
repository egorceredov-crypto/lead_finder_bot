import asyncio
import logging
import hashlib
from datetime import datetime

from aiogram import Bot, Dispatcher
from telethon import TelegramClient, events

import config
import database as db
from handlers import user, filters_menu, admin

# Настройка красивого логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Инициализируем интерфейсного бота (aiogram)
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# Подключаем готовые менюшки
dp.include_routers(user.router, filters_menu.router, admin.router)

# Инициализируем Юзербота через стабильный Telethon
client = TelegramClient('userbot_session', config.API_ID, config.API_HASH)


# Главный обработчик сообщений из чатов
@client.on(events.NewMessage(incoming=True))
async def handle_new_message(event):
    # Проверяем, что сообщение из группы/канала и есть текст
    if not event.is_channel and not event.is_group:
        return
    if not event.text:
        return

    # 1. Проверяем, добавлен ли этот чат админом
    tracked_chats = await db.get_tracked_chats()
    if not tracked_chats:
        return

    current_chat_id = event.chat_id
    # Приводим username к единому виду для сверки
    chat_properties = await event.get_chat()
    current_username = chat_properties.username.lower() if getattr(chat_properties, 'username', None) else ""

    is_allowed = False
    for chat_id, username, _ in tracked_chats:
        clean_db_username = username.replace("@", "").lower().strip()
        # Telethon ID групп могут отличаться знаком минус, проверяем совпадение по цифрам или юзернейму
        if str(chat_id) in str(current_chat_id) or (current_username and current_username == clean_db_username):
            is_allowed = True
            break

    if not is_allowed:
        return

    text = event.text

    # 2. Жесткий фильтр дубликатов (защита от спама)
    msg_hash = hashlib.md5(text.strip().lower().encode('utf-8')).hexdigest()
    if await db.is_duplicate_msg(msg_hash):
        return

    # 3. Ищем мастеров, у которых совпали ключевые слова
    matched_users = await db.get_matching_users(text)
    if not matched_users:
        return

    # Формируем прямую ссылку на сообщение
    if current_username:
        msg_link = f"https://t.me{current_username}/{event.id}"
    else:
        # Для закрытых чатов
        clean_id = str(current_chat_id).replace("-100", "")
        msg_link = f"https://t.mec/{clean_id}/{event.id}"

    chat_title = getattr(chat_properties, 'title', 'Целевой чат')
    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y")
    time_str = now.strftime("%H:%M")

    # 4. Рассылаем уведомление мастерам в бота
    for user_id in matched_users:
        notification_text = (
            f"🔔 <b>Найдена новая заявка!</b>\n"
            f"──────────────────\n"
            f"📝 <b>Текст:</b> <i>{text}</i>\n\n"
            f"📍 <b>Чат:</b> {chat_title}\n"
            f"📅 <b>Дата:</b> {date_str} | ⏱ <b>Время:</b> {time_str}\n"
            f"──────────────────\n"
            f"🚀 <a href='{msg_link}'>ОТКРЫТЬ СООБЩЕНИЕ И НАПИСАТЬ</a>"
        )
        try:
            await bot.send_message(chat_id=user_id, text=notification_text, parse_mode="HTML",
                                   disable_web_page_preview=True)
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление {user_id}: {e}")


# Фоновый цикл для автоматического вступления юзербота в чаты из админки
async def auto_join_chats_loop():
    while True:
        try:
            tracked_chats = await db.get_tracked_chats()
            for chat_id, username, title in tracked_chats:
                if chat_id > 0 or "Чат:" in title:
                    clean_username = username.replace("@", "").strip()
                    try:
                        logging.info(f"Юзербот заходит в чат: {clean_username}")
                        # Пытаемся вступить в чат
                        actual_chat = await client.join_chat(clean_username)

                        # Обновляем данные чата на реальные
                        await db.remove_tracked_chat(chat_id)
                        await db.add_tracked_chat(actual_chat.id, username, actual_chat.title)
                        logging.info(f"Юзербот успешно добавил чат: {actual_chat.title}")
                    except Exception as e:
                        logging.error(f"Ошибка вступления в {clean_username}: {e}")
        except Exception as e:
            logging.error(f"Ошибка в цикле проверки чатов: {e}")
        await asyncio.sleep(20)


async def main():
    # Инициализируем таблицы базы данных
    await db.init_db()
    logging.info("База данных успешно инициализирована.")

    # Запуск клиента Telethon (он сам запросит телефон и код в консоли при первом запуске)
    await client.start()
    logging.info("Юзербот на Telethon успешно запущен!")

    # Включаем фоновую задачу авто-вступления
    asyncio.create_task(auto_join_chats_loop())

    # Запускаем интерфейсного бота
    logging.info("Интерфейсный бота на aiogram запущен.")
    try:
        await dp.start_polling(bot)
    finally:
        await client.disconnect()
        await bot.session.close()


if __name__ == "__main__":
    # Запускаем асинхронный движок
    asyncio.run(main())
