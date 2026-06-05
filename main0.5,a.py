import os
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "xxx"
ADMIN_ID = xxx
logging.basicConfig(level=logging.INFO) #Настраивает логирование. 
                                        #Уровень INFO означает, что в консоли 
                                        # вы будете видеть не только ошибки, но и важную
                                        #  служебную информацию: например, отчеты о запуске бота
                                        #  или уведомления о входящих сообщениях. Это
                                        #  помогает понимать, что происходит «под капотом»
                                        #  в реальном времени.
bot = Bot(token=TOKEN)

dp = Dispatcher(storage=MemoryStorage())


# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
# Функция для проверки, есть ли пользователь в таблице users базы данных sqlite3



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

class Registration(StatesGroup):
    name = State()
    age = State()
    photo = State()
    status = State()

class EditProfile(StatesGroup):
    name = State()
    age = State()
    photo = State()
    status = State()

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
            f"welcome, {message.from_user.first_name}>>> welcome ->>\n"
            f"создаем твой профайл. введи свое имя",
            reply_markup=main_kb
        )
        await state.set_state(Registration.name)
        return
    else:
        await message.answer(
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

# --- ПРОФИЛЬ И АНКЕТА ---
@dp.message(Command("profile"))
@dp.message(F.text == "📝 Моя анкета")
async def profile_command(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    with sqlite3.connect('dating_bot.db') as conn:
        cur = conn.cursor()
        cur.execute("SELECT name, age, photo_id, status FROM users WHERE id = ?", (uid,))
        user = cur.fetchone()

    if user:
        name, age, photo_id, status = user
        status_text = status if status else "Не указан"
        caption = (
            f"👤 Ваша анкета:\n\n"
            f"Имя: {name}\n"
            f"Возраст: {age}\n"
            f"Статус: {status_text}"
        )
        edit_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_profile")
        ]])
        if photo_id:
            await message.answer_photo(photo=photo_id, caption=caption, reply_markup=edit_kb)
        else:
            await message.answer(caption, reply_markup=edit_kb)
    else:
        await message.answer(
            "У тебя пока нет анкеты. Давай создадим её прямо сейчас. Как тебя зовут?",
            reply_markup=main_kb
        )
        await state.set_state(Registration.name)
        return

# --- РЕГИСТРАЦИЯ / СОЗДАНИЕ АНКЕТЫ ---
@dp.message(Registration.name)
async def registration_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Пожалуйста, напиши имя, которое будет отображено в анкете.")
        return

    await state.update_data(name=name)
    await message.answer("Отлично! Сколько тебе лет? (введите число)")
    await state.set_state(Registration.age)


@dp.message(Registration.age)
async def registration_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Возраст нужно указать числом. Попробуй еще раз.")
        return

    age = int(message.text)
    if age < 14 or age > 120:
        await message.answer("Укажи корректный возраст от 14 до 120.")
        return

    await state.update_data(age=age)
    skip_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_photo")]
    ])
    await message.answer("Здорово! Отправь свою фотографию для анкеты.", reply_markup=skip_kb)
    await state.set_state(Registration.photo)


@dp.message(Registration.photo, F.photo)
async def registration_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await message.answer("Фото получено. Добавьте текст анкеты.")
    await state.set_state(Registration.status)


@dp.callback_query(F.data == "skip_photo")
async def registration_skip_photo(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(photo_id=None)
    await callback.message.answer("Фото пропущено. Добавьте текст анкеты.")
    await state.set_state(Registration.status)
    await callback.answer()


@dp.message(Registration.photo)
async def registration_photo_invalid(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, пришли фото. Оно нужно для создания анкеты.")


@dp.message(Registration.status)
async def registration_status(message: types.Message, state: FSMContext):
    status = message.text.strip() or "Привет! Я открыт(а) для новых знакомств."
    data = await state.get_data()
    name = data.get("name")
    age = data.get("age")
    photo_id = data.get("photo_id")

    with sqlite3.connect('dating_bot.db') as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO users (id, name, age, photo_id, status) VALUES (?, ?, ?, ?, ?)",
            (message.from_user.id, name, age, photo_id, status)
        )
        conn.commit()

    await message.answer(
        f"🎉 Анкета создана!\n\nИмя: {name}\nВозраст: {age}\n{status}",
        reply_markup=main_kb
    )
    await state.clear()


# --- РЕДАКТИРОВАНИЕ ПРОФИЛЯ ---
@dp.callback_query(F.data == "edit_profile")
async def edit_profile_start(callback: types.CallbackQuery):
    edit_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Имя", callback_data="edit_name")],
        [InlineKeyboardButton(text="Возраст", callback_data="edit_age")],
        [InlineKeyboardButton(text="Фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="Статус", callback_data="edit_status")]
    ])
    await callback.message.answer("Что хотите изменить?", reply_markup=edit_kb)
    await callback.answer()


@dp.callback_query(F.data == "edit_name")
async def edit_profile_name(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напиши новое имя для анкеты.")
    await state.set_state(EditProfile.name)
    await callback.answer()


@dp.callback_query(F.data == "edit_age")
async def edit_profile_age(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новый возраст.")
    await state.set_state(EditProfile.age)
    await callback.answer()


@dp.callback_query(F.data == "edit_photo")
async def edit_profile_photo(callback: types.CallbackQuery, state: FSMContext):
    skip_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_edit_photo")]
    ])
    await callback.message.answer(
        "Пришли новую фотографию для анкеты или нажми Пропустить.",
        reply_markup=skip_kb
    )
    await state.set_state(EditProfile.photo)
    await callback.answer()


@dp.callback_query(F.data == "skip_edit_photo")
async def skip_edit_photo(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Фото не изменено. Если хотите, откройте профиль снова для продолжения редактирования.",
        reply_markup=main_kb
    )
    await state.clear()
    await callback.answer()


@dp.callback_query(F.data == "edit_status")
async def edit_profile_status(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Напиши новый статус или описание для анкеты.")
    await state.set_state(EditProfile.status)
    await callback.answer()


@dp.message(EditProfile.name)
async def edit_name_input(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Имя не может быть пустым. Введите имя еще раз.")
        return

    with sqlite3.connect('dating_bot.db') as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET name = ? WHERE id = ?", (name, message.from_user.id))
        conn.commit()

    await message.answer(f"Имя обновлено на: {name}", reply_markup=main_kb)
    await state.clear()


@dp.message(EditProfile.age)
async def edit_age_input(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Возраст нужно указать числом. Попробуй еще раз.")
        return

    age = int(message.text)
    if age < 1 or age > 9999:
        await message.answer("Укажи корректный возраст от 14 до 120.")
        return

    with sqlite3.connect('dating_bot.db') as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET age = ? WHERE id = ?", (age, message.from_user.id))
        conn.commit()

    await message.answer(f"Возраст обновлен на: {age}", reply_markup=main_kb)
    await state.clear()


@dp.message(EditProfile.photo, F.photo)
async def edit_photo_input(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    with sqlite3.connect('dating_bot.db') as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET photo_id = ? WHERE id = ?", (photo_id, message.from_user.id))
        conn.commit()

    await message.answer("Фото в анкете обновлено.", reply_markup=main_kb)
    await state.clear()


@dp.message(EditProfile.photo)
async def edit_photo_invalid(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, пришли фото, чтобы обновить анкету.")


@dp.message(EditProfile.status)
async def edit_status_input(message: types.Message, state: FSMContext):
    status = message.text.strip() or "Привет! Я открыт(а) для новых знакомств."
    with sqlite3.connect('dating_bot.db') as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET status = ? WHERE id = ?", (status, message.from_user.id))
        conn.commit()

    await message.answer(f"Статус обновлен на:\n{status}", reply_markup=main_kb)
    await state.clear()


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
            WHERE id NOT IN ({placeholders}) 
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
                f"Нажмите кнопку ниже, чтобы написать {target_name}:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Написать", url=f"tg://user?id={target_id}")]
                ])
            )
            # Сообщение второму
            try:
                await callback.bot.send_message(
                    chat_id=target_id,
                    text=f"🎉 Взаимная симпатия с {sender_name}!\n"
                         f"Нажмите кнопку ниже, чтобы написать {sender_name}:",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Написать", url=f"tg://user?id={sender_id}")]
                    ])
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

    async def run_polling_with_reconnect():
        backoff = 1
        max_backoff = 300
        global bot
        while True:
            try:
                logging.info("Starting polling...")
                await dp.start_polling(bot)
            except Exception:
                logging.exception("Polling stopped with exception, will attempt reconnect")
                logging.info("Reconnecting in %s seconds...", backoff)
                # Try to close existing bot session if possible
                try:
                    await bot.session.close()
                except Exception:
                    pass
                # recreate Bot instance to refresh connection
                try:
                    bot = Bot(token=TOKEN)
                except Exception:
                    logging.exception("Failed to recreate Bot instance")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
            else:
                # clean exit from polling (e.g., shutdown) -> stop loop
                logging.info("Polling stopped cleanly, exiting")
                break

    asyncio.run(run_polling_with_reconnect())