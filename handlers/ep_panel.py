from aiogram import Router, F
from aiogram.types import Message, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Document
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import get_orders_by_specialist_id, get_order_by_id
import os

router = Router()
BASE_DOC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents"))

class SubmitEpFSM(StatesGroup):
    waiting_for_file = State()

def get_gip_review_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Передать заказчику", callback_data=f"gip_approve:{order_id}"),
            InlineKeyboardButton(text="❌ Требует исправлений", callback_data=f"gip_reject:{order_id}")
        ]
    ])

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
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📤 Отправить на проверку", callback_data=f"submit_ep:{order['id']}")]
            ])
            await message.answer_document(FSInputFile(doc_path), caption=caption, reply_markup=keyboard)
        else:
            await message.answer(f"⚠️ Документ не найден: {order['title']}")

# --- Нажатие на кнопку ---
@router.callback_query(F.data.startswith("submit_ep:"))
async def handle_submit_ep(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(SubmitEpFSM.waiting_for_file)
    await state.update_data(order_id=order_id)
    await callback.answer()
    await callback.message.answer("📎 Отправьте PDF файл ЭП для передачи на проверку ГИПу:")

# --- Ожидание файла ---
@router.message(SubmitEpFSM.waiting_for_file, F.document)
async def receive_ep_document(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")

    document: Document = message.document
    if not document.file_name.lower().endswith(".pdf"):
        await message.answer("❗ Пожалуйста, отправьте файл в формате PDF.")
        return

    # Получаем заказ, чтобы найти ГИПа
    order = await get_order_by_id(order_id)
    gip_telegram_id = order["gip_id"]

    await message.bot.send_document(
        chat_id=gip_telegram_id,
        document=document.file_id,
        caption=f"📩 Получен файл ЭП от специалиста по заказу: <b>{order['title']}</b>",
        parse_mode="HTML",
        reply_markup=get_gip_review_keyboard(order['id'])
    )

    await message.answer("✅ ЭП отправлен ГИПу на проверку.")
    await state.clear()