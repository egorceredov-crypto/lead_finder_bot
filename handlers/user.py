from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from config import ADMIN_ID, MAX_KEYWORDS

router = Router()


class Form(StatesGroup):
    waiting_for_keyword = State()
    waiting_for_stopword = State()
    waiting_for_delete_word = State()


def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Ключевые слова", callback_query_data="menu_keywords")],
        [InlineKeyboardButton(text="⚙️ Настройки поиска", callback_query_data="menu_filters")],
        [InlineKeyboardButton(text="👤 Личный кабинет", callback_query_data="menu_profile")]
    ])


@router.message(CommandStart())
async def cmd_start(message: Message):
    # Инициализируем профиль юзера в БД при первом старте
    await db.get_user_profile(message.from_user.id)

    text = (
        "💳 <b>Управление коммерческой подпиской LeadFinder:</b>\n\n"
        "Откройте полный доступ к потоку бьюти-заявок без лимитов "
        "на количество слов.\n\n"
        "💰 <b>Выберите подходящий тарифный план для покупки:</b>\n"
        "──────────────────\n"
        "🔥 <code>Безлимит на месяц</code> — <b>1490₽</b>\n"
        "⚡️ <code>Тестовый доступ 7 дней</code> — <b>490₽</b>"
    )

    # Кнопки тарифов, под ними главное меню
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Безлимит на месяц — 1490₽", callback_query_data="buy_month")],
        [InlineKeyboardButton(text="⚡️ Тестовый доступ 7 дней — 490₽", callback_query_data="buy_test")],
        [InlineKeyboardButton(text="📱 Главное меню", callback_query_data="to_main")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "🚀 Добро пожаловать в <b>LeadFinder</b>! Настройте фильтры и ключевые слова для поиска клиентов.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "menu_profile")
async def show_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    profile = await db.get_user_profile(user_id)
    keywords = await db.get_keywords(user_id)

    # Превращаем технические данные ГЕО в красивый текст
    geo_text = "Все города"
    if profile[1] == 'msk':
        geo_text = "Москва"
    elif profile[1] == 'spb':
        geo_text = "Санкт-Петербург"

    text = (
        "👤 <b>Ваш персональный профиль:</b>\n"
        "──────────────────\n"
        f"🆔 <b>Ваш Telegram ID:</b> <code>{user_id}</code>\n"
        f"📅 <b>Статус подписки:</b> Пробный период (2 дн.)\n"
        f"🗺 <b>Регион поиска:</b> {geo_text}\n"
        f"⚡️ <b>Мониторинг чатов:</b> Запущен (Амстердам)\n"
        f"🔑 <b>Всего фраз в базе:</b> <code>{len(keywords)} / {MAX_KEYWORDS} лимит</code>\n"
        "──────────────────\n"
        "🚀 <i>Система работает в штатном режиме. Заявки парсятся без задержек.</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_query_data="to_main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "menu_keywords")
async def show_keywords_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    keywords = await db.get_keywords(user_id)
    stop_words = await db.get_stop_words(user_id)

    kw_list = "\n".join([f"└ <code>{kw[0]}</code>" for kw in keywords]) if keywords else "└ <i>Список пуст</i>"
    sw_list = "\n".join([f"└ <code>{sw[0]}</code>" for sw in stop_words]) if stop_words else "└ <i>Список пока пуст</i>"

    text = (
        "🔑 <b>Панель управления списками парсинга</b>\n\n"
        f"🎯 <b>Ваши Ключевые слова ({len(keywords)}/{MAX_KEYWORDS}):</b>\n{kw_list}\n\n"
        f"🛑 <b>Ваши Стоп-слова:</b>\n{sw_list}\n\n"
        "👇 <b>Используйте кнопки ниже для добавления и удаления:</b>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить КЛЮЧ", callback_query_data="add_key"),
            InlineKeyboardButton(text="➕ Добавить СТОП-слово", callback_query_data="add_stop")
        ],
        [InlineKeyboardButton(text="🗑 Удалить фразу из базы", callback_query_data="del_word")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_query_data="to_main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# Логика добавления ключевых слов
@router.callback_query(F.data == "add_key")
async def process_add_key(callback: CallbackQuery, state: FSMContext):
    keywords = await db.get_keywords(callback.from_user.id)
    if len(keywords) >= MAX_KEYWORDS:
        await callback.answer(f"❌ Достигнут лимит в {MAX_KEYWORDS} ключевых слов!", show_alert=True)
        return
    await callback.message.answer("✏️ Введите новое ключевое слово или фразу для поиска:")
    await state.set_state(Form.waiting_for_keyword)
    await callback.answer()


@router.message(Form.waiting_for_keyword)
async def save_keyword(message: Message, state: FSMContext):
    success = await db.add_keyword(message.from_user.id, message.text)
    await state.clear()
    if success:
        await message.answer("✅ Ключевое слово успешно добавлено в базу!")
    else:
        await message.answer("⚠️ Такое слово уже есть в вашей базе.")
    # Возвращаем меню
    keywords = await db.get_keywords(message.from_user.id)
    stop_words = await db.get_stop_words(message.from_user.id)
    kw_list = "\n".join([f"└ <code>{kw[0]}</code>" for kw in keywords]) if keywords else "└ <i>Список пуст</i>"
    sw_list = "\n".join([f"└ <code>{sw[0]}</code>" for sw in stop_words]) if stop_words else "└ <i>Список пока пуст</i>"
    text = f"🔑 <b>Панель управления списками парсинга</b>\n\n🎯 <b>Ваши Ключевые слова ({len(keywords)}/{MAX_KEYWORDS}):</b>\n{kw_list}\n\n🛑 <b>Ваши Стоп-слова:</b>\n{sw_list}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить КЛЮЧ", callback_query_data="add_key"),
         InlineKeyboardButton(text="➕ Добавить СТОП-слово", callback_query_data="add_stop")],
        [InlineKeyboardButton(text="🗑 Удалить фразу из базы", callback_query_data="del_word")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_query_data="to_main")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


# Логика добавления стоп-слов
@router.callback_query(F.data == "add_stop")
async def process_add_stop(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("✏️ Введите стоп-слово (при его наличии в заявке уведомление приходить не будет):")
    await state.set_state(Form.waiting_for_stopword)
    await callback.answer()


@router.message(Form.waiting_for_stopword)
async def save_stopword(message: Message, state: FSMContext):
    await db.add_stop_word(message.from_user.id, message.text)
    await state.clear()
    await message.answer("✅ Стоп-слово успешно добавлено!")

    # Релоад меню
    keywords = await db.get_keywords(message.from_user.id)
    stop_words = await db.get_stop_words(message.from_user.id)
    kw_list = "\n".join([f"└ <code>{kw[0]}</code>" for kw in keywords]) if keywords else "└ <i>Список пуст</i>"
    sw_list = "\n".join([f"└ <code>{sw[0]}</code>" for sw in stop_words]) if stop_words else "└ <i>Список пока пуст</i>"
    text = f"🔑 <b>Панель управления списками парсинга</b>\n\n🎯 <b>Ваши Ключевые слова ({len(keywords)}/{MAX_KEYWORDS}):</b>\n{kw_list}\n\n🛑 <b>Ваши Стоп-слова:</b>\n{sw_list}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить КЛЮЧ", callback_query_data="add_key"),
         InlineKeyboardButton(text="➕ Добавить СТОП-слово", callback_query_data="add_stop")],
        [InlineKeyboardButton(text="🗑 Удалить фразу из базы", callback_query_data="del_word")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_query_data="to_main")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


# Удаление фраз
@router.callback_query(F.data == "del_word")
async def process_del_word(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("✏️ Введите слово/фразу, которую хотите УДАЛИТЬ из списков:")
    await state.set_state(Form.waiting_for_delete_word)
    await callback.answer()


@router.message(Form.waiting_for_delete_word)
async def delete_word_from_db(message: Message, state: FSMContext):
    word = message.text.strip().lower()
    await db.delete_keyword(message.from_user.id, word)
    # Пытаемся удалить также из стоп-слов на случай, если оно там
    async with db.aiosqlite.connect(db.DB_URL.replace("sqlite+aiosqlite:///", "")) as con:
        await con.execute("DELETE FROM stop_words WHERE user_id = ? AND word = ?", (message.from_user.id, word))
        await con.commit()
    await state.clear()
    await message.answer("🗑 Если фраза присутствовала в списках, она была полностью удалена.")

