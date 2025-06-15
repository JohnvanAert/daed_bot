from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, CallbackQuery, Document
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import os
from database import get_orders_by_specialist_id, save_calc_file_path_to_tasks, get_order_by_id

router = Router()

CALC_DOC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents", "temporary"))

class SubmitCalcFSM(StatesGroup):
    waiting_for_file = State()

# 📄 Панель расчетчика
@router.message(F.text == "📄 Мои расч.задачи")
async def show_calc_tasks(message: Message):
    orders = await get_orders_by_specialist_id(message.from_user.id, section="рс")

    if not orders:
        await message.answer("📭 У вас пока нет задач.")
        return

    for order in orders:
        caption = (
            f"📌 <b>{order['title']}</b>\n"
            f"📝 {order['description']}\n"
            f"📅 Дата: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Отправить результат", callback_data=f"calc_submit:{order['id']}")]
        ])

        await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)

# 📨 Ожидание файла от расчетчика
@router.callback_query(F.data.startswith("calc_submit:"))
async def handle_calc_submit(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(SubmitCalcFSM.waiting_for_file)
    await state.update_data(order_id=order_id)

    await callback.message.answer("📎 Прикрепите ZIP файл с результатами расчётов.")
    await callback.answer()

@router.message(SubmitCalcFSM.waiting_for_file, F.document)
async def receive_calc_file(message: Message, state: FSMContext, bot):
    from datetime import datetime

    data = await state.get_data()
    order_id = data["order_id"]
    document: Document = message.document

    if not document.file_name.lower().endswith(".zip"):
        await message.answer("❗️ Отправьте файл в формате ZIP.")
        return

    os.makedirs(CALC_DOC_PATH, exist_ok=True)

    filename = f"calc_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{document.file_name}"
    save_path = os.path.join(CALC_DOC_PATH, filename)

    file = await bot.get_file(document.file_id)
    await bot.download_file(file.file_path, destination=save_path)

    relative_path = os.path.relpath(save_path, os.path.join(CALC_DOC_PATH, ".."))
    await save_calc_file_path_to_tasks(order_id, relative_path)

    # Отправляем ГИПу
    order = await get_order_by_id(order_id)
    gip_id = order["gip_id"]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_calc:{order_id}"),
            InlineKeyboardButton(text="❌ Требует исправлений", callback_data=f"revise_calc:{order_id}")
        ]
    ])

    await bot.send_document(
        chat_id=gip_id,
        document=FSInputFile(save_path),
        caption=f"📩 Получен ZIP файл от расчётчика по заказу <b>{order['title']}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await message.answer("✅ Файл расчёта отправлен ГИПу.")
    await state.clear()
