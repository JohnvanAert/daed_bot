from aiogram.types import (
    Message, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup,
    CallbackQuery, Document
)
from aiogram import Router, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database import get_tasks_for_executor, mark_task_as_submitted, get_user_by_telegram_id, get_specialist_by_task_executor_id, get_executor_by_task_executor_id, update_task_status
import os
from datetime import datetime
from aiogram import Bot

router = Router()
BASE_DOC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents"))

# Состояния FSM
class SubmitTaskFSM(StatesGroup):
    waiting_for_submission_file = State()

class ReviewTaskFSM(StatesGroup):
    waiting_for_revision_comment = State()

@router.message(F.text == "📌 Мои задачи")
async def show_executor_tasks(message: Message):
    executor_id = message.from_user.id
    tasks = await get_tasks_for_executor(executor_id)

    if not tasks:
        await message.answer("📭 У вас пока нет назначенных задач.")
        return

    for task in tasks:
        doc_path = os.path.abspath(os.path.join(BASE_DOC_PATH, os.path.relpath(task["document_url"], "documents")))

        caption = (
            f"📝 <b>{task['title']}</b>\n"
            f"{task['description']}\n"
            f"🕒 Дедлайн: {task['deadline'].strftime('%Y-%m-%d') if task['deadline'] else 'не указан'}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Отправить на проверку", callback_data=f"submit_task:{task['task_executor_id']}")]
        ])

        if os.path.exists(doc_path):
            await message.answer_document(
                FSInputFile(doc_path),
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await message.answer(f"⚠️ Документ не найден для заказа: {task['title']}")


@router.callback_query(F.data.startswith("submit_task:"))
async def handle_submit_task(callback: CallbackQuery, state: FSMContext):
    task_executor_id = int(callback.data.split(":")[1])
    await state.update_data(task_executor_id=task_executor_id)
    await state.set_state(SubmitTaskFSM.waiting_for_submission_file)
    await callback.message.answer("📎 Пришлите файл, который нужно отправить на проверку.")
    await callback.answer()


@router.message(SubmitTaskFSM.waiting_for_submission_file, F.document)
async def handle_submission_file(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    task_executor_id = data.get("task_executor_id")
    document = message.document

    # Генерация пути сохранения
    filename = f"submitted_{task_executor_id}_{document.file_name}"
    save_path = os.path.join(BASE_DOC_PATH, filename)

    # Загрузка файла через Bot API
    file = await bot.get_file(document.file_id)
    await bot.download_file(file.file_path, destination=save_path)

    # Обновляем статус и путь в БД
    relative_path = os.path.relpath(save_path, BASE_DOC_PATH)
    await mark_task_as_submitted(task_executor_id, relative_path)

    # Получаем специалиста
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

    await message.answer("✅ Задание отправлено на проверку специалисту.")
    await state.clear()


@router.callback_query(F.data.startswith("approve_task:"))
async def handle_task_approve(callback: CallbackQuery):
    task_executor_id = int(callback.data.split(":")[1])
    await update_task_status(task_executor_id, status="Принято")
    await callback.message.edit_caption(
        caption=callback.message.caption + "\n✅ Задание принято.",
        reply_markup=None
    )
    await callback.answer("Задание принято ✅")


@router.callback_query(F.data.startswith("revise_task:"))
async def handle_task_revision(callback: CallbackQuery, state: FSMContext):
    task_executor_id = int(callback.data.split(":")[1])

    # Сохраняем task_executor_id и сообщение, чтобы потом отредактировать caption
    await state.update_data(
        task_executor_id=task_executor_id,
        message_chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        original_caption=callback.message.caption or ""
    )

    await state.set_state(ReviewTaskFSM.waiting_for_revision_comment)

    await callback.message.answer("✏️ Введите комментарий, который будет отправлен исполнителю.")
    await callback.answer()

@router.message(ReviewTaskFSM.waiting_for_revision_comment)
async def handle_revision_comment(message: Message, state: FSMContext, bot: Bot):
    from database import update_task_status, get_executor_by_task_executor_id  # если ещё не импортированы

    data = await state.get_data()
    task_executor_id = data["task_executor_id"]
    comment = message.text.strip()

    # Обновляем статус
    await update_task_status(task_executor_id, status="Требует доработки")

    # Получаем исполнителя
    executor = await get_executor_by_task_executor_id(task_executor_id)
    if executor:
        await bot.send_message(
            chat_id=executor["executor_id"],
            text=(
                f"🔁 Задача #{task_executor_id} отправлена на доработку.\n\n"
                f"Комментарий специалиста:\n<b>{comment}</b>"
            ),
            parse_mode="HTML"
        )

    # Обновляем caption исходного сообщения у специалиста
    edited_caption = data["original_caption"] + "\n🔁 Отправлено на доработку."
    await bot.edit_message_caption(
        chat_id=data["message_chat_id"],
        message_id=data["message_id"],
        caption=edited_caption,
        reply_markup=None
    )

    await message.answer("✅ Комментарий отправлен исполнителю.")
    await state.clear()


@router.message(ReviewTaskFSM.waiting_for_revision_comment)
async def handle_revision_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    task_executor_id = data.get("task_executor_id")
    comment = message.text.strip()

    # Получаем исполнителя по task_executor_id
    from database import get_executor_by_task_executor_id
    executor = await get_executor_by_task_executor_id(task_executor_id)

    if executor:
        await message.bot.send_message(
            chat_id=executor["executor_id"],
            text=(
                f"🔁 Задача #{task_executor_id} отправлена на доработку.\n\n"
                f"Комментарий специалиста:\n<b>{comment}</b>"
            ),
            parse_mode="HTML"
        )
        await message.answer("✅ Комментарий отправлен исполнителю.")
    else:
        await message.answer("❗ Не удалось найти исполнителя по задаче.")

    await state.clear()

