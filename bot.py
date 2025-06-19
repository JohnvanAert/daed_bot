from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from asyncio import run
from database import connect_db
from handlers import start, registration, tasks, assign_specialist, view_orders, assign_executor, assign_sketch, ep_panel, ar_executor, calculator_panel, genplan_panel, ovik_panel, vk_panel, gs_panel, kj_panel
from dotenv import load_dotenv
import os
from handlers import gip_review
from handlers import ar_panel
from background import daily_check
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
dp.include_router(assign_executor.router)
dp.include_router(view_orders.router) 
dp.include_router(assign_sketch.router)
dp.include_router(ep_panel.router)
dp.include_router(gip_review.router)
dp.include_router(ar_panel.router)
dp.include_router(ar_executor.router)
dp.include_router(calculator_panel.router)
dp.include_router(genplan_panel.router)
dp.include_router(ovik_panel.router)
dp.include_router(vk_panel.router)
dp.include_router(gs_panel.router)
dp.include_router(kj_panel.router)

async def main():
    await connect_db()
    daily_check(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    run(main())
