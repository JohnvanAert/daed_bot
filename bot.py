# bot.py
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from asyncio import run
from database import connect_db

# Импортируй роутеры
from handlers import start, registration, tasks, assign_specialist

from dotenv import load_dotenv
import os

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN") # возьми из .env или напрямую

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Подключи роутеры
dp.include_router(start.router)
dp.include_router(registration.router)
dp.include_router(tasks.router)
dp.include_router(assign_specialist.router)

async def main():
    await connect_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    run(main())
