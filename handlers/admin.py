from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import ADMIN_ID
import database as db

router = Router()


class AdminForm(StatesGroup):
    waiting_for_chat_link = State()


@router.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    chats = await db.get_tracked_chats()

    text = (
        "👨‍💼 <b>Панель администратора LeadFinder</b>\n"
        "──────────────────\n"
        f"📊 <b>Чатов на мониторинге:</b> <code>{len(chats)}</code>\n\n"
        "Вы можете добавить любой открытый чат или супергруппу. Юзербот начнет слушать сообщения мгновенно."
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить чат для парсинга", callback_query_data="adm_add_chat")],
        [InlineKeyboardButton(text="📋 Список чатов / Удаление", callback_query_data="adm_list_chats")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "adm_add_chat", F.from_user.id == ADMIN_ID)
async def adm_request_link(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📥 Отправьте юзернейм чата (например, `@beauty_group`) или прямую ссылку на открытую группу:")
    await state.set_state(AdminForm.waiting_for_chat_link)
    await callback.answer()


# Прием ссылки на чат админом. Валидацию названия проведет Юзербот в основном файле, здесь сохраняем первичные данные
@router.message(AdminForm.waiting_for_chat_link, F.from_user.id == ADMIN_ID)
async def adm_save_chat(message: Message, state: FSMContext):
    chat_input = message.text.strip().replace("https://t.me", "@")

    # Простой парсинг сущности для сохранения структуры базы
    await db.add_tracked_chat(chat_id=hash(chat_input), username=chat_input, title=f"Чат: {chat_input}")
    await state.clear()
    await message.answer(
        f"✅ Чат <code>{chat_input}</code> добавлен в базу мониторинга. Юзербот подключится автоматически при перезапуске системы.",
        parse_mode="HTML")


@router.callback_query(F.data == "adm_list_chats", F.from_user.id == ADMIN_ID)
async def adm_show_chats(callback: CallbackQuery):
    chats = await db.get_tracked_chats()
    if not chats:
        await callback.message.answer("📭 Список чатов пуст.")
        await callback.answer()
        return

    text = "📋 <b>Список отслеживаемых чатов:</b>\n\n"
    kb_list = []
    for chat_id, username, title in chats:
        text += f"🔹 {title} ({username})\n"
        kb_list.append([InlineKeyboardButton(text=f"❌ Удалить {username}", callback_query_data=f"del_chat_{chat_id}")])

    kb_list.append([InlineKeyboardButton(text="⬅️ В админку", callback_query_data="to_adm_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list),
                                     parse_mode="HTML")


@router.callback_query(F.data.startswith("del_chat_"), F.from_user.id == ADMIN_ID)
async def adm_delete_chat(callback: CallbackQuery):
    chat_id = int(callback.data.replace("del_chat_", ""))
    await db.remove_tracked_chat(chat_id)
    await callback.answer("🗑 Чат удален из базы парсинга!")
    await adm_show_chats(callback)


@router.callback_query(F.data == "to_adm_main", F.from_user.id == ADMIN_ID)
async def to_adm_main(callback: CallbackQuery):
    chats = await db.get_tracked_chats()
    text = f"👨‍💼 <b>Панель администратора LeadFinder</b>\n──────────────────\n📊 <b>Чатов на мониторинге:</b> <code>{len(chats)}</code>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить чат для парсинга", callback_query_data="adm_add_chat")],
        [InlineKeyboardButton(text="📋 Список чатов / Удаление", callback_query_data="adm_list_chats")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
