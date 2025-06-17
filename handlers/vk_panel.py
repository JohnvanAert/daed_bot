from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile, Document
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import get_orders_by_specialist_id, save_vk_file_path_to_tasks, get_order_by_id
import os
from datetime import datetime

router = Router()
VK_TEMP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents", "temporary"))

class SubmitVkFSM(StatesGroup):
    waiting_for_file = State()

@router.message(F.text == "📄 Мои задачи по вк")
async def show_vk_tasks(message: Message):
    orders = await get_orders_by_specialist_id(message.from_user.id, section="вк")
    if not orders:
        await message.answer("📭 У вас пока нет задач.")
        return

    for order in orders:
        caption = f"📌 <b>{order['title']}</b>\n📝 {order['description']}\n📅 {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Отправить результат", callback_data=f"submit_vk:{order['id']}")]
        ])
        await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)

@router.callback_query(F.data.startswith("submit_vk:"))
async def handle_vk_submit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubmitVkFSM.waiting_for_file)
    await state.update_data(order_id=int(callback.data.split(":")[1]))
    await callback.message.answer("📎 Прикрепите ZIP файл по ВК/НВК.")
    await callback.answer()

@router.message(SubmitVkFSM.waiting_for_file, F.document)
async def receive_vk_file(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    order_id = data["order_id"]
    document = message.document

    if not document.file_name.lower().endswith(".zip"):
        await message.answer("❗️ Отправьте файл в формате ZIP.")
        return

    os.makedirs(VK_TEMP_PATH, exist_ok=True)
    filename = f"vk_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{document.file_name}"
    save_path = os.path.join(VK_TEMP_PATH, filename)

    file = await bot.get_file(document.file_id)
    await bot.download_file(file.file_path, destination=save_path)
    relative_path = os.path.relpath(save_path, os.path.join(VK_TEMP_PATH, ".."))
    await save_vk_file_path_to_tasks(order_id, relative_path)

    order = await get_order_by_id(order_id)
    gip_id = order["gip_id"]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_vk:{order_id}"),
         InlineKeyboardButton(text="❌ Исправить", callback_data=f"revise_vk:{order_id}")]
    ])

    await bot.send_document(
        chat_id=gip_id,
        document=FSInputFile(save_path),
        caption=f"📩 ZIP от ВК-специалиста по заказу <b>{order['title']}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await message.answer("✅ Файл отправлен ГИПу.")
    await state.clear()
