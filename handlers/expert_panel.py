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
    mark_order_section_done
)
import os

router = Router()

EXPERT_FILES_DIR = os.path.join("psdbot", "documents", "expert_notes")
os.makedirs(EXPERT_FILES_DIR, exist_ok=True)


class ExpertNoteFSM(StatesGroup):
    waiting_for_note_file = State()


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

        buttons = []

        # показать кнопку только если статус — sent_to_experts
        if task['order_status'] == "sent_to_experts":
            if task['expert_note_url']:  # замечание прикреплено
                buttons.append(InlineKeyboardButton(
                    text="✅ Одобрить",
                    callback_data=f"approve_note:{task['task_id']}"
                ))
            else:
                buttons.append(InlineKeyboardButton(
                    text="📎 Прикрепить замечания",
                    callback_data=f"send_note:{task['task_id']}"
                ))

        keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None

        doc_path = f"psdbot/documents/{task['document_url']}"
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
async def start_send_note(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split(":")[1])
    await state.set_state(ExpertNoteFSM.waiting_for_note_file)
    await state.update_data(task_id=task_id)
    await callback.message.answer("📎 Пришлите ZIP файл с замечаниями по разделу.")
    await callback.answer()


@router.message(ExpertNoteFSM.waiting_for_note_file, F.document)
async def receive_note_file(message: Message, state: FSMContext):
    document: Document = message.document

    if not document.file_name.lower().endswith(".zip"):
        await message.answer("❗️Пожалуйста, отправьте файл в формате ZIP.")
        return

    data = await state.get_data()
    task_id = data["task_id"]

    filename = f"note_{task_id}_{document.file_name}"
    save_path = os.path.join(EXPERT_FILES_DIR, filename)

    file = await message.bot.get_file(document.file_id)
    await message.bot.download_file(file.file_path, destination=save_path)

    relative_path = os.path.relpath(save_path, "psdbot")

    # 🔄 Сохраняем в БД
    await update_expert_note_file(task_id, relative_path)

    await message.answer("✅ Замечания успешно прикреплены.")
    await state.clear()

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
