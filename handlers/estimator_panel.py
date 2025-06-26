from aiogram import Router, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, FSInputFile, Document
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import (
    get_orders_by_specialist_id,
    get_order_by_id,
    save_estimate_file_path_to_tasks
)
from datetime import datetime
import os

router = Router()

ESTIMATE_TEMP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot", "documents", "temporary"))

class SubmitEstimateFSM(StatesGroup):
    waiting_for_file = State()

# 📄 Панель Сметчика
@router.message(F.text == "📄 Мои задачи по смете")
async def show_estimate_tasks(message: Message):
    orders = await get_orders_by_specialist_id(message.from_user.id, section="смета")
    if not orders:
        await message.answer("📭 У вас пока нет задач.")
        return

    for order in orders:
        order_id = order["id"]
        status = order["status"]
        caption = (
            f"📌 <b>{order['title']}</b>\n"
            f"📝 {order['description']}\n"
            f"📅 Дата: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )

        buttons = []

        buttons.append(InlineKeyboardButton(text="📤 Отправить на проверку смету", callback_data=f"submit_estimate:{order_id}"))

        keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])
        await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)

# 📨 Ожидание ZIP от сметчика
@router.callback_query(F.data.startswith("submit_estimate:"))
async def handle_estimate_submit(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(SubmitEstimateFSM.waiting_for_file)
    await state.update_data(order_id=order_id)

    await callback.message.answer("📎 Прикрепите ZIP файл по смете.")
    await callback.answer()

# 💾 Обработка ZIP файла от сметчика
@router.message(SubmitEstimateFSM.waiting_for_file, F.document)
async def receive_estimate_file(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    order_id = data["order_id"]
    document: Document = message.document

    if not document.file_name.lower().endswith(".zip"):
        await message.answer("❗️ Отправьте файл в формате ZIP.")
        return

    os.makedirs(ESTIMATE_TEMP_PATH, exist_ok=True)

    filename = f"estimate_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{document.file_name}"
    save_path = os.path.join(ESTIMATE_TEMP_PATH, filename)

    file = await bot.get_file(document.file_id)
    await bot.download_file(file.file_path, destination=save_path)

    relative_path = os.path.relpath(save_path, os.path.join(ESTIMATE_TEMP_PATH, ".."))
    await save_estimate_file_path_to_tasks(order_id, relative_path)

    order = await get_order_by_id(order_id)
    gip_id = order["gip_id"]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_estimate:{order_id}"),
            InlineKeyboardButton(text="❌ Исправить", callback_data=f"revise_estimate:{order_id}")
        ]
    ])

    await bot.send_document(
        chat_id=gip_id,
        document=FSInputFile(save_path),
        caption=f"📩 Получен ZIP файл от сметчика по заказу <b>{order['title']}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await message.answer("✅ Файл сметы отправлен ГИПу.")
    await state.clear()
