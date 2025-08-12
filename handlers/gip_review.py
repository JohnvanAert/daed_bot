from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_order_by_id, get_customer_telegram_id, get_specialist_by_section, update_order_status, create_task, get_specialist_by_order_and_section, get_ar_task_document, update_task_status, save_kj_file_path_to_tasks, get_ovik_task_document, get_eom_task_document, get_ss_task_document, get_kj_task_document, get_vk_task_document, get_task_document_by_section, get_all_experts, update_task_document_url, get_gs_task_document, update_all_sections_status, get_all_experts_i, create_or_get_task, assign_task_to_expert
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import FSInputFile
import os
from aiogram.types import Document
from datetime import date, timedelta, datetime
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.enums import ParseMode
from states.ar_correction import ReviewArCorrectionFSM
import shutil
from states.task_states import AssignARFSM, AssignKJFSM, ReviewKjCorrectionFSM, AssignOVIKFSM, ReviewOvikCorrectionFSM, AssignGSFSM, ReviewGSCorrectionFSM, AssignVKFSM, ReviewVkCorrectionFSM, AssignEOMFSM, ReviewEomCorrectionFSM, AssignSSFSM, ReviewSSCorrectionFSM
import re


load_dotenv()

router = Router()

class ReviewCorrectionFSM(StatesGroup):
    waiting_for_comments = State()
    waiting_for_fixed_files = State()
    waiting_for_customer_questions = State()
    waiting_for_customer_zips = State()
    waiting_for_customer_error_comments = State()

BASE_DOC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot", "documents"))
TEMP_DOC_PATH = os.path.join(BASE_DOC_PATH, "temporary")

@router.callback_query(F.data.startswith("gip_approve:"))
async def handle_gip_approval(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    customer_id = await get_customer_telegram_id(order["customer_id"])
    order_title = order["title"]
    safe_title = order_title.replace(" ", "_")

    # Путь к временной папке
    temp_files = os.listdir(TEMP_DOC_PATH)
    matching_file = next((f for f in temp_files if f.startswith(f"ep_{order_id}_")), None)

    if not matching_file:
        await callback.message.answer("❗ Временный файл не найден.")
        return

    source_path = os.path.join(TEMP_DOC_PATH, matching_file)
    target_dir = os.path.join(BASE_DOC_PATH, safe_title)
    os.makedirs(target_dir, exist_ok=True)
    final_path = os.path.join(target_dir, "ep.pdf")

    shutil.move(source_path, final_path)

    caption = (
        f"📦 По вашему заказу <b>{order['title']}</b> выполнен раздел ЭП.\n"
        f"📄 Пожалуйста, предоставьте следующие документы:\n"
        f"🔷 ГПЗУ\n🔷 ТУ\n🔷 ПДП"
    )

    await callback.bot.send_document(
        chat_id=customer_id,
        document=FSInputFile(final_path),
        caption=caption,
        parse_mode="HTML"
    )

    await update_order_status(order_id, "receive_ird")
    await callback.message.edit_reply_markup()
    await callback.message.answer("✅ Заказ передан заказчику.")
    await callback.answer("Передано заказчику ✅", show_alert=True)

@router.callback_query(F.data.startswith("gip_reject:"))
async def handle_gip_rejection(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewCorrectionFSM.waiting_for_comments)
    await state.update_data(order_id=order_id)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❗ Напишите комментарий с замечаниями по ЭП:")

@router.message(ReviewCorrectionFSM.waiting_for_comments)
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
    await state.set_state(ReviewCorrectionFSM.waiting_for_fixed_files)
    await state.update_data(order_id=order_id)
    await callback.message.answer("📎 Прикрепите исправленный PDF файл ЭП:")
    await callback.answer()

@router.message(ReviewCorrectionFSM.waiting_for_fixed_files, F.document)
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
    await state.set_state(ReviewCorrectionFSM.waiting_for_customer_error_comments)
    await state.update_data(order_id=order_id)
    await callback.message.answer("✏️ Напишите, пожалуйста, комментарий для заказчика (что не так с документами):")
    await callback.answer()

@router.message(ReviewCorrectionFSM.waiting_for_customer_error_comments)
async def send_docs_error_to_customer(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    order = await get_order_by_id(order_id)
    customer_id = await get_customer_telegram_id(order["customer_id"])

    comment = message.text.strip()

    # 🔄 Обновим статус заказа
    await update_order_status(order_id, "pending_correction")

    await message.bot.send_document(
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
async def handle_docs_accept(callback: CallbackQuery, bot: Bot):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    if not order:
        await callback.answer("❗ Заказ не найден.", show_alert=True)
        return

    # Получаем безопасное название проекта
    safe_title = re.sub(r'[^\w\-]', '_', order["title"])
    project_dir = os.path.join("documents", safe_title)
    os.makedirs(project_dir, exist_ok=True)

    # Путь куда будем сохранять
    document: Document = callback.message.document
    if not document:
        await callback.answer("❗ Файл не найден в сообщении.", show_alert=True)
        return

    file_info = await bot.get_file(document.file_id)
    file_path_on_server = file_info.file_path
    filename = document.file_name or f"{order['title']}.zip"
    save_path = os.path.join(project_dir, filename)

    try:
        # Скачиваем и сохраняем файл
        await bot.download_file(file_path_on_server, destination=save_path)

        # Обновим статус и путь
        await update_order_status(order_id, "ep_documents_accepted")
        await update_task_status(order_id=order_id, section="эп", new_status="Сделано")
        print("📁 Сохраняем путь в tasks:", save_path)
        await update_task_document_url(order_id=order_id, section="эп", document_url=save_path)

        # Обновляем caption и кнопку
        original_caption = callback.message.caption or ""
        updated_caption = original_caption + "\n\n✅ Документы заказчика приняты. Теперь можно передать заказ специалисту по АР."

        new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Передать АР", callback_data=f"assign_ar:{order_id}")]
        ])

        await callback.message.edit_caption(caption=updated_caption, reply_markup=new_keyboard)
        await callback.answer("Документы приняты ✅", show_alert=True)

    except Exception as e:
        await callback.answer(f"⚠️ Ошибка при скачивании файла: {e}", show_alert=True)

@router.message(ReviewCorrectionFSM.waiting_for_customer_zips, F.document)
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
            caption=f"📥 Получен исправленный архив 2 от заказчика по заказу: <b>{order['title']}</b>",
            parse_mode="HTML"
        )
    
    await message.answer("✅ Спасибо! ZIP-файл передан исполнителям.")
    await state.clear()

@router.callback_query(F.data.startswith("docs_error:"))
async def handle_docs_error(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewCorrectionFSM.waiting_for_customer_error_comments)
    await state.update_data(order_id=order_id)
    await callback.message.answer("✏️ Укажите, что не так с ИРД:")
    await callback.answer()


@router.message(ReviewCorrectionFSM.waiting_for_customer_error_comments)
async def handle_docs_error_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    order = await get_order_by_id(order_id)
    customer_id = await get_customer_telegram_id(order["customer_id"])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📎 Отправить исправленные ИРД", callback_data=f"send_ird:{order_id}")]
    ])

    await message.bot.send_document(
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

    # Используем безопасное название проекта
    safe_title = re.sub(r'[^\w\-]', '_', title)
    doc_path = os.path.abspath(os.path.join("documents", safe_title, "ep.pdf"))

    if not os.path.exists(doc_path):
        await message.answer("❗️ Не удалось найти файл заказа: ep.pdf.")
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

    order_id = int(callback.data.split(":")[1])
    await update_order_status(order_id, "approved_ar")
    
    order = await get_order_by_id(order_id)
    document_url = order.get("document_url")

    if not document_url:
        await callback.message.answer("❗️ У заказа не указан путь document_url.")
        return

    # Путь до корня проекта (до psdbot)
    BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot"))


    # Путь к папке проекта (на основе document_url)   # e.g. documents/ЖК_Адал/test.zip
    project_folder_rel = document_url  # e.g. documents/ЖК_Адал
    PROJECT_ABS_PATH = os.path.join(BASE_PATH, project_folder_rel)

    if not os.path.exists(PROJECT_ABS_PATH):
        await callback.message.answer(f"❗️ Папка проекта не найдена: {PROJECT_ABS_PATH}")
        return

    # Получаем относительный путь к файлу АР из tasks
    relative_task_file = await get_ar_task_document(order_id)

    if not relative_task_file:
        await callback.message.answer("❗️ Не найден путь к АР-файлу (tasks.document_url).")
        return

    # Абсолютный путь к исходному АР-файлу
    source_abs_path = os.path.join(BASE_PATH, "documents", relative_task_file)

    if not os.path.exists(source_abs_path):
        await callback.message.answer(f"❗️ АР-файл не найден: {source_abs_path}")
        return

    # Целевой путь в проектной папке
    final_path = os.path.join(PROJECT_ABS_PATH, "ar_files.zip")

    try:
        shutil.move(source_abs_path, final_path)
    except Exception as e:
        await callback.message.answer(f"❗️ Ошибка при перемещении файла: {e}")
        return

    await update_task_status(order_id=order_id, section="ар", new_status="Сделано")
    await update_task_document_url(
        order_id=order_id,
        section="ар",
        document_url=os.path.join("documents", os.path.basename(project_folder_rel), "ar_files.zip")
    )
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

@router.callback_query(F.data.startswith("assign_kj:"))
async def handle_assign_kj(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    specialist = await get_specialist_by_section("кж")

    if not specialist:
        await callback.message.answer("❗️ Специалист по КЖ не найден.")
        return

    await state.set_state(AssignKJFSM.waiting_for_deadline)
    await state.update_data(
        order_id=order_id,
        specialist_id=specialist["telegram_id"],
        description=order["description"],
        title=order["title"],
        document_url=order["document_url"]
    )

    await callback.message.answer("📅 Введите количество дней до дедлайна (например: 5):")
    await callback.answer()


@router.message(AssignKJFSM.waiting_for_deadline)
async def receive_kj_deadline_days(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗ Введите положительное число — количество дней до дедлайна.")
        return

    deadline = datetime.today().date() + timedelta(days=days)
    await state.update_data(deadline=deadline, days=days)
    await state.set_state(AssignKJFSM.waiting_for_description)
    await message.answer("📝 Теперь введите описание задачи по КЖ:")


@router.message(AssignKJFSM.waiting_for_description)
async def receive_kj_description(message: Message, state: FSMContext):
    description = message.text.strip()
    data = await state.get_data()

    order_id = data["order_id"]
    specialist_id = data["specialist_id"]
    title = data["title"]
    document_url = data["document_url"]
    deadline = data["deadline"]
    days = data["days"]

    await update_order_status(order_id, "assigned_kj")
    await create_task(
        order_id=order_id,
        section="кж",
        description=description,
        deadline=deadline,
        specialist_id=specialist_id,
        status="Разработка КЖ"
    )

    doc_path = os.path.abspath(os.path.join("..", "psdbot", document_url))
    ar_zip_rel_path = os.path.join(document_url, "ar_files.zip")
    ar_zip_abs_path = os.path.abspath(os.path.join("..", "psdbot", ar_zip_rel_path))
    if not os.path.exists(ar_zip_abs_path):
        await message.answer("❗️ Не удалось найти файл заказа.")
        await state.clear()
        return

    caption = (
        f"📄 Новый заказ по разделу КЖ:\n"
        f"📌 <b>{title}</b>\n"
        f"📝 {description}\n"
        f"📅 Дедлайн через {days} дн. ({deadline.strftime('%d.%m.%Y')})"
    )

    await message.bot.send_document(
        chat_id=specialist_id,
        document=FSInputFile(ar_zip_abs_path),
        caption=caption,
        parse_mode="HTML"
    )

    await message.answer("✅ Задание по КЖ передано.")
    await state.clear()

@router.callback_query(F.data.startswith("approve_kj:"))
async def handle_gip_kj_approval(callback: CallbackQuery):

    order_id = int(callback.data.split(":")[1])
    await callback.message.answer(f"📌 Одобряем КЖ по заказу: {order_id}")
    await update_order_status(order_id, "approved_kj")

    order = await get_order_by_id(order_id)
    document_url = order.get("document_url")

    if not document_url:
        await callback.message.answer("❗️ У заказа не указан путь document_url.")
        return

    # Путь до корня проекта (до psdbot)
    BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot"))
    await callback.message.answer(f"📂 BASE_PATH: {BASE_PATH}")

    # Путь к папке проекта
    project_folder_rel = document_url  # уже нужная папка
    PROJECT_ABS_PATH = os.path.join(BASE_PATH, project_folder_rel)
    await callback.message.answer(f"📁 Папка проекта: {PROJECT_ABS_PATH}")

    if not os.path.exists(PROJECT_ABS_PATH):
        await callback.message.answer(f"❗️ Папка проекта не найдена: {PROJECT_ABS_PATH}")
        return

    # Получаем относительный путь к файлу КЖ из tasks
    relative_file_path = await get_kj_task_document(order_id)

    if not relative_file_path:
        await callback.message.answer("❗️ Не найден путь к КЖ-файлу (tasks.document_url).")
        return

    # Абсолютный путь к исходному КЖ-файлу
    SOURCE_ABS_PATH = os.path.join(BASE_PATH, "documents", relative_file_path)
    
    if not os.path.exists(SOURCE_ABS_PATH):
        await callback.message.answer(f"❗️ КЖ-файл не найден: {SOURCE_ABS_PATH}")
        return

    # Целевой путь в проектной папке
    FINAL_PATH = os.path.join(PROJECT_ABS_PATH, "kj_files.zip")

    try:
        shutil.move(SOURCE_ABS_PATH, FINAL_PATH)
    except Exception as e:
        await callback.message.answer(f"❗️ Ошибка при перемещении файла: {e}")
        return

    await update_task_status(order_id=order_id, section="кж", new_status="Сделано")
    await callback.message.edit_reply_markup()
    await update_task_document_url(
        order_id=order_id,
        section="кж",
        document_url=os.path.join("documents", os.path.basename(project_folder_rel), "kj_files.zip")
    )
    await callback.message.answer("✅ Раздел КЖ принят. Файл сохранён в папке проекта как kj_files.zip.")
    await callback.answer("Файл принят ✅", show_alert=True)


@router.callback_query(F.data.startswith("revise_kj:"))
async def handle_kj_revision(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewKjCorrectionFSM.waiting_for_comment)
    await state.update_data(order_id=order_id, section="кж")

    await callback.message.edit_reply_markup()
    await callback.message.answer("✏️ Напишите замечания по КЖ:")
    await callback.answer()

@router.message(ReviewKjCorrectionFSM.waiting_for_comment)
async def handle_kj_correction_comment(message: Message, state: FSMContext):
    from database import get_specialist_by_order_and_section

    data = await state.get_data()
    order_id = data["order_id"]
    section = data["section"]
    comment = message.text.strip()

    specialist = await get_specialist_by_order_and_section(order_id, section)

    if not specialist:
        await message.answer("❗️ Специалист по КЖ не найден.")
        await state.clear()
        return

    await message.bot.send_message(
        chat_id=specialist["telegram_id"],
        text=(
            f"❗️ Замечания по разделу <b>{section.upper()}</b> по заказу #{order_id}:\n\n"
            f"📝 {comment}"
        ),
        parse_mode="HTML"
    )

    await message.answer("✅ Замечания отправлены специалисту по КЖ.")
    await state.clear()


@router.callback_query(F.data.startswith("assign_ovik:"))
async def handle_assign_ovik(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    specialist = await get_specialist_by_section("овик")

    if not specialist:
        await callback.message.answer("❗️ Специалист по ОВиК не найден.")
        return

    await state.set_state(AssignOVIKFSM.waiting_for_deadline)
    await state.update_data(
        order_id=order_id,
        specialist_id=specialist["telegram_id"],
        description=order["description"],
        title=order["title"],
        document_url=order["document_url"]
    )

    await callback.message.answer("📅 Введите количество дней до дедлайна (например: 5):")
    await callback.answer()


@router.message(AssignOVIKFSM.waiting_for_deadline)
async def receive_ovik_deadline_days(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗ Введите положительное число — количество дней до дедлайна.")
        return

    deadline = datetime.today().date() + timedelta(days=days)
    await state.update_data(deadline=deadline, days=days)
    await state.set_state(AssignOVIKFSM.waiting_for_description)
    await message.answer("📝 Теперь введите описание задачи по ОВиК/ТС:")


@router.message(AssignOVIKFSM.waiting_for_description)
async def receive_ovik_description(message: Message, state: FSMContext):
    description = message.text.strip()
    data = await state.get_data()

    order_id = data["order_id"]
    specialist_id = data["specialist_id"]
    title = data["title"]
    document_url = data["document_url"]
    deadline = data["deadline"]
    days = data["days"]

    await update_order_status(order_id, "assigned_ovik")
    await create_task(
        order_id=order_id,
        section="овик",
        description=description,
        deadline=deadline,
        specialist_id=specialist_id,
        status="Разработка ОВиК/ТС"
    )

    doc_path = os.path.abspath(os.path.join("..", "psdbot", document_url))
    ar_zip_rel_path = os.path.join(document_url, "genplan_files.zip")
    ar_zip_abs_path = os.path.abspath(os.path.join("..", "psdbot", ar_zip_rel_path))

    if not os.path.exists(ar_zip_abs_path):
        await message.answer("❗️ Не удалось найти файл заказа.")
        await state.clear()
        return

    caption = (
        f"📄 Новый заказ по разделу ОВиК/ТС:\n"
        f"📌 <b>{title}</b>\n"
        f"📝 {description}\n"
        f"📅 Дедлайн через {days} дн. ({deadline.strftime('%d.%m.%Y')})"
    )

    await message.bot.send_document(
        chat_id=specialist_id,
        document=FSInputFile(ar_zip_abs_path),
        caption=caption,
        parse_mode="HTML"
    )

    await message.answer("✅ Задание по ОВиК передано.")
    await state.clear()


@router.callback_query(F.data.startswith("approve_ovik:"))
async def handle_gip_ovik_approval(callback: CallbackQuery):

    order_id = int(callback.data.split(":")[1])
    await update_order_status(order_id, "approved_ovik")

    order = await get_order_by_id(order_id)
    document_url = order.get("document_url")

    if not document_url:
        await callback.message.answer("❗️ У заказа не указан путь document_url.")
        return

    # Путь до корня проекта (до psdbot)
    BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot"))

    # Путь к папке проекта (на основе document_url)
    PROJECT_DIR = os.path.join(BASE_PATH, document_url)

    if not os.path.exists(PROJECT_DIR):
        await callback.message.answer(f"❗️ Папка проекта не найдена: {PROJECT_DIR}")
        return

    # Путь к файлу ОВиК из tasks
    relative_file_path = await get_ovik_task_document(order_id)
    project_folder_rel = document_url  # уже нужная папка
    if not relative_file_path:
        await callback.message.answer("❗️ Не найден файл ОВиК в tasks.")
        return

    # Абсолютный путь к исходному файлу ОВиК
    SOURCE_PATH = os.path.join(BASE_PATH, "documents", relative_file_path)

    if not os.path.exists(SOURCE_PATH):
        await callback.message.answer(f"❗️ ОВиК-файл не найден: {SOURCE_PATH}")
        return

    # Путь назначения
    TARGET_PATH = os.path.join(PROJECT_DIR, "ovik_files.zip")

    try:
        shutil.move(SOURCE_PATH, TARGET_PATH)
    except Exception as e:
        await callback.message.answer(f"❗️ Ошибка при перемещении файла: {e}")
        return

    await update_task_status(order_id=order_id, section="овик", new_status="Сделано")
    await callback.message.edit_reply_markup()
    await update_task_document_url(
        order_id=order_id,
        section="овик",
        document_url=os.path.join("documents", os.path.basename(project_folder_rel), "ovik_files.zip")
    )
    await callback.message.answer("✅ Раздел ОВиК принят. Файл сохранён в папке проекта как ovik_files.zip.")
    await callback.answer("Файл принят ✅", show_alert=True)

@router.callback_query(F.data.startswith("revise_ovik:"))
async def handle_ovik_revision(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewOvikCorrectionFSM.waiting_for_comment)
    await state.update_data(order_id=order_id, section="овик")

    await callback.message.edit_reply_markup()
    await callback.message.answer("✏️ Напишите замечания по ОВиК:")
    await callback.answer()


@router.message(ReviewOvikCorrectionFSM.waiting_for_comment)
async def handle_ovik_correction_comment(message: Message, state: FSMContext):

    data = await state.get_data()
    order_id = data["order_id"]
    section = data["section"]
    comment = message.text.strip()

    specialist = await get_specialist_by_order_and_section(order_id, section)

    if not specialist:
        await message.answer("❗️ Специалист по ОВиК не найден.")
        await state.clear()
        return

    await message.bot.send_message(
        chat_id=specialist["telegram_id"],
        text=(
            f"❗️ Замечания по разделу <b>{section.upper()}</b> по заказу #{order_id}:\n\n"
            f"📝 {comment}"
        ),
        parse_mode="HTML"
    )

    await message.answer("✅ Замечания отправлены специалисту по ОВиК.")
    await state.clear()


@router.callback_query(F.data.startswith("assign_gs:"))
async def handle_assign_gs(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    specialist = await get_specialist_by_section("гс")  # или "гс", в зависимости от вашей базы

    if not specialist:
        await callback.message.answer("❗️ Специалист по ГС не найден.")
        return

    await state.set_state(AssignGSFSM.waiting_for_deadline)
    await state.update_data(
        order_id=order_id,
        specialist_id=specialist["telegram_id"],
        description=order["description"],
        title=order["title"],
        document_url=order["document_url"]
    )

    await callback.message.answer("📅 Введите количество дней до дедлайна (например: 5):")
    await callback.answer()

@router.message(AssignGSFSM.waiting_for_deadline)
async def receive_gs_deadline_days(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗ Введите положительное число — количество дней до дедлайна.")
        return

    deadline = datetime.today().date() + timedelta(days=days)
    await state.update_data(deadline=deadline, days=days)
    await state.set_state(AssignGSFSM.waiting_for_description)
    await message.answer("📝 Теперь введите описание задачи по ГС:")


@router.message(AssignGSFSM.waiting_for_description)
async def receive_gs_description(message: Message, state: FSMContext):
    description = message.text.strip()
    data = await state.get_data()

    order_id = data["order_id"]
    specialist_id = data["specialist_id"]
    title = data["title"]
    document_url = data["document_url"]
    deadline = data["deadline"]
    days = data["days"]

    await update_order_status(order_id, "assigned_gs")
    await create_task(
        order_id=order_id,
        section="гс",  # или "гс"
        description=description,
        deadline=deadline,
        specialist_id=specialist_id,
        status="Разработка ГС"
    )

    doc_path = os.path.abspath(os.path.join("..", "psdbot", document_url))
    ar_zip_rel_path = os.path.join(document_url, "genplan_files.zip")
    ar_zip_abs_path = os.path.abspath(os.path.join("..", "psdbot", ar_zip_rel_path))
    if not os.path.exists(ar_zip_abs_path):
        await message.answer("❗️ Не удалось найти файл заказа.")
        await state.clear()
        return

    caption = (
        f"📄 Новый заказ по разделу ГC:\n"
        f"📌 <b>{title}</b>\n"
        f"📝 {description}\n"
        f"📅 Дедлайн через {days} дн. ({deadline.strftime('%d.%m.%Y')})"
    )

    await message.bot.send_document(
        chat_id=specialist_id,
        document=FSInputFile(ar_zip_abs_path),
        caption=caption,
        parse_mode="HTML"
    )

    await message.answer("✅ Задание по ГС передано.")
    await state.clear()


@router.callback_query(F.data.startswith("revise_gs:"))
async def handle_gs_revision(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewGSCorrectionFSM.waiting_for_comment)
    await state.update_data(order_id=order_id, section="гс")  # Или "гс", если у тебя так в базе

    await callback.message.edit_reply_markup()
    await callback.message.answer("✏️ Напишите замечания по разделу ГС:")
    await callback.answer()

@router.message(ReviewGSCorrectionFSM.waiting_for_comment)
async def handle_gs_correction_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    section = data["section"]
    comment = message.text.strip()

    specialist = await get_specialist_by_order_and_section(order_id, section)

    if not specialist:
        await message.answer("❗️ Специалист по ГС не найден.")
        await state.clear()
        return

    await message.bot.send_message(
        chat_id=specialist["telegram_id"],
        text=(
            f"❗️ Замечания по разделу <b>{section.upper()}</b> по заказу #{order_id}:\n\n"
            f"📝 {comment}"
        ),
        parse_mode="HTML"
    )

    await message.answer("✅ Замечания отправлены специалисту по ГС.")
    await state.clear()

@router.callback_query(F.data.startswith("approve_gs:"))
async def handle_gip_gs_approval(callback: CallbackQuery):

    order_id = int(callback.data.split(":")[1])
    await callback.message.answer(f"📌 Одобряем ГС по заказу: {order_id}")
    await update_order_status(order_id, "approved_gs")

    order = await get_order_by_id(order_id)
    document_url = order.get("document_url")

    if not document_url:
        await callback.message.answer("❗️ У заказа не указан путь document_url.")
        return

    # Путь до корня проекта
    BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot"))
    await callback.message.answer(f"📂 BASE_PATH: {BASE_PATH}")

    # Путь к папке проекта
    project_folder_rel = document_url  # уже нужная папка
    PROJECT_ABS_PATH = os.path.join(BASE_PATH, project_folder_rel)

    if not os.path.exists(PROJECT_ABS_PATH):
        await callback.message.answer(f"❗️ Папка проекта не найдена: {PROJECT_ABS_PATH}")
        return

    # Получаем относительный путь к файлу КЖ из tasks
    relative_file_path = await get_gs_task_document(order_id)

    if not relative_file_path:
        await callback.message.answer(f"❗️ Не найден путь к КЖ-файлу (tasks.document_url).")
        return

    # Файл gs_files.zip должен быть в temporary
    SOURCE_PATH = os.path.join(BASE_PATH, "documents", relative_file_path)

    project_folder_rel = document_url 
    if not os.path.exists(SOURCE_PATH):
        await callback.message.answer(f"❗️ Файл ГС не найден: {SOURCE_PATH}")
        return

    FINAL_PATH = os.path.join(PROJECT_ABS_PATH, "gs_files.zip")

    try:
        shutil.move(SOURCE_PATH, FINAL_PATH)
    except Exception as e:
        await callback.message.answer(f"❗️ Ошибка при перемещении файла: {e}")
        return

    await update_task_status(order_id=order_id, section="гс", new_status="Сделано")
    await callback.message.edit_reply_markup()
    await update_task_document_url(
        order_id=order_id,
        section="гс",
        document_url=os.path.join("documents", os.path.basename(project_folder_rel), "gs_files.zip")
    )
    await callback.message.answer("✅ Раздел ГС принят. Файл сохранён как gs_files.zip.")
    await callback.answer("Файл принят ✅", show_alert=True)

@router.callback_query(F.data.startswith("assign_vk:"))
async def handle_assign_vk(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    specialist = await get_specialist_by_section("вк")

    if not specialist:
        await callback.message.answer("❗️ Специалист по ВК не найден.")
        return

    await state.set_state(AssignVKFSM.waiting_for_deadline)
    await state.update_data(
        order_id=order_id,
        specialist_id=specialist["telegram_id"],
        description=order["description"],
        title=order["title"],
        document_url=order["document_url"]
    )

    await callback.message.answer("📅 Введите количество дней до дедлайна (например: 5):")
    await callback.answer()


@router.message(AssignVKFSM.waiting_for_deadline)
async def receive_vk_deadline_days(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗️ Введите положительное число — количество дней до дедлайна.")
        return

    deadline = datetime.today().date() + timedelta(days=days)
    await state.update_data(deadline=deadline, days=days)
    await state.set_state(AssignVKFSM.waiting_for_description)
    await message.answer("📝 Теперь введите описание задачи по ВК/НВК:")


@router.message(AssignVKFSM.waiting_for_description)
async def receive_vk_description(message: Message, state: FSMContext):
    description = message.text.strip()
    data = await state.get_data()

    order_id = data["order_id"]
    specialist_id = data["specialist_id"]
    title = data["title"]
    document_url = data["document_url"]
    deadline = data["deadline"]
    days = data["days"]

    await update_order_status(order_id, "assigned_vk")
    await create_task(
        order_id=order_id,
        section="вк",
        description=description,
        deadline=deadline,
        specialist_id=specialist_id,
        status="Разработка ВК"
    )

    doc_path = os.path.abspath(os.path.join("..", "psdbot", document_url))
    ar_zip_rel_path = os.path.join(document_url, "genplan_files.zip")
    ar_zip_abs_path = os.path.abspath(os.path.join("..", "psdbot", ar_zip_rel_path))
    if not os.path.exists(ar_zip_abs_path):
        await message.answer("❗️ Не удалось найти файл заказа.")
        await state.clear()
        return

    caption = (
        f"📄 Новый заказ по разделу ВК/НВК:\n"
        f"📌 <b>{title}</b>\n"
        f"📝 {description}\n"
        f"📅 Дедлайн через {days} дн. ({deadline.strftime('%d.%m.%Y')})"
    )

    await message.bot.send_document(
        chat_id=specialist_id,
        document=FSInputFile(ar_zip_abs_path),
        caption=caption,
        parse_mode="HTML"
    )

    await message.answer("✅ Задание по ВК/НВК передано.")
    await state.clear()

@router.callback_query(F.data.startswith("gip_vk_approve:"))
async def handle_gip_vk_approval(callback: CallbackQuery):

    order_id = int(callback.data.split(":")[1])
    await callback.message.answer(f"📌 Одобряем ВК по заказу: {order_id}")
    await update_order_status(order_id, "approved_vk")

    order = await get_order_by_id(order_id)
    document_url = order.get("document_url")

    if not document_url:
        await callback.message.answer("❗️ У заказа не указан путь document_url.")
        return

    # Путь до корня проекта (до psdbot)
    BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot"))
    await callback.message.answer(f"📂 BASE_PATH: {BASE_PATH}")

    # Путь к папке проекта
    project_folder_rel = document_url  # уже нужная папка
    PROJECT_ABS_PATH = os.path.join(BASE_PATH, project_folder_rel)
    await callback.message.answer(f"📁 Папка проекта: {PROJECT_ABS_PATH}")

    if not os.path.exists(PROJECT_ABS_PATH):
        await callback.message.answer(f"❗️ Папка проекта не найдена: {PROJECT_ABS_PATH}")
        return

    # Получаем относительный путь к файлу ВК из tasks
    relative_file_path = await get_vk_task_document(order_id)

    if not relative_file_path:
        await callback.message.answer("❗️ Не найден путь к ВК-файлу (tasks.document_url).")
        return

    # Абсолютный путь к исходному ВК-файлу
    SOURCE_ABS_PATH = os.path.join(BASE_PATH, "documents", relative_file_path)
    
    if not os.path.exists(SOURCE_ABS_PATH):
        await callback.message.answer(f"❗️ ВК-файл не найден: {SOURCE_ABS_PATH}")
        return

    # Целевой путь в проектной папке
    FINAL_PATH = os.path.join(PROJECT_ABS_PATH, "vk_files.zip")

    try:
        shutil.move(SOURCE_ABS_PATH, FINAL_PATH)
    except Exception as e:
        await callback.message.answer(f"❗️ Ошибка при перемещении файла: {e}")
        return

    await update_task_status(order_id=order_id, section="вк", new_status="Сделано")
    
    await callback.message.edit_reply_markup()
    await update_task_document_url(
        order_id=order_id,
        section="вк",
        document_url=os.path.join("documents", os.path.basename(project_folder_rel), "vk_files.zip")
    )
    await callback.message.answer("✅ Раздел ВК принят. Файл сохранён как vk_files.zip.")
    await callback.answer("Файл принят ✅", show_alert=True)

@router.callback_query(F.data.startswith("revise_vk:"))
async def handle_vk_revision(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewVkCorrectionFSM.waiting_for_comment)
    await state.update_data(order_id=order_id, section="вк")

    await callback.message.edit_reply_markup()
    await callback.message.answer("✏️ Напишите замечания по ВК:")
    await callback.answer()

@router.message(ReviewVkCorrectionFSM.waiting_for_comment)
async def handle_vk_correction_comment(message: Message, state: FSMContext):

    data = await state.get_data()
    order_id = data["order_id"]
    section = data["section"]
    comment = message.text.strip()

    specialist = await get_specialist_by_order_and_section(order_id, section)

    if not specialist:
        await message.answer("❗️ Специалист по ВК не найден.")
        await state.clear()
        return

    await message.bot.send_message(
        chat_id=specialist["telegram_id"],
        text=(
            f"❗️ Замечания по разделу <b>{section.upper()}</b> по заказу #{order_id}:\n\n"
            f"📝 {comment}"
        ),
        parse_mode="HTML"
    )

    await message.answer("✅ Замечания отправлены специалисту по ВК.")
    await state.clear()


@router.callback_query(F.data.startswith("assign_eom:"))
async def handle_assign_eom(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    specialist = await get_specialist_by_section("эом")

    if not specialist:
        await callback.message.answer("❗️ Специалист по ЭОМ не найден.")
        return

    await state.set_state(AssignEOMFSM.waiting_for_deadline)
    await state.update_data(
        order_id=order_id,
        specialist_id=specialist["telegram_id"],
        description=order["description"],
        title=order["title"],
        document_url=order["document_url"]
    )

    await callback.message.answer("📅 Введите количество дней до дедлайна (например: 5):")
    await callback.answer()


@router.message(AssignEOMFSM.waiting_for_deadline)
async def receive_eom_deadline_days(message: Message, state: FSMContext):

    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗ Введите положительное число — количество дней до дедлайна.")
        return

    deadline = datetime.today().date() + timedelta(days=days)
    await state.update_data(deadline=deadline, days=days)
    await state.set_state(AssignEOMFSM.waiting_for_description)
    await message.answer("📝 Теперь введите описание задачи по ЭОМ:")


@router.message(AssignEOMFSM.waiting_for_description)
async def receive_eom_description(message: Message, state: FSMContext):

    description = message.text.strip()
    data = await state.get_data()

    order_id = data["order_id"]
    specialist_id = data["specialist_id"]
    title = data["title"]
    document_url = data["document_url"]
    deadline = data["deadline"]
    days = data["days"]

    await update_order_status(order_id, "assigned_eom")
    await create_task(
        order_id=order_id,
        section="эом",
        description=description,
        deadline=deadline,
        specialist_id=specialist_id,
        status="Разработка ЭОМ"
    )

    doc_path = os.path.abspath(os.path.join("..", "psdbot", document_url))
    ar_zip_rel_path = os.path.join(document_url, "genplan_files.zip")
    ar_zip_abs_path = os.path.abspath(os.path.join("..", "psdbot", ar_zip_rel_path))
    if not os.path.exists(ar_zip_abs_path):
        await message.answer("❗️ Не удалось найти файл заказа.")
        await state.clear()
        return

    caption = (
        f"📄 Новый заказ на разработку ЭОМ:\n"
        f"📌 <b>{title}</b>\n"
        f"📝 {description}\n"
        f"📅 Дедлайн через {days} дн. ({deadline.strftime('%d.%m.%Y')})\n"
        f"💬 Комментарий: Передан заказ на разработку ЭОМ"
    )

    await message.bot.send_document(
        chat_id=specialist_id,
        document=FSInputFile(ar_zip_abs_path),
        caption=caption,
        parse_mode="HTML"
    )

    await message.answer("✅ Задание передано специалисту по ЭОМ.")
    await state.clear()

@router.callback_query(F.data.startswith("gip_eom_approve:"))
async def handle_gip_eom_approval(callback: CallbackQuery):

    order_id = int(callback.data.split(":")[1])
    await callback.message.answer(f"📌 Одобряем ЭОМ по заказу: {order_id}")
    await update_order_status(order_id, "approved_eom")

    order = await get_order_by_id(order_id)
    document_url = order.get("document_url")

    if not document_url:
        await callback.message.answer("❗️ У заказа не указан путь document_url.")
        return

    # Абсолютный путь до проекта
    BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot"))
    await callback.message.answer(f"📂 BASE_PATH: {BASE_PATH}")

    # Путь к папке проекта
    project_folder_rel = document_url  # уже нужная папка
    PROJECT_ABS_PATH = os.path.join(BASE_PATH, project_folder_rel)
    await callback.message.answer(f"📁 Папка проекта: {PROJECT_ABS_PATH}")

    if not os.path.exists(PROJECT_ABS_PATH):
        await callback.message.answer(f"❗️ Папка проекта не найдена: {PROJECT_ABS_PATH}")
        return

    # Получаем относительный путь к файлу КЖ из tasks
    relative_file_path = await get_eom_task_document(order_id)

    if not relative_file_path:
        await callback.message.answer("❗️ Не найден путь к ЭОМ-файлу (tasks.document_url).")
        return

    # Абсолютный путь к исходному КЖ-файлу
    SOURCE_ABS_PATH = os.path.join(BASE_PATH, "documents", relative_file_path)
    
    if not os.path.exists(SOURCE_ABS_PATH):
        await callback.message.answer(f"❗️ ЭОМ-файл не найден: {SOURCE_ABS_PATH}")
        return

    # Целевой путь в проектной папке
    FINAL_PATH = os.path.join(PROJECT_ABS_PATH, "eom_files.zip")
    try:
        shutil.move(SOURCE_ABS_PATH, FINAL_PATH)
    except Exception as e:
        await callback.message.answer(f"❗️ Ошибка при перемещении файла: {e}")
        return

    await update_task_status(order_id=order_id, section="эом", new_status="Сделано")
    await update_task_document_url(
        order_id=order_id,
        section="эом",
        document_url=os.path.join("documents", os.path.basename(project_folder_rel), "eom_files.zip")
    )
    await callback.message.edit_reply_markup()
    await callback.message.answer("✅ Раздел ЭОМ принят. Файл сохранён как eom_files.zip.")
    await callback.answer("Файл принят ✅", show_alert=True)


@router.callback_query(F.data.startswith("gip_eom_reject:"))
async def handle_gip_eom_rejection(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.clear()
    await state.set_state(ReviewEomCorrectionFSM.waiting_for_comment)
    await state.update_data(order_id=order_id, section="эом")

    await callback.message.edit_reply_markup()
    await callback.message.answer("❗️ Напишите замечания по разделу ЭОМ:")
    await callback.answer()

@router.message(ReviewEomCorrectionFSM.waiting_for_comment)
async def send_eom_correction_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    section = data["section"]
    comment = message.text.strip()

    specialist = await get_specialist_by_order_and_section(order_id, section)

    if not specialist:
        await message.answer("❗ Специалист по ЭОМ не найден.")
        await state.clear()
        return

    await message.bot.send_message(
        chat_id=specialist["telegram_id"],
        text=(
            f"🛠 Получены замечания по разделу <b>{section.upper()}</b> по заказу #{order_id}:\n\n"
            f"🗒 {comment}"
        ),
        parse_mode="HTML"
    )

    await message.answer("✅ Комментарий передан специалисту.")
    await state.clear()


@router.callback_query(F.data.startswith("assign_ss:"))
async def handle_assign_ss(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    specialist = await get_specialist_by_section("сс")

    if not specialist:
        await callback.message.answer("❗️ Специалист по СС не найден.")
        return

    await state.set_state(AssignSSFSM.waiting_for_deadline)
    await state.update_data(
        order_id=order_id,
        specialist_id=specialist["telegram_id"],
        description=order["description"],
        title=order["title"],
        document_url=order["document_url"]
    )

    await callback.message.answer("📅 Введите количество дней до дедлайна (например: 5):")
    await callback.answer()


@router.message(AssignSSFSM.waiting_for_deadline)
async def receive_ss_deadline_days(message: Message, state: FSMContext):
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
    await state.set_state(AssignSSFSM.waiting_for_description)
    await message.answer("📝 Теперь введите описание задачи по СС:")


@router.message(AssignSSFSM.waiting_for_description)
async def receive_ss_description(message: Message, state: FSMContext):
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

    await update_order_status(order_id, "assigned_ss")
    await create_task(
        order_id=order_id,
        section="сс",
        description=description,
        deadline=deadline,
        specialist_id=specialist_id,
        status="Разработка СС"
    )

    doc_path = os.path.abspath(os.path.join("..", "psdbot", document_url))
    ar_zip_rel_path = os.path.join(document_url, "genplan_files.zip")
    ar_zip_abs_path = os.path.abspath(os.path.join("..", "psdbot", ar_zip_rel_path))
    if not os.path.exists(ar_zip_abs_path):
        await message.answer("❗️ Не удалось найти файл заказа.")
        await state.clear()
        return

    caption = (
        f"📄 Новый заказ на разработку СС:\n"
        f"📌 <b>{title}</b>\n"
        f"📝 {description}\n"
        f"📅 Дедлайн через {days} дн. ({deadline.strftime('%d.%m.%Y')})\n"
        f"💬 Комментарий: Передан заказ на разработку СС"
    )

    await message.bot.send_document(
        chat_id=specialist_id,
        document=FSInputFile(ar_zip_abs_path),
        caption=caption,
        parse_mode="HTML"
    )

    await message.answer("✅ Задание передано специалисту по СС.")
    await state.clear()


@router.callback_query(F.data.startswith("gip_ss_approve:"))
async def handle_gip_ss_approval(callback: CallbackQuery):

    order_id = int(callback.data.split(":")[1])
    await callback.message.answer(f"📌 Одобряем СС по заказу: {order_id}")
    await update_order_status(order_id, "approved_ss")

    order = await get_order_by_id(order_id)
    document_url = order.get("document_url")

    if not document_url:
        await callback.message.answer("❗️ У заказа не указан путь document_url.")
        return

    # Абсолютный путь до проекта
    BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot"))

    # Путь к папке проекта
    project_folder_rel = document_url  # уже нужная папка
    PROJECT_ABS_PATH = os.path.join(BASE_PATH, project_folder_rel)
    await callback.message.answer(f"📁 Папка проекта: {PROJECT_ABS_PATH}")
    if not os.path.exists(PROJECT_ABS_PATH):
        await callback.message.answer(f"❗️ Папка проекта не найдена: {PROJECT_ABS_PATH}")
        return

    # Получаем относительный путь к файлу КЖ из tasks
    relative_file_path = await get_ss_task_document(order_id)

    if not relative_file_path:
        await callback.message.answer("❗️ Не найден путь к СС-файлу (tasks.document_url).")
        return

    # Абсолютный путь к исходному КЖ-файлу
    SOURCE_ABS_PATH = os.path.join(BASE_PATH, "documents", relative_file_path)
    
    if not os.path.exists(SOURCE_ABS_PATH):
        await callback.message.answer(f"❗️ СС-файл не найден: {SOURCE_ABS_PATH}")
        return
    
     # Целевой путь в проектной папке
    FINAL_PATH = os.path.join(PROJECT_ABS_PATH, "ss_files.zip")

    try:
        shutil.move(SOURCE_ABS_PATH, FINAL_PATH)
        await callback.message.answer("✅ Файл успешно перемещён.")
    except Exception as e:
        await callback.message.answer(f"❗️ Ошибка при перемещении файла: {e}")
        return

    await update_task_status(order_id=order_id, section="сс", new_status="Сделано")
    await update_task_document_url(
        order_id=order_id,
        section="сс",
        document_url=os.path.join("documents", os.path.basename(project_folder_rel), "ss_files.zip")
    )
    await callback.message.edit_reply_markup()
    await callback.message.answer("✅ Раздел СС принят. Файл сохранён как ss_files.zip.")
    await callback.answer("Файл принят ✅", show_alert=True)

@router.callback_query(F.data.startswith("gip_ss_reject:"))
async def handle_gip_ss_rejection(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.clear()
    await state.set_state(ReviewSSCorrectionFSM.waiting_for_comment)
    await state.update_data(order_id=order_id, section="сс")

    await callback.message.edit_reply_markup()
    await callback.message.answer("❗️ Напишите замечания по разделу СС:")
    await callback.answer()


@router.message(ReviewSSCorrectionFSM.waiting_for_comment)
async def send_ss_correction_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    section = data["section"]
    comment = message.text.strip()

    specialist = await get_specialist_by_order_and_section(order_id, section)

    if not specialist:
        await message.answer("❗️ Специалист по СС не найден.")
        await state.clear()
        return

    await message.bot.send_message(
        chat_id=specialist["telegram_id"],
        text=(
            f"🛠 Получены замечания по разделу <b>{section.upper()}</b> по заказу #{order_id}:\n\n"
            f"🗒 {comment}"
        ),
        parse_mode="HTML"
    )

    await message.answer("✅ Комментарий передан специалисту.")
    await state.clear()

def get_section_selection_kb(order_id: int):
    sections = ["ар", "кж", "овик", "вк", "эо","гс","сс"]  # исключаем "эп"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=section.upper(), callback_data=f"send_section:{order_id}:{section}")]
        for section in sections
    ])
    return kb

@router.callback_query(F.data.startswith("send_to_expert:"))
async def handle_select_section(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    kb = get_section_selection_kb(order_id)
    await callback.message.answer("🔍 Выберите раздел, который нужно передать экспертам:", reply_markup=kb)
    await callback.answer()
    
@router.callback_query(F.data.startswith("send_section:"))
async def handle_send_selected_section(callback: CallbackQuery, bot: Bot):
    _, order_id_str, section = callback.data.split(":")
    order_id = int(order_id_str)
    section = section.lower()

    BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot"))
    project = await get_order_by_id(order_id)
    document_url = project.get("document_url")
    order_title = project.get("title")
    if not document_url:
        await callback.message.answer("❗️ У заказа не указан путь document_url.")
        return

    project_path = os.path.join(BASE_PATH, document_url)
    if not os.path.exists(project_path):
        await callback.message.answer(f"❗️ Папка проекта не найдена: {project_path}")
        return

    # Получаем эксперта по разделу
    experts = await get_all_experts_i()
    expert = next((e for e in experts if e["section"].lower() == section), None)

    if not expert:
        await callback.message.answer(f"❗️ Не найден эксперт по разделу {section.upper()}")
        return

    tg_id = expert["telegram_id"]
    
    # Список файлов по разделам
    section_files_map = {
        "ар": ["ar_files.zip", "genplan_files.zip"],
        "кж": ["kj_files.zip", "calc_files.zip", "Geologia.zip"],
        "овик": ["ov_files.zip", "TU.zip"],
        "вк": ["vk_files.zip", "TU.zip"],
        "эо": ["eo_files.zip", "TU.zip"],
        "генплан": ["genplan_files.zip"]
    }

    files_to_send = section_files_map.get(section, [])
    sent_any = False

    for filename in files_to_send:
        full_path = os.path.join(project_path, filename)
        if not os.path.exists(full_path):
            print(f"⚠️ Файл не найден: {full_path}")
            continue
        try:
            await bot.send_document(
                chat_id=tg_id,
                document=FSInputFile(full_path),
                caption=f"📩 Заказ #{order_id} — файл {filename}"
            )
            sent_any = True
        except Exception as e:
            print(f"❌ Ошибка при отправке файла {filename}: {e}")

    if sent_any:
        await callback.message.answer(f"✅ Раздел {section.upper()} отправлен эксперту.")
        await callback.answer("Отправлено ✅", show_alert=True)
        task_id = await create_or_get_task(order_id, section, document_url)
        await assign_task_to_expert(task_id, expert["id"])
    else:
        await callback.message.answer("❗️Этот раздел еще не сделан.")
