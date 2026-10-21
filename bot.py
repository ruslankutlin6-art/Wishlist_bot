import asyncio
import logging
import sqlite3
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Ваш токен от BotFather
TOKEN = os.getenv("BOT_TOKEN", "8923011131:AAGfGnOrdlUHc52l5-5oGLVHRGCw7TTXzuw")

# Инициализация базы данных SQLite
def init_db():
    conn = sqlite3.connect("apartment_wishlist.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            room TEXT,
            item TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_item_to_db(user_id: int, room: str, item: str):
    conn = sqlite3.connect("apartment_wishlist.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO wishlist (user_id, room, item) VALUES (?, ?, ?)", (user_id, room, item))
    conn.commit()
    conn.close()

def get_items_by_room(user_id: int, room: str):
    conn = sqlite3.connect("apartment_wishlist.db")
    cursor = conn.cursor()
    cursor.execute("SELECT item FROM wishlist WHERE user_id = ? AND room = ?", (user_id, room))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_all_items(user_id: int):
    conn = sqlite3.connect("apartment_wishlist.db")
    cursor = conn.cursor()
    cursor.execute("SELECT room, item FROM wishlist WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def clear_room_in_db(user_id: int, room: str):
    conn = sqlite3.connect("apartment_wishlist.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM wishlist WHERE user_id = ? AND room = ?", (user_id, room))
    conn.commit()
    conn.close()

class WishlistStates(StatesGroup):
    waiting_for_link = State()

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

ROOMS = {
    "kitchen": "🍳 Кухня",
    "hallway": "🚪 Прихожая",
    "living": "🛋 Гостиная",
    "bedroom": "🛏 Спальня",
    "bathroom": "🚿 Ванная"
}

def get_rooms_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍳 Кухня", callback_data="add_kitchen"),
         InlineKeyboardButton(text="🚪 Прихожая", callback_data="add_hallway")],
        [InlineKeyboardButton(text="🛋 Гостиная", callback_data="add_living"),
         InlineKeyboardButton(text="🛏 Спальня", callback_data="add_bedroom")],
        [InlineKeyboardButton(text="🚿 Ванная", callback_data="add_bathroom")],
        [InlineKeyboardButton(text="📋 Посмотреть весь виш-лист", callback_data="view_all")]
    ])

def get_room_actions_keyboard(room_key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Посмотреть товары этой комнаты", callback_data=f"show_{room_key}")],
        [InlineKeyboardButton(text="🗑 Очистить эту комнату", callback_data=f"clear_{room_key}")],
        [InlineKeyboardButton(text="🏠 Назад к выбору комнат", callback_data="back_to_menu")]
    ])

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 **Добро пожаловать в менеджер покупок для квартиры!**\n\n"
        "Выбери комнату, в которую хочешь добавить новую ссылку или товар:",
        reply_markup=get_rooms_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("add_"))
async def process_room_selection(callback: types.CallbackQuery, state: FSMContext):
    room_key = callback.data.split("_")[1]
    room_name = ROOMS[room_key]
    
    await state.update_data(current_room_key=room_key, current_room_name=room_name)
    await state.set_state(WishlistStates.waiting_for_link)
    
    await callback.message.edit_text(
        f"📍 **Выбран раздел: {room_name}**\n\n"
        f"Отправь мне ссылку на товар с Ozon (или напиши название/заметку), и я сразу сохраню её в эту комнату.",
        reply_markup=get_room_actions_keyboard(room_key),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(WishlistStates.waiting_for_link)
async def handle_link_input(message: types.Message, state: FSMContext):
    data = await state.get_data()
    room_key = data.get("current_room_key")
    room_name = data.get("current_room_name")
    
    if not room_key or not room_name:
        await message.answer("Произошла ошибка выбора комнаты. Пожалуйста, выберите комнату заново:", reply_markup=get_rooms_keyboard())
        await state.clear()
        return

    add_item_to_db(user_id=message.from_user.id, room=room_name, item=message.text)
    
    await message.answer(
        f"✅ **Добавлено в раздел «{room_name}»!**\n\n"
        f"Можешь сразу отправить еще одну ссылку для этой же комнаты или выбрать другое действие ниже:",
        reply_markup=get_room_actions_keyboard(room_key),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("show_"))
async def show_room_items(callback: types.CallbackQuery):
    room_key = callback.data.split("_")[1]
    room_name = ROOMS[room_key]
    items = get_items_by_room(user_id=callback.from_user.id, room=room_name)
    
    if not items:
        text = f"В разделе **{room_name}** пока нет сохраненных товаров."
    else:
        text = f"📦 **Товары в разделе «{room_name}»:**\n\n"
        for i, item in enumerate(items, 1):
            text += f"{i}. {item}\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_room_actions_keyboard(room_key),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("clear_"))
async def clear_room(callback: types.CallbackQuery):
    room_key = callback.data.split("_")[1]
    room_name = ROOMS[room_key]
    clear_room_in_db(user_id=callback.from_user.id, room=room_name)
    
    await callback.message.edit_text(
        f"🗑 Раздел **«{room_name}»** успешно очищен!",
        reply_markup=get_room_actions_keyboard(room_key),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "view_all")
async def view_all_wishlist(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    rows = get_all_items(user_id=callback.from_user.id)
    
    if not rows:
        text = "🛒 Твой виш-лист пока полностью пуст."
    else:
        text = "📋 **Твой общий список покупок по комнатам:**\n\n"
        grouped = {}
        for room, item in rows:
            grouped.setdefault(room, []).append(item)
            
        for room, items in grouped.items():
            text += f"**{room}:**\n"
            for i, item in enumerate(items, 1):
                text += f"  {i}. {item}\n"
            text += "\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Выбрать комнату для добавления", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Выбери комнату, в которую хочешь добавить товар:",
        reply_markup=get_rooms_keyboard()
    )
    await callback.answer()

async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    print("Бот виш-листа успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
