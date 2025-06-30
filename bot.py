from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from asyncio import run
from database import connect_db
from handlers import start, registration, tasks, assign_specialist, view_orders, assign_executor, assign_sketch, ep_panel, ar_executor, calculator_panel, genplan_panel, ovik_panel, vk_panel, gs_panel, kj_panel, eom_panel, ss_panel, estimator_panel, gip_review, ar_panel, register_expert, client_register, client_create_orders, client_order
from dotenv import load_dotenv
import os
from aiogram import Router
from aiogram.types import Message
from background import run_deadline_check
import aiocron
from background import router as background_router
load_dotenv()
router = Router()

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
dp.include_router(background_router)
dp.include_router(eom_panel.router)
dp.include_router(ss_panel.router)
dp.include_router(estimator_panel.router)
dp.include_router(register_expert.router)
dp.include_router(client_register.router)
dp.include_router(client_create_orders.router)
dp.include_router(client_order.router)
async def main():
    await connect_db()
    aiocron.crontab('0 9 * * *', func=lambda: run_deadline_check(bot))
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    run(main())
