from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile, Document
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import get_orders_by_specialist_id, save_ovik_file_path_to_tasks, get_order_by_id

import os
from datetime import datetime

router = Router()

OVIK_TEMP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents", "temporary"))

class SubmitOvikFSM(StatesGroup):
    waiting_for_file = State()

# 📄 Панель ОВиК
@router.message(F.text == "📄 Мои задачи по тс/ов")
async def show_ovik_tasks(message: Message):
    orders = await get_orders_by_specialist_id(message.from_user.id, section="овик")
    if not orders:
        await message.answer("📭 У вас пока нет задач.")
        return

    for order in orders:
        caption = (
            f"📌 <b>{order['title']}</b>\n"
            f"📝 {order['description']}\n"
            f"📅 {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Отправить результат", callback_data=f"submit_ovik:{order['id']}")]
        ])
        await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)

# 🔄 Ожидание загрузки файла
@router.callback_query(F.data.startswith("submit_ovik:"))
async def handle_ovik_submit(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(SubmitOvikFSM.waiting_for_file)
    await state.update_data(order_id=order_id)
    await callback.message.answer("📎 Прикрепите ZIP файл с результатами по ОВиК.")
    await callback.answer()

# 📥 Получение файла
@router.message(SubmitOvikFSM.waiting_for_file, F.document)
async def receive_ovik_file(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    order_id = data["order_id"]
    document: Document = message.document

    if not document.file_name.lower().endswith(".zip"):
        await message.answer("❗️ Пожалуйста, отправьте файл в формате ZIP.")
        return

    os.makedirs(OVIK_TEMP_PATH, exist_ok=True)
    filename = f"ovik_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{document.file_name}"
    save_path = os.path.join(OVIK_TEMP_PATH, filename)

    file = await bot.get_file(document.file_id)
    await bot.download_file(file.file_path, destination=save_path)

    relative_path = os.path.relpath(save_path, os.path.join(OVIK_TEMP_PATH, ".."))
    await save_ovik_file_path_to_tasks(order_id, relative_path)

    # Отправка ГИПу
    order = await get_order_by_id(order_id)
    gip_id = order["gip_id"]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_ovik:{order_id}"),
            InlineKeyboardButton(text="❌ Требует исправлений", callback_data=f"revise_ovik:{order_id}")
        ]
    ])

    await bot.send_document(
        chat_id=gip_id,
        document=FSInputFile(save_path),
        caption=f"📩 Получен ZIP файл от ОВиК-специалиста по заказу <b>{order['title']}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await message.answer("✅ Файл отправлен ГИПу.")
    await state.clear()
