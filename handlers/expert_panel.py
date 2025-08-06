from aiogram import Router, F
from aiogram.types import (
    Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, Document
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import (
    get_expert_tasks,
    update_expert_note_file,  # нужно реализовать
    get_task_by_id,
    update_task_status_by_id,
    mark_order_section_done,
    update_expert_note_url,
    get_task_id_by_expert_task
)
import os
from pathlib import Path
from aiogram.filters import StateFilter
router = Router()

EXPERT_FILES_DIR = os.path.join("psdbot", "documents", "expert_notes")
os.makedirs(EXPERT_FILES_DIR, exist_ok=True)


class ExpertNoteStates(StatesGroup):
    awaiting_note_text = State()

@router.message(F.text == "📄 Мои экспертизы")
async def show_expert_tasks(message: Message):
    tasks = await get_expert_tasks(message.from_user.id)

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
            ),
            InlineKeyboardButton(
                text="✅ Одобрить",
                callback_data=f"approve_note:{task['task_id']}"
            )
        ]

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
    print("🟡 Получено сообщение от эксперта.")

    data = await state.get_data()
    task_id = data.get("task_id")
    print(f"🔧 task_id из state: {task_id}")

    note_text = message.text

    file_path = await save_expert_note(task_id, note_text)

    if file_path is None:
        print("❌ save_expert_note вернул None.")
        await message.answer("⚠️ Не удалось найти заказ. Возможно, он был удалён.")
        await state.clear()
        return

    print(f"📁 Замечания сохранены по пути: {file_path}")

    await update_expert_note_url(task_id, str(file_path))
    print("✅ Ссылка на файл замечаний сохранена в БД.")

    await message.answer("✅ Замечания успешно сохранены.")
    await state.clear()

    # Отправка замечаний ГИПу и специалисту
    task = await get_task_id_by_expert_task(task_id)
    if not task:
        print("❌ Task не найден в get_task_id_by_expert_task")
        return

    section_user_id = task.get("section_user_id")
    gip_user_id = task.get("gip_user_id")
    section = task.get("section", "").upper()
    order_title = task.get("order_title", "Без названия")

    print(f"📦 Отправляем файл по заказу: {order_title}, раздел: {section}")
    print(f"👤 Специалист ID: {section_user_id}, ГИП ID: {gip_user_id}")

    expert_username = message.from_user.username
    expert_id = message.from_user.id

    expert_display = (
        f"@{expert_username}" if expert_username
        else f'<a href="tg://user?id={expert_id}">{message.from_user.full_name}</a>'
    )

    caption = (
        f"📌 Замечания по заказу <b>{order_title}</b>\n"
        f"Раздел: <b>{section}</b>\n"
        f"👷 Эксперт: {expert_display}"
    )

    reply_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉ Ответить эксперту", url=f"tg://user?id={expert_id}")]
    ])

    try:
        doc = FSInputFile(file_path)
    except Exception as e:
        print(f"❌ Ошибка при открытии файла: {e}")
        return

    for user_id in [section_user_id, gip_user_id]:
        if user_id:
            try:
                print(f"📤 Отправляем файл пользователю {user_id}")
                await message.bot.send_document(
                    chat_id=user_id,
                    document=doc,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_button
                )
                print(f"✅ Успешно отправлено пользователю {user_id}")
            except Exception as e:
                print(f"⚠️ Не удалось отправить замечания пользователю {user_id}: {e}")


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
    task_id = int(callback.data.split(":")[1])

    # Получаем задачу
    task = await get_task_by_id(task_id)
    order_id = task["order_id"]
    section = task["section"].lower()

    # Обновляем статус задачи
    await update_task_status_by_id(task_id, "approved_by_expert")

    # Универсально обновим поле <section>_status у заказа
    await mark_order_section_done(order_id, section)

    # Удаляем кнопки и уведомляем
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"✅ Раздел {section.upper()} одобрен экспертом.")
    await callback.answer("Одобрено ✅", show_alert=True)
