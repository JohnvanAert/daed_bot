from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_order_by_id, get_specialist_by_section, get_customer_telegram_id, get_all_orders
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram import Bot
import os

router = Router()

class AssignSketchFSM(StatesGroup):
    waiting_for_deadline = State()
    waiting_for_comment = State()

@router.callback_query(F.data.startswith("assign_sketch:"))
async def ask_deadline(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(AssignSketchFSM.waiting_for_deadline)
    await state.update_data(order_id=order_id)
    await callback.answer()
    await callback.message.answer("📆 Введите дедлайн в днях для эскизчика:")

@router.message(AssignSketchFSM.waiting_for_deadline)
async def receive_deadline(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗ Пожалуйста, введите дедлайн числом (в днях):")
        return

    await state.update_data(deadline=int(message.text))
    await state.set_state(AssignSketchFSM.waiting_for_comment)
    await message.answer("✏️ Введите комментарий для эскизчика:")

@router.message(AssignSketchFSM.waiting_for_comment)
async def send_to_sketch_specialist(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    deadline = data["deadline"]
    comment = message.text.strip()

    order = await get_order_by_id(order_id)
    specialist_id = await get_specialist_by_section("эп")

    if not specialist_id:
        await message.answer("❗ Специалист по разделу ЭП не назначен.")
        await state.clear()
        return

    doc_path = os.path.abspath(os.path.join("..", "clientbot", order["document_url"]))
    if not os.path.exists(doc_path):
        await message.answer("❗ Не удалось найти документ заказа.")
        await state.clear()
        return

    caption = (
        f"🆕 Новый заказ для выполнения ЭП:"
        f"📌 <b>{order['title']}</b>"
        f"📝 {order['description']}"
        f"📅 Дедлайн: {deadline} дней"
        f"💬 Комментарий от ГИПа: {comment}"
    )

    await message.bot.send_document(
        chat_id=specialist_id,
        document=FSInputFile(doc_path),
        caption=caption,
        parse_mode=ParseMode.HTML
    )

    await message.answer("✅ Заказ успешно передан эскизчику.")
    await state.clear()
