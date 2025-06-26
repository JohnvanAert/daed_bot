from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
import os
from database import get_order_by_id, get_specialist_by_section, create_task
from datetime import date, timedelta

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
        await message.answer("❗ Пожалуйста, введите число (дедлайн в днях):")
        return
    await state.update_data(deadline=int(message.text))
    await state.set_state(AssignSketchFSM.waiting_for_comment)
    await message.answer("✏️ Введите комментарий для эскизчика:")

@router.message(AssignSketchFSM.waiting_for_comment)
async def send_to_ep_specialist(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    deadline_days = data["deadline"]
    comment = message.text.strip()

    order = await get_order_by_id(order_id)
    specialist = await get_specialist_by_section("эп")

    if not specialist:
        await message.answer("❗ Специалист по ЭП не найден.")
        await state.clear()
        return
    deadline_date = date.today() + timedelta(days=deadline_days)
    await create_task(order_id, "эп", comment, deadline_date, specialist["telegram_id"], "Разработка ЭП")

    doc_path = os.path.abspath(os.path.join("..", "psdbot", order["document_url"]))
    if not os.path.exists(doc_path):
        await message.answer("❗ Не удалось найти документ заказа.")
        await state.clear()
        return

    caption = (
        f"🆕 Новый заказ для выполнения ЭП:\n"
        f"📌 <b>{order['title']}</b>\n"
        f"📝 {order['description']}\n"
        f"📅 Дедлайн: {deadline_days} дней\n"
        f"💬 Комментарий от ГИПа: {comment}"
    )

    await message.bot.send_document(
        chat_id=specialist["telegram_id"],
        document=FSInputFile(doc_path),
        caption=caption,
        parse_mode=ParseMode.HTML
    )

    await message.answer("✅ Заказ успешно передан специалисту по ЭП.")
    await state.clear()
