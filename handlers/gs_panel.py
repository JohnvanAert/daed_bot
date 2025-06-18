from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile, Document
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import get_orders_by_specialist_id, save_gs_file_path_to_tasks, get_order_by_id
import os
from datetime import datetime

router = Router()
VGS_TEMP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents", "temporary"))

class SubmitVgsFSM(StatesGroup):
    waiting_for_file = State()

@router.message(F.text == "📄 Мои задачи по гс")
async def show_vgs_tasks(message: Message):
    orders = await get_orders_by_specialist_id(message.from_user.id, section="гс")
    if not orders:
        await message.answer("📭 У вас пока нет задач.")
        return

    for order in orders:
        caption = f"📌 <b>{order['title']}</b>\n📝 {order['description']}\n📅 {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Отправить результат", callback_data=f"submit_vgs:{order['id']}")]
        ])
        await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)

@router.callback_query(F.data.startswith("submit_vgs:"))
async def handle_vgs_submit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubmitVgsFSM.waiting_for_file)
    await state.update_data(order_id=int(callback.data.split(":")[1]))
    await callback.message.answer("📎 Прикрепите ZIP файл по ВГС/НГС.")
    await callback.answer()

@router.message(SubmitVgsFSM.waiting_for_file, F.document)
async def receive_vgs_file(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    order_id = data["order_id"]
    document = message.document

    if not document.file_name.lower().endswith(".zip"):
        await message.answer("❗️ Отправьте файл в формате ZIP.")
        return

    os.makedirs(VGS_TEMP_PATH, exist_ok=True)
    filename = f"vgs_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{document.file_name}"
    save_path = os.path.join(VGS_TEMP_PATH, filename)

    file = await bot.get_file(document.file_id)
    await bot.download_file(file.file_path, destination=save_path)
    relative_path = os.path.relpath(save_path, os.path.join(VGS_TEMP_PATH, ".."))
    await save_gs_file_path_to_tasks(order_id, relative_path)

    order = await get_order_by_id(order_id)
    gip_id = order["gip_id"]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_gs:{order_id}"),
         InlineKeyboardButton(text="❌ Исправить", callback_data=f"revise_gs:{order_id}")]
    ])

    await bot.send_document(
        chat_id=gip_id,
        document=FSInputFile(save_path),
        caption=f"📩 ZIP от ВГС-специалиста по заказу <b>{order['title']}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await message.answer("✅ Файл отправлен ГИПу.")
    await state.clear()
