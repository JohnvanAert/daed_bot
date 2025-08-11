from aiogram import Router, F, Bot
from aiogram.types import Message, Document, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove
from states.states import CreateOrder, FixOrder
from database import add_order, get_customer_by_telegram_id
import os
import re
import zipfile
import shutil
from database import get_all_gips, get_order_by_customer_id, update_order_document
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()
BASE_DOC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot", "documents"))


@router.message(F.text == "➕ Создать заказ")
async def start_order_creation(message: Message, state: FSMContext):
    await message.answer("Введите название проекта:")
    await state.set_state(CreateOrder.waiting_for_title)

@router.message(CreateOrder.waiting_for_title)
async def process_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("Введите описание проекта:")
    await state.set_state(CreateOrder.waiting_for_description)

@router.message(CreateOrder.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await message.answer("📎 Загрузите архив с документами (в формате .zip):")
    await state.set_state(CreateOrder.waiting_for_document)
    

@router.message(CreateOrder.waiting_for_document, F.document)
async def process_document(message: Message, state: FSMContext):
    file = message.document
    if not file.file_name.endswith(".zip"):
        await message.answer("❗️ Пожалуйста, загрузите архив в формате .zip.")
        return

    data = await state.get_data()
    title = data.get("title", "UnnamedProject")

    # Папка проекта
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
    project_folder = os.path.join(BASE_DOC_PATH, safe_title)
    os.makedirs(project_folder, exist_ok=True)

    # Временная папка
    tmp_folder = os.path.join("documents", "temporary")
    os.makedirs(tmp_folder, exist_ok=True)

    # Сохраняем загруженный файл
    file_path = os.path.join(tmp_folder, file.file_name)
    await message.bot.download(file, destination=file_path)

    # === Обработка архива и разделение по папкам ===
    temp_extract_dir = os.path.join("temp", f"ird_extract_{message.from_user.id}")
    os.makedirs(temp_extract_dir, exist_ok=True)

    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall(temp_extract_dir)

    tu_path = os.path.join(temp_extract_dir, "ТУ")
    geo_path = os.path.join(temp_extract_dir, "Геология")

    # Сохраняем ТУ.zip
    if os.path.exists(tu_path):
        tu_zip = os.path.join(project_folder, "ТУ.zip")
        with zipfile.ZipFile(tu_zip, 'w') as zipf:
            for root, _, files in os.walk(tu_path):
                for f in files:
                    abs_path = os.path.join(root, f)
                    arcname = os.path.relpath(abs_path, tu_path)
                    zipf.write(abs_path, arcname=arcname)

    # Сохраняем Геология.zip
    if os.path.exists(geo_path):
        geo_zip = os.path.join(project_folder, "Геология.zip")
        with zipfile.ZipFile(geo_zip, 'w') as zipf:
            for root, _, files in os.walk(geo_path):
                for f in files:
                    abs_path = os.path.join(root, f)
                    arcname = os.path.relpath(abs_path, geo_path)
                    zipf.write(abs_path, arcname=arcname)

    # Остальное — в ИРД.zip
    ird_zip = os.path.join(project_folder, "ИРД.zip")
    with zipfile.ZipFile(ird_zip, 'w') as zipf:
        for root, _, files in os.walk(temp_extract_dir):
            if root.startswith(tu_path) or root.startswith(geo_path):
                continue
            for f in files:
                abs_path = os.path.join(root, f)
                arcname = os.path.relpath(abs_path, temp_extract_dir)
                zipf.write(abs_path, arcname=arcname)

    shutil.rmtree(temp_extract_dir, ignore_errors=True)

    # Сохраняем заказ в БД
    customer = await get_customer_by_telegram_id(message.from_user.id)
    await add_order(
        title=title,
        description=data["description"],
        document_url=project_folder,
        customer_id=customer["id"]
    )

    # Уведомляем ГИПов
    gip_ids = await get_all_gips()
    for gip_id in gip_ids:
        try:
            inline_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📦 Открыть заказы", callback_data="view_orders")]
                ]
            )
            await message.bot.send_message(
                gip_id,
                f"📬 Поступил новый заказ:\n<b>{title}</b>",
                reply_markup=inline_kb
            )
        except Exception as e:
            print(f"Не удалось отправить сообщение ГИПу {gip_id}: {e}")

    await message.answer("✅ Заказ успешно создан и документы сохранены!")
    await state.clear()

@router.message(F.document, FixOrder.waiting_for_document)
async def process_fixed_document(message: Message, state: FSMContext):
    file = message.document
    if not file.file_name.endswith(".zip"):
        await message.answer("❗ Пожалуйста, загрузите архив в формате .zip.")
        return

    # Получаем заказ клиента
    customer_id = message.from_user.id
    order = await get_order_by_customer_id(customer_id)

    if not order:
        await message.answer("❗ У вас нет заказов, требующих исправления.")
        return

    # Безопасное имя проекта
    safe_title = re.sub(r'[^\w\-]', '_', order['title'])
    project_folder = os.path.join("documents", safe_title)
    os.makedirs(project_folder, exist_ok=True)

    file_path = os.path.join(project_folder, file.file_name)
    await message.bot.download(file, destination=file_path)

    # Обновляем путь к документу в базе
    await update_order_document(order_id=order["id"], new_path=file_path)

    # Уведомим всех ГИПов
    gip_ids = await get_all_gips()
    for gip_id in gip_ids:
        try:
            inline_kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="📦 Открыть заказы", callback_data="view_orders")]]
            )
            await message.bot.send_message(
                chat_id=gip_id,
                text=f"♻️ Заказ <b>{order['title']}</b> был обновлён заказчиком и требует повторного рассмотрения.",
                reply_markup=inline_kb
            )
        except Exception as e:
            print(f"❗ Не удалось уведомить ГИПа {gip_id}: {e}")


    await message.answer("✅ Исправленный архив получен! Ожидайте обратной связи от ГИПа.")

    await state.clear()


@router.callback_query(F.data.startswith("start_fix:"))
async def handle_fix_start(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(FixOrder.waiting_for_document)
    await state.update_data(order_id=order_id)
    await callback.message.answer("📎 Пожалуйста, отправьте исправленный архив .zip:")
    await callback.answer()

