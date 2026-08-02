from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import database as db

router = Router()


def make_filters_keyboard(geo_mode: str, spam_filter: int):
    # Проверяем текущие отметки для ГЕО
    all_check = "✅" if geo_mode == "all" else "❌"
    msk_check = "✅" if geo_mode == "msk" else "❌"
    spb_check = "✅" if geo_mode == "spb" else "❌"

    # Проверяем фильтр спама
    spam_status = "Включен ✅" if spam_filter == 1 else "Выключен ❌"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{all_check} Все города", callback_query_data="set_geo_all")],
        [
            InlineKeyboardButton(text=f"{msk_check} Москва", callback_query_data="set_geo_msk"),
            InlineKeyboardButton(text=f"{spb_check} Санкт-Петербург", callback_query_data="set_geo_spb")
        ],
        [InlineKeyboardButton(text=f"🛡 Фильтр спама и дублей: {spam_status}", callback_query_data="toggle_spam")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_query_data="to_main")]
    ])


@router.callback_query(F.data == "menu_filters")
async def show_filters(callback: CallbackQuery):
    profile = await db.get_user_profile(callback.from_user.id)
    geo_mode = profile[1]
    spam_filter = profile[2]

    geo_text = "Все локации"
    if geo_mode == 'msk':
        geo_text = "Только Москва"
    elif geo_mode == 'spb':
        geo_text = "Только Санкт-Петербург"

    text = (
        "⚙️ <b>Интерактивная панель управления фильтрами парсера:</b>\n\n"
        "Настраивайте параметры фильтрации юзербота в реальном времени. "
        "Кликните по кнопке, чтобы переключить режим работы или выбрать ГЕО:\n\n"
        f"📍 <b>Текущий регион:</b> <code>{geo_text}</code>\n"
        "🎯 <b>Режим парсинга:</b> <code>Строгое совпадение фраз</code>\n"
        f"🤖 <b>Фильтр ботов и дублей:</b> <code>{'Активен' if spam_filter == 1 else 'Отключен'}</code>"
    )

    await callback.message.edit_text(text, reply_markup=make_filters_keyboard(geo_mode, spam_filter), parse_mode="HTML")


@router.callback_query(F.data.startswith("set_geo_"))
async def change_geo(callback: CallbackQuery):
    new_geo = callback.data.replace("set_geo_", "")
    await db.update_user_geo(callback.from_user.id, new_geo)
    # Обновляем меню на лету
    profile = await db.get_user_profile(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=make_filters_keyboard(profile[1], profile[2]))
    await callback.answer("📍 Регион поиска изменен!")


@router.callback_query(F.data == "toggle_spam")
async def change_spam(callback: CallbackQuery):
    profile = await db.get_user_profile(callback.from_user.id)
    current_spam = profile[2]
    new_status = await db.toggle_spam_filter(callback.from_user.id, current_spam)

    # Обновляем на лету
    await callback.message.edit_reply_markup(reply_markup=make_filters_keyboard(profile[1], new_status))
    await callback.answer("🛡 Статус фильтра спама изменен!")
