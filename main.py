# Замени старую функцию login_via_qr() на эту:
async def login_via_qr():
    qr_login = await client.qr_login()
    logging.warning("🔑 Запущен процесс авторизации через QR-код...")
    
    # Создаем сразу стартовую ссылку
    qr_url = qr_login.url
    api_qr_show = f"https://qrserver.com{qr_url}"
    
    # Отправляем ВСЁ в одном сообщении, чтобы ничего не терялось
    try:
        msg = await bot.send_message(
            chat_id=config.ADMIN_ID,
            text="⚠️ <b>Юзербот не авторизован!</b>\n\n"
                 "Чтобы запустить парсер, отсканируй этот QR-код со своего второго аккаунта:\n"
                 "1. Открой Telegram на телефоне\n"
                 "2. Настройки -> Устройства -> Подключить устройство\n\n"
                 "👇 <b>НАЖМИ НА ССЫЛКУ НИЖЕ, ЧТОБЫ ОТКРЫТЬ QR-КОД:</b>\n"
                  f"👉 <a href='{api_qr_show}'>КЛИКНИ СЮДА ДЛЯ СКАНИРОВАНИЯ</a>",
            parse_mode="HTML",
            disable_web_page_preview=False
        )
    except Exception as e:
        logging.error(f"Не удалось отправить пуш админу: {e}")
        return

    # Каждые 10 секунд просто обновляем ссылку в этом же сообщении, без удаления
    while not qr_login.is_logged_in:
        try:
            await asyncio.sleep(10)
            await qr_login.recreate()
            qr_url = qr_login.url
            api_qr_show = f"https://qrserver.com{qr_url}"
            
            await bot.edit_message_text(
                chat_id=config.ADMIN_ID,
                message_id=msg.message_id,
                text="⚠️ <b>Юзербот не авторизован!</b>\n\n"
                     "Чтобы запустить парсер, отсканируй этот QR-код со своего второго аккаунта:\n"
                     "1. Открой Telegram на телефоне\n"
                     "2. Настройки -> Устройства -> Подключить устройство\n\n"
                     "👇 <b>[ССЫЛКА ОБНОВЛЕНА] НАЖМИ СЮДА:</b>\n"
                     f"👉 <a href='{api_qr_show}'>КЛИКНИ СЮДА ДЛЯ СКАНИРОВАНИЯ</a>",
                parse_mode="HTML",
                disable_web_page_preview=False
            )
        except:
            break

    logging.info("🎉 УРА! Авторизация через QR успешно пройдена!")
    await bot.send_message(chat_id=config.ADMIN_ID, text="🎉 <b>Юзербот успешно вошел в аккаунт! Парсинг чатов запущен.</b>")
