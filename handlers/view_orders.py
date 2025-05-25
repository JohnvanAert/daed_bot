from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from database import get_all_orders, get_customer_telegram_id
import os
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram import Bot
from database import delete_order, update_order_status
from states.states import EditOrder
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

load_dotenv()
router = Router()
BASE_DOC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents"))
# Initialize the client bot with the token from environment variables
client_bot = Bot(
    token=os.getenv("CLIENT_BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

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

        if order["status"] == "queue":
                keyboard_buttons = [[
                    InlineKeyboardButton(text="✅ Принять", callback_data=f"order_accept:{order['id']}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"order_reject:{order['id']}"),
                    InlineKeyboardButton(text="✏️ Исправить", callback_data=f"order_edit:{order['id']}")
                ]]
        elif order["status"] == "approved":
                keyboard_buttons = [[
                    InlineKeyboardButton(text="📤 Передать ЭП", callback_data=f"assign_sketch:{order['id']}")
                ]]
        else:
                keyboard_buttons = []

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        document_path = os.path.abspath(os.path.join(BASE_DOC_PATH, os.path.relpath(order["document_url"], "documents")))

        if os.path.exists(document_path):
            doc = FSInputFile(document_path)
            await bot.send_document(chat_id=recipient.chat.id, document=doc, caption=text, reply_markup=keyboard)
        else:
            await send_method(f"{text}\n\n⚠️ Документ не найден по пути: {document_path}", reply_markup=keyboard)

@router.callback_query(F.data.startswith("order_accept:"))
async def accept_order(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    await update_order_status(order_id, "approved")

    await callback.answer("Заказ принят ✅", show_alert=True)
    await callback.message.answer("✅ Заказ был принят. Теперь можно передать его эскизчику.")




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
async def edit_order(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(EditOrder.waiting_for_comment)
    await state.update_data(order_id=order_id)
    await callback.answer()
    await callback.message.answer("✏️ Введите комментарий, который будет отправлен заказчику для исправления заказа:")


@router.message(EditOrder.waiting_for_comment)
async def process_edit_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    comment = message.text

    orders = await get_all_orders()
    order = next((o for o in orders if o["id"] == order_id), None)

    if not order:
        await message.answer("❗ Заказ не найден.")
        await state.clear()
        return

    customer_telegram_id = await get_customer_telegram_id(order["customer_id"])
    if customer_telegram_id:
        fix_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Загрузить исправленный архив", callback_data=f"start_fix:{order['id']}")]
        ])
        await client_bot.send_message(
            chat_id=customer_telegram_id,
            text=(
                f"✏️ Ваш заказ требует исправлений.\n"
                f"<b>Комментарий от ГИПа:</b> {comment}\n\n"
                f"📌 <b>{order['title']}</b>\n"
                f"📝 {order['description']}\n"
                f"📅 Создан: {order['created_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
                f"Пожалуйста, отправьте обновлённый архив."
            ),
            reply_markup=fix_kb
        )

    await message.answer("Комментарий отправлен заказчику ✉️")
    await state.clear()

@router.message(F.text == "📦 Заказы")
async def show_orders_message(message: Message):
    await send_orders_to(message, message.answer)

@router.callback_query(F.data == "view_orders")
async def show_orders_callback(callback: CallbackQuery):
    await send_orders_to(callback.message, callback.message.answer)
