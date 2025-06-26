from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, CallbackQuery, Document
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import os
from datetime import datetime
from database import get_orders_by_specialist_id, save_genplan_file_path_to_tasks, get_order_by_id

router = Router()

GENPLAN_TEMP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot", "documents", "temporary"))

class SubmitGenplanFSM(StatesGroup):
    waiting_for_file = State()

# 📄 Панель генпланиста
@router.message(F.text == "📄 Мои задачи по гп")
async def show_genplan_tasks(message: Message):
    orders = await get_orders_by_specialist_id(message.from_user.id, section="гп")
    
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
            [InlineKeyboardButton(text="📤 Отправить результат", callback_data=f"genplan_submit:{order['id']}")]
        ])

        await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)

# 📨 Обработка callback от генпланиста
@router.callback_query(F.data.startswith("genplan_submit:"))
async def handle_genplan_submit(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(SubmitGenplanFSM.waiting_for_file)
    await state.update_data(order_id=order_id)

    await callback.message.answer("📎 Прикрепите ZIP файл по разделу Генплан.")
    await callback.answer()

# 💾 Получение ZIP файла от генпланиста
@router.message(SubmitGenplanFSM.waiting_for_file, F.document)
async def receive_genplan_file(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    order_id = data["order_id"]
    document: Document = message.document

    if not document.file_name.lower().endswith(".zip"):
        await message.answer("❗️ Отправьте файл в формате ZIP.")
        return

    # ✅ Используем общую временную папку
    os.makedirs(GENPLAN_TEMP_PATH, exist_ok=True)

    # 🧾 Генерация имени файла
    filename = f"genplan_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{document.file_name}"
    save_path = os.path.join(GENPLAN_TEMP_PATH, filename)

    # ⬇️ Скачиваем файл
    file = await bot.get_file(document.file_id)
    await bot.download_file(file.file_path, destination=save_path)

    # 💾 Сохраняем относительный путь
    relative_path = os.path.relpath(save_path, os.path.join(GENPLAN_TEMP_PATH, ".."))
    await save_genplan_file_path_to_tasks(order_id, relative_path)

    # 📬 Получаем ГИПа
    order = await get_order_by_id(order_id)
    gip_id = order["gip_id"]

    # Кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_genplan:{order_id}"),
            InlineKeyboardButton(text="❌ Требует исправлений", callback_data=f"revise_genplan:{order_id}")
        ]
    ])

    # Отправка ГИПу
    await bot.send_document(
        chat_id=gip_id,
        document=FSInputFile(save_path),
        caption=f"📩 Получен ZIP файл от генпланиста по заказу <b>{order['title']}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await message.answer("✅ Файл по Генплану отправлен ГИПу.")
    await state.clear()