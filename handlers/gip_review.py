from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_order_by_id, get_customer_telegram_id, get_specialist_by_section, update_order_status, create_task, get_specialist_by_order_and_section, get_ar_task_document, update_task_status
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import FSInputFile
import os
from aiogram.types import Document
from datetime import date, timedelta
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from states.ar_correction import ReviewArCorrectionFSM
import shutil
from states.task_states import AssignARFSM
load_dotenv()
router = Router()
# Initialize the client bot with the token from environment variables
client_bot = Bot(
    token=os.getenv("CLIENT_BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
class ReviewCorrectionFSM(StatesGroup):
    waiting_for_comment = State()
    waiting_for_fixed_file = State()
    waiting_for_customer_question = State()
    waiting_for_customer_zip = State()
    waiting_for_customer_error_comment = State()

@router.callback_query(F.data.startswith("gip_approve:"))
async def handle_gip_approval(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    customer_id = await get_customer_telegram_id(order["customer_id"])
    await update_order_status(order_id, "receive_ird")
    ep_file_path = os.path.abspath(os.path.join("..", "clientbot", order["document_url"]))
    
    if os.path.exists(ep_file_path):
        caption = (
            f"📦 По вашему заказу <b>{order['title']}</b> выполнен раздел ЭП.\n"
            f"📄 Пожалуйста, предоставьте следующие документы:\n"
            f"🔷 ГПЗУ\n🔷 ТУ\n🔷 ПДП"
        )

        # ✅ Отправляем через client_bot
        await client_bot.send_document(
            chat_id=customer_id,
            document=FSInputFile(ep_file_path),
            caption=caption
        )
    else:
        await callback.message.answer("❗ Файл ЭП не найден.")
        return

    await callback.message.edit_reply_markup()
    await callback.message.answer("✅ Заказ передан заказчику.")
    await callback.answer("Передано заказчику ✅", show_alert=True)

@router.callback_query(F.data.startswith("gip_reject:"))
async def handle_gip_rejection(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewCorrectionFSM.waiting_for_comment)
    await state.update_data(order_id=order_id)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❗ Напишите комментарий с замечаниями по ЭП:")

@router.message(ReviewCorrectionFSM.waiting_for_comment)
async def send_correction_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    comment = message.text.strip()
    order = await get_order_by_id(order_id)

    specialist = await get_specialist_by_section("эп")
    if not specialist:
        await message.answer("❗ Специалист не найден.")
        await state.clear()
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Прикрепить исправленный файл", callback_data=f"resubmit_ep:{order['id']}")]
    ])
    await message.bot.send_message(
        chat_id=specialist["telegram_id"],
        text=(
            f"❗ <b>Замечания по ЭП</b> по заказу: <b>{order['title']}</b>\n\n"
            f"{comment}"
        ),
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await message.answer("✉️ Замечания отправлены специалисту.")
    await state.clear()


@router.callback_query(F.data.startswith("resubmit_ep:"))
async def handle_resubmit_ep(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewCorrectionFSM.waiting_for_fixed_file)
    await state.update_data(order_id=order_id)
    await callback.message.answer("📎 Прикрепите исправленный PDF файл ЭП:")
    await callback.answer()

@router.message(ReviewCorrectionFSM.waiting_for_fixed_file, F.document)
async def receive_fixed_ep(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    order = await get_order_by_id(order_id)

    document: Document = message.document
    if not document.file_name.lower().endswith(".pdf"):
        await message.answer("❗ Пожалуйста, прикрепите файл в формате PDF.")
        return

    # Отправим ГИПу
    await message.bot.send_document(
        chat_id=order["gip_id"],
        document=document,
        caption=f"📩 Исправленный ЭП по заказу: <b>{order['title']}</b>",
        parse_mode="HTML"
    )

    await message.answer("✅ Исправленный файл отправлен ГИПу на проверку.")
    await state.clear()


@router.callback_query(F.data.startswith("docs_error:"))
async def handle_docs_error(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewCorrectionFSM.waiting_for_customer_error_comment)
    await state.update_data(order_id=order_id)
    await callback.message.answer("✏️ Напишите, пожалуйста, комментарий для заказчика (что не так с документами):")
    await callback.answer()

@router.message(ReviewCorrectionFSM.waiting_for_customer_error_comment)
async def send_docs_error_to_customer(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    order = await get_order_by_id(order_id)
    customer_id = await get_customer_telegram_id(order["customer_id"])

    comment = message.text.strip()

    # 🔄 Обновим статус заказа
    await update_order_status(order_id, "pending_correction")

    await client_bot.send_message(
        chat_id=customer_id,
        text=(
            f"❗ <b>Ошибка в документах</b> по заказу <b>{order['title']}</b>:\n\n"
            f"{comment}"
        ),
        parse_mode="HTML"
    )

    await message.answer("✉️ Комментарий отправлен заказчику.")
    await state.clear()


@router.callback_query(F.data.startswith("docs_accept:"))
async def handle_docs_accept(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])

    # Обновим статус, например: ep_documents_accepted
    await update_order_status(order_id, "ep_documents_accepted")

    # Изменим caption и кнопку
    original_caption = callback.message.caption or ""
    updated_caption = original_caption + "\n\n✅ Документы заказчика приняты. Теперь можно передать заказ специалисту по АР."

    new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Передать АР", callback_data=f"assign_ar:{order_id}")]
    ])
    await update_task_status(order_id=order_id, section="эп", new_status="Сделано")
    await callback.message.edit_caption(caption=updated_caption, reply_markup=new_keyboard)
    await callback.answer("Документы приняты ✅", show_alert=True)


@router.message(ReviewCorrectionFSM.waiting_for_customer_zip, F.document)
async def receive_customer_zip(message: Message, state: FSMContext):
    document = message.document

    if not document.file_name.lower().endswith(".zip"):
        await message.answer("❗ Пожалуйста, отправьте архив в формате .zip")
        return

    data = await state.get_data()
    order = await get_order_by_id(data["order_id"])

    for user_id in [order["gip_id"], (await get_specialist_by_section("эп"))["telegram_id"]]:
        await message.bot.send_document(
            chat_id=user_id,
            document=document.file_id,  # <-- важно: здесь используется document.file_id
            caption=f"📥 Получен исправленный архив от заказчика по заказу: <b>{order['title']}</b>",
            parse_mode="HTML"
        )
    
    await message.answer("✅ Спасибо! ZIP-файл передан исполнителям.")
    await state.clear()

@router.callback_query(F.data.startswith("docs_error:"))
async def handle_docs_error(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewCorrectionFSM.waiting_for_customer_error_comment)
    await state.update_data(order_id=order_id)
    await callback.message.answer("✏️ Укажите, что не так с ИРД:")
    await callback.answer()


@router.message(ReviewCorrectionFSM.waiting_for_customer_error_comment)
async def handle_docs_error_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    order = await get_order_by_id(order_id)
    customer_id = await get_customer_telegram_id(order["customer_id"])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📎 Отправить исправленные ИРД", callback_data=f"send_ird:{order_id}")]
    ])

    await client_bot.send_message(
        chat_id=customer_id,
        text=f"❗ <b>Ошибка в ИРД</b> по заказу <b>{order['title']}</b>:\n\n{message.text.strip()}",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await message.answer("✉️ Комментарий отправлен заказчику.")
    await state.clear()

@router.callback_query(F.data.startswith("assign_ar:"))
async def handle_assign_ar(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    specialist = await get_specialist_by_section("ар")

    if not specialist:
        await callback.message.answer("❗️ Специалист по АР не найден.")
        return

    # Сохраняем данные в FSM
    await state.set_state(AssignARFSM.waiting_for_deadline)
    await state.update_data(
        order_id=order_id,
        specialist_id=specialist["telegram_id"],
        description=order["description"],
        title=order["title"],
        document_url=order["document_url"]
    )

    await callback.message.answer("📅 Введите количество дней до дедлайна (например: 5):")
    await callback.answer()
    
@router.message(AssignARFSM.waiting_for_deadline)
async def receive_ar_deadline_days(message: Message, state: FSMContext):
    from datetime import datetime, timedelta

    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗️ Введите положительное число — количество дней до дедлайна.")
        return

    deadline = datetime.today().date() + timedelta(days=days)
    await state.update_data(deadline=deadline, days=days)
    await state.set_state(AssignARFSM.waiting_for_description)
    await message.answer("📝 Теперь введите описание задачи по АР:")


@router.message(AssignARFSM.waiting_for_description)
async def receive_ar_description(message: Message, state: FSMContext):
    from aiogram.types import FSInputFile
    import os

    description = message.text.strip()
    data = await state.get_data()

    order_id = data["order_id"]
    specialist_id = data["specialist_id"]
    title = data["title"]
    document_url = data["document_url"]
    deadline = data["deadline"]
    days = data["days"]

    await update_order_status(order_id, "assigned_ar")
    await create_task(
        order_id=order_id,
        section="ар",
        description=description,
        deadline=deadline,
        specialist_id=specialist_id,
        status="Разработка АР"
    )

    doc_path = os.path.abspath(os.path.join("..", "clientbot", document_url))
    if not os.path.exists(doc_path):
        await message.answer("❗️ Не удалось найти файл заказа.")
        await state.clear()
        return

    caption = (
        f"📄 Новый заказ на разработку АР:\n"
        f"📌 <b>{title}</b>\n"
        f"📝 {description}\n"
        f"📅 Дедлайн через {days} дн. ({deadline.strftime('%d.%m.%Y')})\n"
        f"💬 Комментарий: Передан заказ на разработку АР"
    )

    await message.bot.send_document(
        chat_id=specialist_id,
        document=FSInputFile(doc_path),
        caption=caption,
        parse_mode="HTML"
    )

    await message.answer("✅ Задание передано специалисту по АР.")
    await state.clear()


@router.callback_query(F.data.startswith("gip_ar_approve:"))
async def handle_gip_ar_approval(callback: CallbackQuery):
    import shutil
    import os

    order_id = int(callback.data.split(":")[1])
    await update_order_status(order_id, "approved_ar")
    
    order = await get_order_by_id(order_id)
    if not order["document_url"]:
        await callback.message.answer("❗️ У заказа не указан путь document_url.")
        return

    # Путь до clientbot
    BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot"))

    # Путь к папке проекта
    relative_path = order["document_url"]  # documents/ЖК_Адал/test (1).zip
    project_folder_rel = os.path.dirname(relative_path)  # documents/ЖК_Адал
    PROJECT_ABS_PATH = os.path.join(BASE_PATH, project_folder_rel)

    if not os.path.exists(PROJECT_ABS_PATH):
        await callback.message.answer(f"❗️ Папка проекта не найдена: {PROJECT_ABS_PATH}")
        return

    # Путь к файлу от АР-специалиста (из tasks)
    relative_file_path = await get_ar_task_document(order_id)
    if not relative_file_path:
        await callback.message.answer("❗️ Не найден АР-файл в tasks.document_url.")
        return

    SOURCE_ABS_PATH = os.path.join(BASE_PATH, "documents", relative_file_path)
    FINAL_PATH = os.path.join(PROJECT_ABS_PATH, "ar_files.zip")

    try:
        shutil.move(SOURCE_ABS_PATH, FINAL_PATH)
    except Exception as e:
        await callback.message.answer(f"❗️ Ошибка при перемещении: {e}")
        return
    await update_task_status(order_id=order_id, section="ар", new_status="Сделано")
    await callback.message.edit_reply_markup()
    await callback.message.answer("✅ Раздел АР принят. Файл сохранён в папке проекта как ar_files.zip.")
    await callback.answer("Файл принят ✅", show_alert=True)

@router.callback_query(F.data.startswith("gip_ar_reject:"))
async def handle_gip_ar_rejection(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.clear()  # 🧹 Очистим все предыдущее
    await state.set_state(ReviewArCorrectionFSM.waiting_for_comment)
    await state.update_data(order_id=order_id, section="ар")

    await callback.message.edit_reply_markup()
    await callback.message.answer("❗️ Напишите замечания по разделу АР:")
    await callback.answer()

@router.message(ReviewArCorrectionFSM.waiting_for_comment)
async def send_ar_correction_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    section = data["section"]
    comment = message.text.strip()

    # Получаем специалиста по разделу
    specialist = await get_specialist_by_order_and_section(order_id, section)
    
    if not specialist:
        await message.answer("❗ Специалист по этому заказу не найден.")
        await state.clear()
        return

    await message.bot.send_message(
        chat_id=specialist["telegram_id"],
        text=(f"🛠 Получены замечания по разделу <b>{section.upper()}</b> по заказу #{order_id}:\n\n"
              f"🗒 {comment}"),
        parse_mode="HTML"
    )

    await message.answer("✅ Комментарий передан специалисту.")
    await state.clear()