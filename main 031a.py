import asyncio
import sqlite3
import aiosqlite
import logging
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- НАСТРОЙКИ ---
API_TOKEN = 'xxx'
ADMIN_ID = xxx

logging.basicConfig(level=logging.INFO) #Настраивает логирование. Уровень INFO означает, что в консоли вы будете видеть не только ошибки, но и важную служебную информацию: например, отчеты о запуске бота или уведомления о входящих сообщениях. Это помогает понимать, что происходит «под капотом» в реальном времени.
bot = Bot(token=API_TOKEN) #Создает экземпляр бота с нашим токеном
dp = Dispatcher() #создает диспетчера

# --- БАЗА ДАННЫХ --- 
def init_db():
    with sqlite3.connect('dating_bot.db') as conn:
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS users 
                       (id INTEGER PRIMARY KEY, name TEXT, age INTEGER, photo_id TEXT, status TEXT, username TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS feedbacks 
               (from_id INTEGER, to_id INTEGER, comment TEXT)''')
        conn.commit() 
        
class Reg(StatesGroup): #класс состояний (на каком этапе сейчас юзер?)
    name = State()
    age = State()
    photo = State() 
    comment = State() # состояние при котором юзер пишет комментарий после дизлайка

# --- ЛОГИКА РЕГИСТРАЦИИ ---
@dp.message(Command("start")) 
async def start(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    with sqlite3.connect('dating_bot.db') as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM users WHERE id = ?", (uid,))
        user = cur.fetchone()
    
    if user:
        if user[0] == 'active':
            return await message.answer("Твоя анкета активна! Жми /search чтобы смотреть других.")
        if user[0] == 'moderate':
            return await message.answer("Твоя анкета еще на проверке.")
            
    await message.answer("Привет! Давай создадим анкету. Как тебя зовут?")
    await state.set_state(Reg.name)

@dp.message(Reg.name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Сколько тебе лет?")
    await state.set_state(Reg.age)

@dp.message(Reg.age)
async def get_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введи возраст числом!")
    await state.update_data(age=int(message.text))
    await message.answer("Пришли свое фото")
    await state.set_state(Reg.photo)

@dp.message(Reg.photo, F.photo)
async def get_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = message.photo[-1].file_id
    uid = message.from_user.id
    # Получаем юзернейм (может быть None, если он не задан в настройках ТГ)
    username = message.from_user.username 

    # Асинхронное подключение не вешает бота
    async with aiosqlite.connect('dating_bot.db') as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (id, name, age, photo_id, status, username) VALUES (?, ?, ?, ?, ?, ?)", 
            (uid, data['name'], data['age'], photo_id, 'moderate', username)
        )
        await db.commit()
    
    await message.answer("Готово! Анкета на проверке...")
    # ... дальше отправка админу

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"app_{uid}"),
        InlineKeyboardButton(text="❌ Бан", callback_data=f"ban_{uid}")
    ]])
    
    await bot.send_photo(
        ADMIN_ID, 
        photo_id, 
        caption=f"Новая анкета:\n{data['name']}, {data['age']}\nID: {uid}", 
        reply_markup=kb
    )
    await state.clear()

# --- ЛОГИКА ПОИСКА ---
@dp.message(Command("search")) #/search
async def search(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    with sqlite3.connect('dating_bot.db') as conn:
        cur = conn.cursor()
        # Ищем случайную активную анкету, кроме своей
        cur.execute("SELECT id, name, age, photo_id FROM users WHERE status = 'active' AND id != ? ORDER BY RANDOM() LIMIT 1", (uid,))
        target = cur.fetchone()

    if not target:
        return await message.answer("Пока никого нет... Попробуй позже!")

    target_id, name, age, photo_id = target
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{target_id}"),
        InlineKeyboardButton(text="🈯️ Дальше", callback_data="search")
    ]])
    
    await state.update_data(last_viewed_id=target_id)

    await bot.send_photo(uid, photo_id, caption=f"{name}, {age}", reply_markup=kb)

# --- ОБРАБОТКА КНОПОК ---
@dp.callback_query(F.data == "search")
async def ask_dislike_comment(call: types.CallbackQuery, state: FSMContext):
    # Если в callback_data зашит ID (например "dislike_123"), достань его
    # Для простоты пока просто просим коммент
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏩ Пропустить", callback_data="skip_comment")
    ]])
    
    await call.message.answer("🗒 Оставьте комментарий.", reply_markup=kb)
    await state.set_state(Reg.comment)
    await call.answer()

@dp.callback_query(F.data.startswith("like_"))
async def like(call: types.CallbackQuery, state: FSMContext):
    target_id = int(call.data.split("_")[1])
    my_id = call.from_user.id
    my_username = call.from_user.username # Чтобы партнер мог нам написать
    
    async with aiosqlite.connect('dating_bot.db') as db:
        # 1. Записываем наш лайк в базу (создай таблицу likes в init_db заранее!)
        await db.execute("INSERT OR IGNORE INTO likes (from_id, to_id) VALUES (?, ?)", (my_id, target_id))
        await db.commit()
        
        # 2. Проверяем, есть ли ответный лайк от него к нам?
        async with db.execute("SELECT * FROM likes WHERE from_id = ? AND to_id = ?", (target_id, my_id)) as cursor:
            is_match = await cursor.fetchone()
            
        if is_match:
            # 3. Это МЭТЧ! Уведомляем обоих.
            await call.message.answer(f"🎉 Взаимная симпатия c @{target_username_from_db}")
            # Тут нужно будет еще отправить сообщение target_id, что у него мэтч
        else:
            await call.answer("Лайк отправлен!")

    await search(call.message, state)

@dp.callback_query(F.data.startswith("app_"))
async def approve(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    with sqlite3.connect('dating_bot.db') as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET status = 'active' WHERE id = ?", (user_id,))
        conn.commit()
    await bot.send_message(user_id, "Твоя анкета одобрена! Теперь ты можешь искать людей с помощью /search")
    await call.message.edit_caption(caption="✅ Анкету одобрил")

@dp.callback_query(F.data.startswith("ban_"))
async def ban(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    with sqlite3.connect('dating_bot.db') as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET status = 'banned' WHERE id = ?", (user_id,))
        conn.commit()
    await call.message.edit_caption(caption="❌ Забанен")



@dp.callback_query(F.data == "skip_comment") #Обработка кнопка "пропустить комментарий"

async def skip_comment(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer("Окей, ищем дальше...")
    # Вызываем поиск (нужно передать message, берем его из call)
    await search(call.message, state)

@dp.message(Reg.comment) #Обработка самого текста (если юзер написал, 
                        # этот хендлер поймает текст и запишет его 
                        # в базу.)
async def save_dislike_comment(message: types.Message, state: FSMContext):
    comment_text = message.text
    uid = message.from_user.id
    data = await state.get_data()
    target_id = data.get('last_viewed_id') # Достаем ID того, кого дизлайкнули (мы его сохранили в функции search)

        
    
    async with aiosqlite.connect('dating_bot.db') as db:
        # Вот та самая строка! Добавляем target_id в запрос
        await db.execute(
            "INSERT INTO feedbacks (from_id, to_id, comment) VALUES (?, ?, ?)", 
            (uid, target_id, comment_text)
        )
        await db.commit()
    
    await message.answer("Спасибо за обратную связь!")
    await state.clear()
    await search(message, state) # Возвращаемся к поиску анкет



async def main():
    init_db()
    await dp.start_polling(bot) #asyncio создает бесконечный цикл. Бот не "спит", он постоянно 
                                        #проверяет, не пришли ли новые сообщения от серверов Telegram

if __name__ == '__main__': #проверяет, запущен ли файл напрямую. (Если вы 
                            #просто импортируете этот файл в другой проект, 
                            #код внутри этого условия не выполнится.) 
                            #Это защищает от случайного запуска логики
    try:
        asyncio.run(main()) ###пытается запустить главную асинхронную функцию main(). 
                                 #Метод asyncio.run создает цикл событий (event loop), 
                                    #выполняет программу и закрывает его по завершении##

    except KeyboardInterrupt:   #перехватывает нажатие клавиш Ctrl+C. Без этого блока при попытке 
                                #остановить бота вручную консоль выдала бы
                                # длинную «простыню» с ошибкой (Traceback) 
        print("Бот выключен")
