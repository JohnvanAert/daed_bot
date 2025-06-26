from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import os

from database import (
    get_tasks_for_executor,
    mark_task_as_submitted,
    get_specialist_by_task_executor_id
)

router = Router()
BASE_DOC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot", "documents"))

# Состояния FSM
class SubmitVKTaskFSM(StatesGroup):
    waiting_for_submission_file = State()

@router.message(F.text == "📌 Мои задачи по ВК")
async def show_vk_tasks(message: Message):
    executor_id = message.from_user.id
    tasks = await get_tasks_for_executor(executor_id)

    if not tasks:
        await message.answer("📭 У вас пока нет задач по ВК.")
        return

    for task in tasks:
        doc_path = os.path.abspath(os.path.join(BASE_DOC_PATH, os.path.relpath(task["document_url"], "documents")))

        caption = (
            f"📝 <b>{task['title']}</b>\n"
            f"{task['description']}\n"
            f"🕒 Дедлайн: {task['deadline'].strftime('%Y-%m-%d') if task['deadline'] else 'не указан'}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Отправить на проверку", callback_data=f"submit_vk_task:{task['task_executor_id']}")]
        ])

        if os.path.exists(doc_path):
            await message.answer_document(
                FSInputFile(doc_path),
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await message.answer(f"⚠️ Документ не найден для задачи: {task['title']}")


@router.callback_query(F.data.startswith("submit_vk_task:"))
async def handle_vk_submit_task(callback: CallbackQuery, state: FSMContext):
    task_executor_id = int(callback.data.split(":")[1])
    await state.update_data(task_executor_id=task_executor_id)
    await state.set_state(SubmitVKTaskFSM.waiting_for_submission_file)
    await callback.message.answer("📎 Пришлите файл в формате ZIP для отправки специалисту по ВК.")
    await callback.answer()


@router.message(SubmitVKTaskFSM.waiting_for_submission_file, F.document)
async def handle_vk_submission_file(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    task_executor_id = data.get("task_executor_id")
    document = message.document

    if not document.file_name.lower().endswith(".zip"):
        await message.answer("❗️ Файл должен быть в формате ZIP.")
        return

    filename = f"vk_submit_{task_executor_id}_{document.file_name}"
    save_path = os.path.join(BASE_DOC_PATH, filename)

    file = await bot.get_file(document.file_id)
    await bot.download_file(file.file_path, destination=save_path)

    relative_path = os.path.relpath(save_path, BASE_DOC_PATH)
    await mark_task_as_submitted(task_executor_id, relative_path)

    specialist = await get_specialist_by_task_executor_id(task_executor_id)
    if specialist:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_task:{task_executor_id}"),
                InlineKeyboardButton(text="🔁 Переделать", callback_data=f"revise_task:{task_executor_id}")
            ]
        ])

        await bot.send_document(
            chat_id=specialist["specialist_id"],
            document=FSInputFile(save_path),
            caption=(
                f"📥 Новый файл от исполнителя по задаче #{task_executor_id}\n"
                f"👤 Исполнитель: @{message.from_user.username or message.from_user.full_name}"
            ),
            reply_markup=keyboard
        )

    await message.answer("✅ Задание отправлено специалисту по ВК.")
    await state.clear()
