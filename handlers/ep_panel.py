from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from database import get_orders_by_specialist_id
import os

router = Router()
BASE_DOC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents"))

@router.message(F.text == "📄 Мои заказы")
async def show_ep_orders(message: Message):
    orders = await get_orders_by_specialist_id(message.from_user.id, section="эп")

    if not orders:
        await message.answer("📭 У вас пока нет назначенных заказов.")
        return

    for order in orders:
        doc_path = os.path.abspath(os.path.join(BASE_DOC_PATH, os.path.relpath(order["document_url"], "documents")))

        if os.path.exists(doc_path):
            caption = (
                f"📌 <b>{order['title']}</b>\n"
                f"📝 {order['description']}\n"
                f"📅 Создан: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
            )
            await message.answer_document(FSInputFile(doc_path), caption=caption)
        else:
            await message.answer(f"⚠️ Документ не найден: {order['title']}")
