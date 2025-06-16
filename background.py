import aiocron
from database import get_upcoming_deadlines
from datetime import date
from aiogram import Bot

@aiocron.crontab('0 9 * * *')  # каждый день в 9:00 утра
async def daily_check(bot: Bot):
    tasks = await get_upcoming_deadlines()
    today = date.today()

    for task in tasks:
        # 🔽 Пропускаем задачи, которые уже сделаны
        if task["status"] == "Сделано":
            continue

        days_left = (task["deadline"] - today).days
        executor_id = task["executor_id"]
        specialist_id = task["specialist_id"]
        title = task["title"]
        task_id = task["task_executor_id"]

        msg_executor = None
        msg_specialist = None

        if days_left < 0:
            msg_executor = f"⚠️ Задача #{task_id} «{title}» просрочена!"
            msg_specialist = f"⚠️ У исполнителя просрочена задача #{task_id} «{title}»."
        elif days_left == 0:
            msg_executor = f"📅 Сегодня дедлайн по задаче #{task_id} «{title}»."
            msg_specialist = f"📌 Сегодня дедлайн у исполнителя по задаче #{task_id}."
        elif days_left == 1:
            msg_executor = f"⏳ Завтра дедлайн по задаче #{task_id} «{title}»."

        if msg_executor:
            await bot.send_message(chat_id=executor_id, text=msg_executor)
        if msg_specialist:
            await bot.send_message(chat_id=specialist_id, text=msg_specialist)
