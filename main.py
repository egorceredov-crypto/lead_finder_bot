import asyncio
import logging
import hashlib
from datetime import datetime

from aiogram import Bot, Dispatcher
from telethon import TelegramClient, events

import config
import database as db
from handlers import user, filters_menu, admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()
dp.include_routers(user.router, filters_menu.router, admin.router)

# Инициализируем Юзербота через Telethon
client = TelegramClient('userbot_session', config.API_ID, config.API_HASH)

# Главный обработчик сообщений из бьюти-чатов
@client.on(events.NewMessage(incoming=True))
async def handle_new_message(event):
    if not event.is_channel and not event.is_group:
        return
    if not event.text:
        return

    tracked_chats = await db.get_tracked_chats()
    if not tracked_chats:
        return

    current_chat_id = event.chat_id
    chat_properties = await event.get_chat()
    current_username = chat_properties.username.lower() if getattr(chat_properties, 'username', None) else ""

    is_allowed = False
    for chat_id, username, _ in tracked_chats:
        clean_db_username = username.replace("@", "").lower().strip()
        if str(chat_id) in str(current_chat_id) or (current_username and current_username == clean_db_username):
            is_allowed = True
            break

    if not is_allowed:
        return

    text = event.text

    # Фильтр дубликатов
    msg_hash = hashlib.md5(text.strip().lower().encode('utf-8')).hexdigest()
    if await db.is_duplicate_msg(msg_hash):
        return

    # Ищем мастеров, чьи ключи совпали
    matched_users = await db.get_matching_users(text)
    if not matched_users:
        return

    if current_username:
        msg_link = f"https://t.me{current_username}/{event.id}"
    else:
        clean_id = str(current_chat_id).replace("-100", "")
        msg_link = f"https://t.mec/{clean_id}/{event.id}"

    chat_title = getattr(chat_properties, 'title', 'Целевой чат')
    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y")
    time_str = now.strftime("%H:%M")

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
            await bot.send_message(chat_id=user_id, text=notification_text, parse_mode="HTML", disable_web_page_preview=True)
        except Exception as e:
            logging.error(f"Ошибка отправки пользователю {user_id}: {e}")

# Цикл вступления в новые чаты из админки
async def auto_join_chats_loop():
    while True:
        try:
            tracked_chats = await db.get_tracked_chats()
            for chat_id, username, title in tracked_chats:
                if chat_id > 0 or "Чат:" in title:
                    clean_username = username.replace("@", "").strip()
                    try:
                        logging.info(f"Юзербот заходит в чат: {clean_username}")
                        actual_chat = await client.join_chat(clean_username)
                        await db.remove_tracked_chat(chat_id)
                        await db.add_tracked_chat(actual_chat.id, username, actual_chat.title)
                        logging.info(f"Юзербот успешно добавил чат: {actual_chat.title}")
                    except Exception as e:
                        logging.error(f"Ошибка вступления в {clean_username}: {e}")
        except Exception as e:
            logging.error(f"Ошибка в цикле проверки чатов: {e}")
        await asyncio.sleep(20)

# Функция генерации QR-кода для входа без консоли
async def login_via_qr():
    qr_login = await client.qr_login()
    logging.warning("🔑 Запущен процесс авторизации через QR-код...")
    
    # Отправляем админу сообщение, что нужно зайти по QR
    try:
        await bot.send_message(
            chat_id=config.ADMIN_ID,
            text="⚠️ <b>Юзербот не авторизован!</b>\n\n"
                 "Чтобы запустить парсер, отсканируй этот QR-код со своего второго аккаунта:\n"
                 "1. Открой Telegram на телефоне\n"
                 "2. Настройки -> Устройства -> Подключить устройство\n"
                 "3. Отсканируй QR по ссылке ниже 👇"
        )
    except Exception as e:
        logging.error(f"Не удалось отправить пуш админу: {e}")

    while not qr_login.is_logged_in:
        # Генерируем ссылку на QR (Телеграм обновляет её каждые пару секунд для безопасности)
        qr_url = qr_login.url
        # Создаем удобную кнопку-ссылку для сканирования через любой генератор QR
        api_qr_show = f"https://qrserver.com{qr_url}"
        
        try:
            msg = await bot.send_message(
                chat_id=config.ADMIN_ID,
                text=f"⏳ <b>Ссылка на QR-код обновлена!</b>\n\n"
                     f"👉 <a href='{api_qr_show}'>КЛИКНИ СЮДА ЧТОБЫ ОТКРЫТЬ QR-КОД</a>\n\n"
                     f"У тебя есть 10 секунд на сканирование, пока ссылка не обновилась!",
                parse_mode="HTML"
            )
            # Ждем немного и удаляем старую ссылку, чтобы не спамить чат
            await asyncio.sleep(8)
            await bot.delete_message(chat_id=config.ADMIN_ID, message_id=msg.message_id)
        except:
            await asyncio.sleep(8)
            
        try:
            await qr_login.recreate()
        except:
            break

    logging.info("🎉 УРА! Авторизация через QR успешно пройдена!")
    await bot.send_message(chat_id=config.ADMIN_ID, text="🎉 <b>Юзербот успешно вошел в аккаунт! Парсинг чатов запущен.</b>")

async def main():
    await db.init_db()
    logging.info("База данных успешно инициализирована.")

    await client.connect()
    
    # Если юзербот не вошел — запускаем наш умный QR-вход
    if not await client.is_user_authorized():
        # Запускаем aiogram параллельно, чтобы он мог отправить нам QR в чат
        asyncio.create_task(login_via_qr())
        asyncio.create_task(dp.start_polling(bot))
        # Держим Telethon активным, пока идет сканирование
        while not await client.is_user_authorized():
            await asyncio.sleep(2)
            
    # Если залогинен — запускаем обычную работу
    logging.info("Юзербот на Telethon успешно запущен!")
    asyncio.create_task(auto_join_chats_loop())

    logging.info("Интерфейсный бот на aiogram запущен в штатном режиме.")
    try:
        # Проверяем, не запущен ли уже поллинг
        if not dp.storage: 
            await dp.start_polling(bot)
        else:
            while True: await asyncio.sleep(3600)
    finally:
        await client.disconnect()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
