from aiogram import Router, F
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_expert_tasks

router = Router()

@router.message(F.text == "📂 Мои заказы")
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

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📎 Прикрепить замечания", callback_data=f"send_note:{task['task_id']}")]
        ])

        doc_path = f"clientbot/documents/{task['document_url']}"
        try:
            await message.answer_document(
                document=FSInputFile(doc_path),
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception as e:
            await message.answer(f"⚠️ Файл не найден по пути: {doc_path}")
