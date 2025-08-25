from datetime import date
from aiogram import Bot, Router, F
from aiogram.types import Message
from database import (
    get_upcoming_executor_deadlines,
    get_upcoming_specialist_deadlines,
    add_bonus_penalty  # 👈 нужно реализовать в database.py
)

router = Router()


# 🔹 Уведомления исполнителям
async def notify_executors(bot: Bot, one_day_list: list):
    tasks = await get_upcoming_executor_deadlines()
    today = date.today()

    for task in tasks:
        if task["status"] == "Сделано":
            continue

        days_left = (task["deadline"] - today).days
        executor_id = task["executor_id"]
        section = task["section"].upper()
        task_id = task["task_executor_id"]
        order_id = task["order_id"]
        title = task["title"]

        if days_left < 0:
            msg = f"⚠️ Задача #{task_id} «{title}» просрочена!"
            # 👇 Записываем штраф
            await add_bonus_penalty(
                telegram_id=executor_id,
                task_id=task_id,
                type="penalty",
                description=f"Просрочка по разделу {section}, задача #{task_id}"
            )


        elif days_left == 0:
            msg = f"📅 Сегодня дедлайн по задаче #{task_id} «{title}»."
        elif days_left == 1:
            msg = f"⏳ Завтра дедлайн по задаче #{task_id} «{title}»."
            one_day_list.append(f"Исполнитель {executor_id} — задача #{task_id} «{title}»")
        else:
            continue

        await bot.send_message(chat_id=executor_id, text=msg)


# 🔹 Уведомления специалистам
async def notify_specialists(bot: Bot, one_day_list: list):
    tasks = await get_upcoming_specialist_deadlines()
    today = date.today()

    for task in tasks:
        if task["status"] == "Сделано":
            continue

        days_left = (task["deadline"] - today).days
        specialist_id = task["specialist_id"]
        task_id = task["id"]
        order_id = task["order_id"]
        section = task["section"].upper()

        # 👀 Лог для отладки
        print(f"[DEBUG] task_id={task_id}, order_id={order_id}, specialist_id={specialist_id}, days_left={days_left}")

        if days_left < 0:
            msg = f"⚠️ Просрочена задача по разделу {section}, задача #{task_id}"
            if order_id is None:
                print(f"[WARNING] Пропущена запись штрафа: нет order_id у задачи #{task_id}")
            else:
                # 👇 Записываем штраф
                await add_bonus_penalty(
                    telegram_id=specialist_id,
                    task_id=task_id,
                    type="penalty",
                    description=f"Просрочка по разделу {section}, задача #{task_id}"
                )


        elif days_left == 0:
            msg = f"📅 Сегодня дедлайн по разделу {section}, задача #{task_id}"
        elif days_left == 1:
            msg = f"⏳ Завтра дедлайн по разделу {section}, задача #{task_id}"
            one_day_list.append(f"Специалист {specialist_id} — {section}, задача #{task_id}")
        else:
            continue

        await bot.send_message(chat_id=specialist_id, text=msg)

# 🔄 Объединённая функция
async def run_deadline_check(bot: Bot, report_chat_id: int = None):
    one_day_list = []

    await notify_executors(bot, one_day_list)
    await notify_specialists(bot, one_day_list)

    # 📋 Отчёт по тем, у кого 1 день до дедлайна
    if report_chat_id and one_day_list:
        report_text = "⏳ Пользователи с 1 днём до дедлайна:\n\n" + "\n".join(one_day_list)
        await bot.send_message(chat_id=report_chat_id, text=report_text)


# 🚀 Ручной запуск через /test_deadlines
@router.message(F.text == "/test_deadlines")
async def test_manual_check(message: Message, bot: Bot):
    await run_deadline_check(bot, report_chat_id=message.chat.id)
    await message.answer("✅ Проверка дедлайнов вручную выполнена.")
