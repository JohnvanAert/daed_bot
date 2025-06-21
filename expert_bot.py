from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from asyncio import run
import os
from handlers import expert_panel
from database import connect_db

load_dotenv()
API_TOKEN = os.getenv("EXPERT_BOT_TOKEN")  # .env должен содержать токен отдельного бота

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

dp.include_router(expert_panel.router)

async def main():
    await connect_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    run(main())
