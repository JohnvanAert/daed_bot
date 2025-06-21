from datetime import date
from aiogram import Bot, Router, F
from aiogram.types import Message
from database import (
    get_upcoming_executor_deadlines,
    get_upcoming_specialist_deadlines
)

router = Router()

# 🔹 Уведомления исполнителям
async def notify_executors(bot: Bot):
    tasks = await get_upcoming_executor_deadlines()
    today = date.today()

    for task in tasks:
        if task["status"] == "Сделано":
            continue

        days_left = (task["deadline"] - today).days
        executor_id = task["executor_id"]
        task_id = task["task_executor_id"]
        title = task["title"]

        if days_left < 0:
            msg = f"⚠️ Задача #{task_id} «{title}» просрочена!"
        elif days_left == 0:
            msg = f"📅 Сегодня дедлайн по задаче #{task_id} «{title}»."
        elif days_left == 1:
            msg = f"⏳ Завтра дедлайн по задаче #{task_id} «{title}»."
        else:
            continue

        await bot.send_message(chat_id=executor_id, text=msg)


# 🔹 Уведомления специалистам
async def notify_specialists(bot: Bot):
    tasks = await get_upcoming_specialist_deadlines()
    today = date.today()

    for task in tasks:
        if task["status"] == "Сделано":
            continue

        days_left = (task["deadline"] - today).days
        specialist_id = task["specialist_id"]
        task_id = task["id"]
        section = task["section"].upper()

        if days_left < 0:
            msg = f"⚠️ Просрочена задача по разделу {section}, задача #{task_id}"
        elif days_left == 0:
            msg = f"📅 Сегодня дедлайн по разделу {section}, задача #{task_id}"
        elif days_left == 1:
            msg = f"⏳ Завтра дедлайн по разделу {section}, задача #{task_id}"
        else:
            continue

        await bot.send_message(chat_id=specialist_id, text=msg)


# 🔄 Объединённая функция
async def run_deadline_check(bot: Bot):
    await notify_executors(bot)
    await notify_specialists(bot)


# 🚀 Ручной запуск через /test_deadlines
@router.message(F.text == "/test_deadlines")
async def test_manual_check(message: Message, bot: Bot):
    await run_deadline_check(bot)
    await message.answer("✅ Проверка дедлайнов вручную выполнена.")
