from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from database import get_all_orders, get_customer_telegram_id
import os
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram import Bot
from database import delete_order 

router = Router()
BASE_DOC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents"))

async def send_orders_to(recipient, send_method):
    orders = await get_all_orders()

    if not orders:
        await send_method("📭 Пока нет доступных заказов.")
        return
    
    bot = recipient.bot

    for order in orders:
        text = (
            f"📌 <b>{order['title']}</b>\n"
            f"📝 {order['description']}\n"
            f"👤 Заказчик ID: {order['customer_id']}\n"
            f"📅 Создан: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"order_accept:{order['id']}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"order_reject:{order['id']}"),
                InlineKeyboardButton(text="✏️ Исправить", callback_data=f"order_edit:{order['id']}")
            ]
        ])
        document_path = os.path.abspath(os.path.join(BASE_DOC_PATH, os.path.relpath(order["document_url"], "documents")))

        if os.path.exists(document_path):
            doc = FSInputFile(document_path)
            await bot.send_document(chat_id=recipient.chat.id, document=doc, caption=text, reply_markup=keyboard)
        else:
            await send_method(f"{text}\n\n⚠️ Документ не найден по пути: {document_path}", reply_markup=keyboard)

@router.callback_query(F.data.startswith("order_accept:"))
async def accept_order(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    await callback.answer("Заказ принят ✅", show_alert=True)
    await callback.message.edit_reply_markup()  # Удалим кнопки после действия


@router.callback_query(F.data.startswith("order_reject:"))
async def reject_order(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])

    orders = await get_all_orders()
    order = next((o for o in orders if o["id"] == order_id), None)

    if order:
        # Удаляем файл
        document_path = os.path.abspath(os.path.join(BASE_DOC_PATH, os.path.relpath(order["document_url"], "documents")))
        if os.path.exists(document_path):
            try:
                os.remove(document_path)
            except Exception as e:
                print(f"Ошибка при удалении файла: {e}")

        # Уведомляем заказчика
        customer_telegram_id = await get_customer_telegram_id(order["customer_id"])
        if customer_telegram_id:
            await callback.bot.send_message(
                chat_id=customer_telegram_id,
                text=(
                    f"🚫 Ваш заказ был отклонён.\n\n"
                    f"📌 <b>{order['title']}</b>\n"
                    f"📝 {order['description']}\n"
                    f"📅 Создан: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
                )
            )

        await delete_order(order_id)

    await callback.answer("Заказ отклонён и удалён ❌", show_alert=True)
    await callback.message.edit_text("❌ Заказ был отклонён и удалён.")
    
@router.callback_query(F.data.startswith("order_edit:"))
async def edit_order(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    await callback.answer("Открыт режим исправления ✏️", show_alert=True)
    await callback.message.edit_reply_markup()

@router.message(F.text == "📦 Заказы")
async def show_orders_message(message: Message):
    await send_orders_to(message, message.answer)

@router.callback_query(F.data == "view_orders")
async def show_orders_callback(callback: CallbackQuery):
    await send_orders_to(callback.message, callback.message.answer)
