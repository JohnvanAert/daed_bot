from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
import os
from database import get_order_by_id, get_specialist_by_section, create_task
from datetime import date, timedelta
import tempfile
import shutil

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

    # Абсолютный путь к папке проекта
    doc_path = os.path.abspath(os.path.join("..", "psdbot", order["document_url"]))

    if not os.path.exists(doc_path):
        await message.answer("❗ Не удалось найти документ заказа.")
        await state.clear()
        return

    # Проверим, если это папка — архивируем
    if os.path.isdir(doc_path):
        temp_dir = tempfile.gettempdir()
        zip_name = f"{order['title'].replace(' ', '_')}_for_EP.zip"
        zip_path = os.path.join(temp_dir, zip_name)

        try:
            shutil.make_archive(base_name=zip_path.replace(".zip", ""), format='zip', root_dir=doc_path)
        except Exception as e:
            await message.answer(f"❗ Ошибка при создании архива: {e}")
            await state.clear()
            return
    else:
        zip_path = doc_path  # если это не папка, то сразу путь к файлу

    caption = (
        f"🆕 Новый заказ для выполнения ЭП:\n"
        f"📌 <b>{order['title']}</b>\n"
        f"📝 {order['description']}\n"
        f"📅 Дедлайн: {deadline_days} дней\n"
        f"💬 Комментарий от ГИПа: {comment}"
    )

    try:
        await message.bot.send_document(
            chat_id=specialist["telegram_id"],
            document=FSInputFile(zip_path),
            caption=caption,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await message.answer(f"❗ Ошибка при отправке файла: {e}")
        await state.clear()
        return
    finally:
        # Удалим временный .zip файл, если он был создан
        if os.path.isdir(doc_path) and os.path.exists(zip_path):
            os.remove(zip_path)

    await message.answer("✅ Заказ успешно передан специалисту по ЭП.")
    await state.clear()