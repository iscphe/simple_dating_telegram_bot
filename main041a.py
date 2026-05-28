import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "xxx"
ADMIN_ID = xxx
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
def init_db():
    with sqlite3.connect('dating_bot.db') as conn:
        cur = conn.cursor()
        # Таблица пользователей
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                age INTEGER,
                photo_id TEXT,
                status TEXT
            )
        """)
        # Таблица лайков
        cur.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                liker_id INTEGER,
                liked_id INTEGER,
                PRIMARY KEY (liker_id, liked_id)
            )
        """)
        conn.commit()

init_db()

# --- КЛАВИАТУРЫ ---
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔍 Найти пару"), KeyboardButton(text="📝 Моя анкета")],
        [KeyboardButton(text="ℹ️ Справка")]
    ],
    resize_keyboard=True
)

# --- КОМАНДА /START ---
@dp.message(Command("start")) 
async def start(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    with sqlite3.connect('dating_bot.db') as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM users WHERE id = ?", (uid,))
        user = cur.fetchone()
 
    if user is None:
        await message.answer(
            f"Привет, {message.from_user.first_name}! Рад видеть тебя в боте знакомств.\n"
            f"Ты еще не зарегистрирован. Используй команду /profile или кнопку ниже, чтобы создать анкету!",
            reply_markup=main_kb
        )
    else:
        await message.answer(
            f"Привет, {message.from_user.first_name}! Рад видеть тебя снова.\n"
            f"Используй меню ниже для навигации 👇",
            reply_markup=main_kb
        )

# --- КОМАНДА /HELP И КНОПКА СПРАВКИ ---
@dp.message(Command("help"))
@dp.message(F.text == "ℹ️ Справка")
async def help_command(message: types.Message):
    help_text = (
        "📝 **Моя анкета** — управление вашим профилем.\n\n"
        "🔍 **Найти пару** — просмотр анкет.\n"
        "ℹ️ **Справка** — просмотр данной страницы.\n\n"
        "**Правила :**\n"
        "!!! Программное обеспечение PICONY предназначено для поиска людей\n"
        "в сети интернет, с целью общения, знакомства и встречи в оффлайне.\n"
        "Пользователь сам открывает все данные (фото, возраст, описание).\n"
        "ПО делится ими с другими пользователями по механизму взаимной симпатии.\n"
        "Каждая анкета соответствует реальному человеку.\n"
        "Общайтесь, знакомьтесь.\n"
        "Администрация проводит модерацию анкет.\n"
        "Приятного полета! :D \n"
        "\n"
        "\n"
        "Нажимайте ❤️, чтобы выразить симпатию. Если человек ответит взаимностью, "
        "программа пришлет вам ссылки на профили друг друга!"
    )
    await message.answer(help_text, parse_mode="Markdown")

# --- ЛОГИКА ПОИСКА (ФУНКЦИЯ) ---
async def run_search(user_id: int, message: types.Message, state: FSMContext):
    data = await state.get_data()
    viewed_ids = data.get("viewed_ids", [])
    
    exclude_ids = viewed_ids + [user_id]
    placeholders = ", ".join(["?"] * len(exclude_ids))
    
    with sqlite3.connect('dating_bot.db') as conn:
        cur = conn.cursor()
        query = f"""
            SELECT id, name, age, photo_id 
            FROM users 
            WHERE status = 'active' AND id NOT IN ({placeholders}) 
            ORDER BY RANDOM() LIMIT 1
        """
        cur.execute(query, exclude_ids)
        target = cur.fetchone()

    # Если анкеты закончились
    if not target:
        if viewed_ids:
            # Очищаем историю просмотров в FSM
            await state.update_data(viewed_ids=[])
            # Запускаем поиск заново с чистым списком (исключая только себя)
            return await run_search(user_id, message, state)
        return await message.answer("Пока никого нет... Попробуй позже!")

    target_id, name, age, photo_id = target
    
    # Добавляем анкету в просмотренные
    viewed_ids.append(target_id)
    await state.update_data(viewed_ids=viewed_ids)

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{target_id}"),
        InlineKeyboardButton(text="🈯️ Дальше", callback_data="next_profile")
    ]])
    
    await message.answer_photo(photo=photo_id, caption=f"{name}, {age}", reply_markup=kb)

# Точки входа в поиск
@dp.message(Command("search"))
@dp.message(F.text == "🔍 Найти пару")
async def search_command(message: types.Message, state: FSMContext):
    await run_search(message.from_user.id, message, state)

# --- ОБРАБОТЧИКИ ДЛЯ ИНЛАЙН-КНОПОК ---

@dp.callback_query(F.data == "next_profile")
async def next_profile_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await run_search(callback.from_user.id, callback.message, state)
    await callback.answer()

@dp.callback_query(F.data.startswith("like_"))
async def like_profile_handler(callback: types.CallbackQuery, state: FSMContext):
    sender_id = callback.from_user.id
    target_id = int(callback.data.split("_")[1])

    with sqlite3.connect('dating_bot.db') as conn:
        cur = conn.cursor()
        
        # Проверяем взаимность
        cur.execute("SELECT 1 FROM likes WHERE liker_id = ? AND liked_id = ?", (target_id, sender_id))
        is_match = cur.fetchone()

        if is_match:
            # Получаем имена для отправки уведомлений
            cur.execute("SELECT name FROM users WHERE id = ?", (sender_id,))
            sender_name = cur.fetchone()[0]
            
            cur.execute("SELECT name FROM users WHERE id = ?", (target_id,))
            target_name = cur.fetchone()[0]

            # Сообщение текущему
            await callback.message.answer(
                f"🎉 Взаимная симпатия! Вы понравились {target_name}.\n"
                f"Напиши ему/ей: [{target_name}](tg://user?id={target_id})",
                parse_mode="Markdown"
            )
            # Сообщение второму
            try:
                await callback.bot.send_message(
                    chat_id=target_id,
                    text=f"🎉 Взаимная симпатия с {sender_name}!\n"
                         f"Напиши ему/ей: [{sender_name}](tg://user?id={sender_id})",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
                
            cur.execute("DELETE FROM likes WHERE liker_id = ? AND liked_id = ?", (target_id, sender_id))
        else:
            # Обычный лайк
            cur.execute("INSERT OR IGNORE INTO likes (liker_id, liked_id) VALUES (?, ?)", (sender_id, target_id))
            try:
                await callback.bot.send_message(
                    chat_id=target_id, 
                    text="❤️ Ты кому-то понравился! Нажми '🔍 Найти пару', чтобы найти взаимность."
                )
            except Exception:
                pass

        conn.commit()

    try:
        await callback.message.delete()
    except Exception:
        pass
        
    await run_search(sender_id, callback.message, state)
    await callback.answer()

# Запуск бота
if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))