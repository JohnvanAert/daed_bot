from aiogram import Router, F
from aiogram.types import (
    Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, Document
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import (
    get_expert_tasks,
    get_task_by_expert_task_id,  # нужно реализовать
    approve_expert_task,
    approve_task,
    mark_order_section_done,
    update_expert_note_url,
    get_task_id_by_expert_task,
    get_task_users,
    update_task_created_at_and_status,
    update_expert_task_status
)
import os
from pathlib import Path
from aiogram.filters import StateFilter
from datetime import datetime, timedelta
router = Router()

EXPERT_FILES_DIR = os.path.join("psdbot", "documents", "expert_notes")
os.makedirs(EXPERT_FILES_DIR, exist_ok=True)


class ExpertNoteStates(StatesGroup):
    awaiting_note_text = State()


@router.message(F.text == "📄 Текущие экспертизы")
async def show_expert_tasks(message: Message):
    tasks = await get_expert_tasks(message.from_user.id, completed=False)

    if not tasks:
        await message.answer("📭 У вас пока нет прикреплённых заказов.")
        return

    for task in tasks:
        caption = (
            f"📌 Заказ: <b>{task['order_title']}</b>\n"
            f"Раздел: <b>{task['section'].upper()}</b>\n"
            f"Описание: {task['order_description']}"
        )

    buttons = [
        InlineKeyboardButton(
            text="📎 Прикрепить замечания",
            callback_data=f"send_note:{task['task_id']}"
        )
    ]

    # Добавляем кнопку "Одобрить", только если статус не "Одобрено"
    if task.get("status") != "Одобрено":
        buttons.append(
            InlineKeyboardButton(
                text="✅ Одобрить",
                callback_data=f"approve_note:{task['task_id']}"
            )
        )
    else:
        caption += "\n\n✅ <b>Раздел уже одобрен экспертом.</b>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])

    doc_path = task["document_url"]
    try:
        await message.answer_document(
            document=FSInputFile(doc_path),
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception as e:
        await message.answer(f"⚠️ Файл не найден по пути: {doc_path}")

@router.callback_query(F.data.startswith("send_note:"))
async def handle_send_note(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[1])

    await state.update_data(task_id=task_id)
    await callback.message.answer(
        "📝 Пожалуйста, введите текст замечаний к заказу:"
    )
    await state.set_state(ExpertNoteStates.awaiting_note_text)
    await callback.answer()  # Убираем "часики"

@router.message(StateFilter(ExpertNoteStates.awaiting_note_text))
async def receive_note_text(message: Message, state: FSMContext):

    data = await state.get_data()
    task_id = data.get("task_id")

    note_text = message.text

    file_path = await save_expert_note(task_id, note_text)
    deadline_date = (datetime.now() + timedelta(days=5)).strftime("%d.%m.%Y")
    if file_path is None:
        await message.answer("⚠️ Не удалось найти заказ. Возможно, он был удалён.")
        await state.clear()
        return

    await update_task_created_at_and_status(task_id)
    await update_expert_note_url(task_id, str(file_path))
    await message.answer("✅ Замечания успешно сохранены.")
    await state.clear()

    # Получаем данные задачи
    task = await get_task_id_by_expert_task(task_id)
    if not task:
        print("❌ Task не найден в get_task_id_by_expert_task")
        return

    section = task.get("section", "").upper()

    # Получаем пользователей задачи
    task_users = await get_task_users(task["task_id"])
    if not task_users:
        print(f"❌ Не удалось найти пользователей задачи ID {task['task_id']}")
        return

    section_user_id = task_users.get("section_user_id")
    gip_user_id = task_users.get("gip_id")
    order_title = task_users.get("order_title", "Без названия")

    # Информация об эксперте
    expert_username = message.from_user.username
    expert_id = message.from_user.id

    expert_display = (
        f"@{expert_username}" if expert_username
        else f'<a href="tg://user?id={expert_id}">{message.from_user.full_name}</a>'
    )

    # Открываем файл
    try:
        doc = FSInputFile(file_path)
    except Exception as e:
        print(f"❌ Ошибка при открытии файла: {e}")
        return

    # Отправляем специалисту (без имени эксперта)
    if section_user_id:
        try:
            await message.bot.send_document(
                chat_id=section_user_id,
                document=doc,
                caption=(
                    f"📌 Замечания по заказу <b>{order_title}</b>\n"
                    f"Раздел: <b>{section}</b>"
                    f"📅 Срок на исправление: <b>до {deadline_date}</b>"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Не удалось отправить специалисту: {e}")

    # Отправляем ГИПу (с именем эксперта и кнопкой ответа)
    if gip_user_id:
        try:
            await message.bot.send_document(
                chat_id=gip_user_id,
                document=doc,
                caption=(
                    f"📌 Замечания по заказу <b>{order_title}</b>\n"
                    f"Раздел: <b>{section}</b>\n"
                    f"👷 Эксперт: {expert_display}"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✉ Ответить эксперту", url=f"tg://user?id={expert_id}")]
                ])
            )
        except Exception as e:
            print(f"⚠️ Не удалось отправить ГИПу: {e}")

async def save_expert_note(task_id: int, text: str) -> Path | None:
    task = await get_task_id_by_expert_task(task_id)
    
    if task is None:
        print(f"❌ Task with ID {task_id} not found!")
        return None

    doc_path = Path(task["document_url"])
    section = task["section"].upper()

    project_dir = doc_path.parent
    notes_dir = project_dir / "expert_notes"
    notes_dir.mkdir(exist_ok=True)

    note_file_path = notes_dir / f"{section}.txt"
    note_file_path.write_text(text, encoding="utf-8")

    return note_file_path

@router.callback_query(F.data.startswith("approve_note:"))
async def handle_approve_note(callback: CallbackQuery):
    expert_task_id = int(callback.data.split(":")[1])

    # Получаем задачу через expert_task_id
    task = await get_task_by_expert_task_id(expert_task_id)
    if not task:
        await callback.answer("❌ Задача не найдена.", show_alert=True)
        return

    task_id = task["task_id"]
    section = task["section"].upper()

    # Обновляем статус через функции из database.py
    await approve_expert_task(expert_task_id, "Одобрено")
    await approve_task(task_id, "Одобрено экспертом")
    await callback.message.edit_reply_markup(reply_markup=None)

    await callback.answer("✅ Раздел одобрен!")

    # Получаем нужные ID пользователей
    task_users = await get_task_users(task_id)
    if not task_users:
        print(f"❌ Не найдены пользователи задачи ID {task_id}")
        return

    order_title = task_users.get("order_title", "Без названия")
    section_user_id = task_users.get("section_user_id")
    gip_user_id = task_users.get("gip_id")

    expert_username = callback.from_user.username
    expert_id = callback.from_user.id
    expert_display = (
        f"@{expert_username}"
        if expert_username
        else f'<a href="tg://user?id={expert_id}">{callback.from_user.full_name}</a>'
    )

    # Уведомляем специалиста
    if section_user_id:
        try:
            await callback.bot.send_message(
                chat_id=section_user_id,
                text=(
                    f"✅ <b>Раздел одобрен экспертом</b>\n"
                    f"📌 Заказ: <b>{order_title}</b>\n"
                    f"Раздел: <b>{section}</b>"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Не удалось отправить специалисту: {e}")

    # Уведомляем ГИПа
    if gip_user_id:
        try:
            await callback.bot.send_message(
                chat_id=gip_user_id,
                text=(
                    f"✅ <b>Эксперт одобрил раздел</b>\n"
                    f"📌 Заказ: <b>{order_title}</b>\n"
                    f"Раздел: <b>{section}</b>\n"
                    f"👷 Эксперт: {expert_display}"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="✉ Связаться с экспертом", url=f"tg://user?id={expert_id}")
                ]])
            )
        except Exception as e:
            print(f"⚠️ Не удалось отправить ГИПу: {e}")


@router.message(F.text == "📁 Завершённые экспертизы")
async def show_completed_expert_tasks(message: Message):
    tasks = await get_expert_tasks(message.from_user.id, completed=True)

    if not tasks:
        await message.answer("📭 У вас пока нет завершённых экспертиз.")
        return

    for task in tasks:
        caption = (
            f"📌 Заказ: <b>{task['order_title']}</b>\n"
            f"Раздел: <b>{task['section'].upper()}</b>\n"
            f"Описание: {task['order_description']}"
        )

        # Для завершённых экспертиз кнопки действий можно не показывать,
        # но, если хочешь, можно оставить кнопку "Посмотреть замечания"
        buttons = []
        if task.get("expert_note_url"):
            buttons.append(
                InlineKeyboardButton(
                    text="📎 Посмотреть замечания",
                    callback_data=f"view_note:{task['task_id']}"
                )
            )

        caption += "\n\n✅ <b>Раздел завершён.</b>"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None

        try:
            await message.answer_document(
                document=FSInputFile(task["document_url"]),
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except:
            await message.answer(f"⚠️ Файл не найден по пути: {task['document_url']}")
