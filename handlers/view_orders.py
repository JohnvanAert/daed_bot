from aiogram import Router, F, types
from aiogram.types import Message, CallbackQuery, FSInputFile
from database import get_all_orders, get_customer_telegram_id, create_task, get_order_by_id, get_specialist_by_section, get_specialist_by_order_and_section, update_task_status, get_genplan_task_document, get_calc_task_document, update_task_document_path, is_section_task_done, are_all_sections_done, update_order_document_url, update_task_document_url, get_completed_orders, get_sections_by_order_id, get_estimate_task_document
import os
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram import Bot
from database import delete_order, update_order_status
from states.states import EditOrder
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from database import set_order_gip
from aiogram.fsm.context import FSMContext
from datetime import timedelta, date
from states.task_states import AssignCalculatorFSM
from states.cl_correction import ReviewCalcCorrectionFSM
from states.task_states import AssignGenplanFSM
from datetime import datetime, timedelta
from states.task_states import ReviewGenplanCorrectionFSM
from states.task_states import AssignARFSM
from states.states import AssignSmetchikFSM, AttachFilesFSM
import zipfile
import shutil
import re
load_dotenv()
router = Router()
ALLOWED_STATUSES = {
    "assigned_vk", "approved_gs", "assigned_gs", "approved_ovik", "approve_ovik",
    "assigned_ovik", "approved_kj", "approve_kj", "assigned_kj", "approved_ss",
    "gip_ss_approve", "assigned_ss", "approved_eom", "gip_eom_approve", "assigned_eom",
    "approved_vk", "gip_vk_approve", "waiting_cl"
}
BASE_DOC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot", "documents"))
# Initialize the client bot with the token from environment variables

section_files_map = {
    "ар": ["ar_files.zip", "genplan_files.zip"],
    "кж": ["kj_files.zip", "calc_files.zip"],
    "овик": ["ovik_files.zip"],
    "вк": ["vk_files.zip"],
    "эо": ["eom_files.zip"],
    "сс": ["ss_files"]
}

async def send_orders_to(recipient, send_method):
    orders = await get_all_orders()

    if not orders:
        await send_method("📭 Пока нет доступных заказов.")
        return
    
    bot = recipient.bot

    for order in orders:
        text = (
            f"📌 <b>{order['title']}</b>\n"
            f"📝 {order['description']}\n"
            f"👤 Заказчик ID: {order['customer_id']}\n"
            f"📅 Создан: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )

        if order["status"] == "queue":
                keyboard_buttons = [[
                    InlineKeyboardButton(text="✅ Принять", callback_data=f"order_accept:{order['id']}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"order_reject:{order['id']}"),
                    InlineKeyboardButton(text="✏️ Исправить", callback_data=f"order_edit:{order['id']}")
                ]]
        elif order["status"] == "approved":
                keyboard_buttons = [[
                    InlineKeyboardButton(text="📤 Передать ЭП", callback_data=f"assign_sketch:{order['id']}")
                ]]
        elif order["status"] == "approved_ar":
            keyboard_buttons = [[
                InlineKeyboardButton(text="📤 Передать расчётчику", callback_data=f"assign_calculator:{order['id']}"),
                InlineKeyboardButton(text="📤 Передать генпланисту", callback_data=f"assign_genplan:{order['id']}")
            ]]
        elif order["status"] == "approved_estimates":
            keyboard_buttons = [[
                InlineKeyboardButton(text="🏁 Завершить ПД", callback_data=f"finish_pd:{order['id']}")
            ]]
        elif order["status"] in ALLOWED_STATUSES:
            keyboard_buttons = []

            if not await is_section_task_done(order["id"], "овик"):
                keyboard_buttons.append([
                    InlineKeyboardButton(text="📤 Передать ОВиК/ТС", callback_data=f"assign_ovik:{order['id']}")
                ])
            if not await is_section_task_done(order["id"], "вк"):
                keyboard_buttons.append([
                    InlineKeyboardButton(text="📤 Передать ВК/НВК", callback_data=f"assign_vk:{order['id']}")
                ])
            if not await is_section_task_done(order["id"], "гс"):
                keyboard_buttons.append([
                    InlineKeyboardButton(text="📤 Передать ВГС/НГС", callback_data=f"assign_gs:{order['id']}")
                ])
            if not await is_section_task_done(order["id"], "кж"):
                keyboard_buttons.append([
                    InlineKeyboardButton(text="📤 Передать КЖ", callback_data=f"assign_kj:{order['id']}")
                ])
            if not await is_section_task_done(order["id"], "эом"):
                keyboard_buttons.append([
                    InlineKeyboardButton(text="📤 Передать ЭОМ", callback_data=f"assign_eom:{order['id']}")
                ])
            if not await is_section_task_done(order["id"], "сс"):
                keyboard_buttons.append([
                    InlineKeyboardButton(text="📤 Передать СС", callback_data=f"assign_ss:{order['id']}")
                ])
             # Новые кнопки для ПЗ и ПОС
            keyboard_buttons.append([
                InlineKeyboardButton(text="📎 Прикрепить пояснительную записку", callback_data=f"attach_pz:{order['id']}")
            ])
            keyboard_buttons.append([
                InlineKeyboardButton(text="📎 Прикрепить ПОС", callback_data=f"attach_pos:{order['id']}")
            ])
            keyboard_buttons.append([
                InlineKeyboardButton(text="📤 Передать экспертам", callback_data=f"send_to_expert:{order['id']}"),
                
            ])
            keyboard_buttons.append([
                    InlineKeyboardButton(text="📤 Передать Сметчику", callback_data=f"assign_sm:{order['id']}")
                ])

            # Добавляем кнопку сметчику, если ВСЕ задачи по разделам выполнены
            # if await are_all_sections_done(order["id"]):
            #     keyboard_buttons.append([
            #         InlineKeyboardButton(text="📤 Передать Сметчику", callback_data=f"assign_sm:{order['id']}")
            #     ])

            
        else:
                keyboard_buttons = []

        keyboard_buttons.append([
            InlineKeyboardButton(text="📥 Скачать весь проект", callback_data=f"send_project_zip:{order['id']}")
        ])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        document_path = os.path.abspath(os.path.join(BASE_DOC_PATH, os.path.relpath(order["document_url"], "documents")))
        if os.path.exists(document_path):
            await send_method(text, reply_markup=keyboard)
        else:
            await send_method(f"{text}\n\n⚠️ Документ не найден по пути: {document_path}", reply_markup=keyboard)

@router.callback_query(F.data.startswith("send_project_zip:"))
async def handle_send_project_zip(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    order_title = order["title"]
    
    await callback.answer("⏳ Формируем архив... Пожалуйста, подождите.")

    # Название папки — с подчёркиваниями вместо пробелов
    folder_name = order_title.replace(" ", "_")
    project_dir = os.path.join(BASE_DOC_PATH, folder_name)

    if not os.path.exists(project_dir):
        await callback.answer("❗ Папка проекта не найдена.", show_alert=True)
        return

    # Путь к временному ZIP-архиву
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_base_name = f"{folder_name}_{timestamp}"
    zip_path = os.path.join(BASE_DOC_PATH, f"{zip_base_name}.zip")

    # Создание архива
    shutil.make_archive(
        base_name=os.path.join(BASE_DOC_PATH, zip_base_name),
        format="zip",
        root_dir=project_dir
    )

    # Отправка архива пользователю
    try:
        await callback.message.bot.send_document(
            chat_id=callback.message.chat.id,
            document=FSInputFile(zip_path),
            caption=f"📦 Архив проекта: <b>{order_title}</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.answer("⚠️ Не удалось отправить архив.", show_alert=True)
        return
    finally:
        # Удаление архива после отправки
        if os.path.exists(zip_path):
            os.remove(zip_path)

    await callback.answer("✅ Архив проекта отправлен.")
    
def extract_with_cp1251(zip_path, dest_folder):
    with zipfile.ZipFile(zip_path) as zf:
        for zinfo in zf.infolist():
            try:
                raw_name = zinfo.filename.encode('cp437')
            except Exception:
                raw_name = zinfo.filename.encode(errors='replace')
            try:
                decoded_name = raw_name.decode('cp1251')
            except UnicodeDecodeError:
                try:
                    decoded_name = raw_name.decode('utf-8')
                except Exception:
                    decoded_name = zinfo.filename
            zinfo.filename = decoded_name
            zf.extract(zinfo, dest_folder)

def rename_folders_to_latin(base_folder):
    mapping = {
        "ИРД": "IRD",
        "ТУ": "TU",
        "Геология": "Geologia"
    }
    for old_name, new_name in mapping.items():
        old_path = os.path.join(base_folder, old_name)
        new_path = os.path.join(base_folder, new_name)
        if os.path.exists(old_path):
            os.rename(old_path, new_path)

def zip_folder(folder_path, zip_path):
    """Упаковать папку в zip."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                full_path = os.path.join(root, file)
                # относительный путь внутри архива
                rel_path = os.path.relpath(full_path, folder_path)
                zf.write(full_path, rel_path)

@router.callback_query(F.data.startswith("order_accept:"))
async def accept_order(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    await update_order_status(order_id, "approved")
    gip_id = callback.from_user.id
    await set_order_gip(order_id, gip_id)

    order = await get_order_by_id(order_id)
    title = order["title"]
    safe_title = re.sub(r'[^\w\-]', '_', title)
    project_folder = os.path.join("documents", safe_title)
    os.makedirs(project_folder, exist_ok=True)

    src_temp_file_path = order["document_url"]
    dest_file_path = os.path.join(project_folder, "ird1_file.zip")

    try:
        shutil.copy(src_temp_file_path, dest_file_path)

        # === 1. Распаковка ===
        extract_with_cp1251(dest_file_path, project_folder)

        # === 2. Переименовываем на латиницу ===
        rename_folders_to_latin(project_folder)

        # === 3. Архивируем нужные папки ===
        for folder_name in ["IRD", "TU", "Geologia"]:
            folder_path = os.path.join(project_folder, folder_name)
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                zip_path = os.path.join(project_folder, f"{folder_name}.zip")
                zip_folder(folder_path, zip_path)
                shutil.rmtree(folder_path)  # удаляем оригинальную папку

        # === 4. Удаляем лишнее ===
        for item in os.listdir(project_folder):
            if item not in ["IRD.zip", "TU.zip", "Geologia.zip", "ird1_file.zip"]:
                path = os.path.join(project_folder, item)
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)

        # === 5. Удаляем исходный архив из temporary ===
        if os.path.exists(src_temp_file_path):
            os.remove(src_temp_file_path)

        # === 6. Сохраняем путь в БД ===
        await update_order_document_url(order_id, project_folder)

        await callback.message.answer(
            f"📦 Исходный файл заказчика сохранён как <b>{safe_title}/ird1_file.zip</b>.\n"
            f"📂 Папки IRD, TU и Geologia упакованы в архивы.",
            parse_mode="HTML"
        )

    except Exception as e:
        await callback.message.answer(f"❗ Ошибка при обработке файла: {e}")
        return

    new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Передать ЭП", callback_data=f"assign_sketch:{order_id}")]
    ])
    if callback.message.caption:
        updated_caption = callback.message.caption + "\n\n✅ Заказ был принят. Теперь можно передать его эскизчику."
        await callback.message.edit_caption(caption=updated_caption, reply_markup=new_keyboard)
    else:
        updated_text = callback.message.text + "\n\n✅ Заказ был принят. Теперь можно передать его эскизчику."
        await callback.message.edit_text(text=updated_text, reply_markup=new_keyboard)
        
@router.callback_query(F.data.startswith("order_reject:"))
async def reject_order(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])

    orders = await get_all_orders()
    order = next((o for o in orders if o["id"] == order_id), None)

    if order:
        # Удаляем файл
        document_path = os.path.abspath(os.path.join(BASE_DOC_PATH, os.path.relpath(order["document_url"], "documents")))
        if os.path.exists(document_path):
            try:
                os.remove(document_path)
            except Exception as e:
                print(f"Ошибка при удалении файла: {e}")

        # Уведомляем заказчика
        customer_telegram_id = await get_customer_telegram_id(order["customer_id"])
        if customer_telegram_id:
            await callback.bot.send_message(
                chat_id=customer_telegram_id,
                text=(
                    f"🚫 Ваш заказ был отклонён.\n\n"
                    f"📌 <b>{order['title']}</b>\n"
                    f"📝 {order['description']}\n"
                    f"📅 Создан: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
                )
            )

        await delete_order(order_id)

    await callback.answer("Заказ отклонён и удалён ❌", show_alert=True)
    await callback.message.edit_text("❌ Заказ был отклонён и удалён.")
    
@router.callback_query(F.data.startswith("order_edit:"))
async def edit_order(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(EditOrder.waiting_for_comment)
    await state.update_data(order_id=order_id)
    await callback.answer()
    await callback.message.answer("✏️ Введите комментарий, который будет отправлен заказчику для исправления заказа:")


@router.message(EditOrder.waiting_for_comment)
async def process_edit_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    comment = message.text

    orders = await get_all_orders()
    order = next((o for o in orders if o["id"] == order_id), None)

    if not order:
        await message.answer("❗ Заказ не найден.")
        await state.clear()
        return

    customer_telegram_id = await get_customer_telegram_id(order["customer_id"])
    if customer_telegram_id:
        fix_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Загрузить исправленный архив", callback_data=f"start_fix:{order['id']}")]
        ])
        await message.bot.send_message(
            chat_id=customer_telegram_id,
            text=(
                f"✏️ Ваш заказ требует исправлений.\n"
                f"<b>Комментарий от ГИПа:</b> {comment}\n\n"
                f"📌 <b>{order['title']}</b>\n"
                f"📝 {order['description']}\n"
                f"📅 Создан: {order['created_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
                f"Пожалуйста, отправьте обновлённый архив."
            ),
            reply_markup=fix_kb
        )

    await message.answer("Комментарий отправлен заказчику ✉️")
    await state.clear()

@router.message(F.text == "📦 Текущие заказы")
async def show_orders_message(message: Message):
    await send_orders_to(message, message.answer)

@router.callback_query(F.data == "view_orders")
async def show_orders_callback(callback: CallbackQuery):
    await send_orders_to(callback.message, callback.message.answer)

# 💬 Общая функция отправки файлов
async def send_project_files(order_title: str, recipient_telegram_id: int, bot, role: str):
    # Тоже очищаем для consistency
    safe_title = re.sub(r'[^\w\-]', '_', order_title)

    folder_path = os.path.join(BASE_DOC_PATH, safe_title)

    if not os.path.exists(folder_path):
        await bot.send_message(recipient_telegram_id, f"❗️ Папка проекта <b>{order_title}</b> не найдена.", parse_mode="HTML")
        return

    if not os.listdir(folder_path):
        await bot.send_message(recipient_telegram_id, f"📁 Папка проекта <b>{order_title}</b> пуста.", parse_mode="HTML")
        return

    # 📁 Временный ZIP архив
    zip_filename = f"{safe_title}.zip"
    zip_path = os.path.join(BASE_DOC_PATH, "temporary", zip_filename)

    os.makedirs(os.path.dirname(zip_path), exist_ok=True)

    # 🗜 Архивация папки
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, folder_path)
                zipf.write(abs_path, arcname=rel_path)

    await bot.send_message(
        recipient_telegram_id,
        f"📦 Передан архив проекта <b>{order_title}</b> для роли: {role}",
        parse_mode="HTML"
    )
    await bot.send_document(recipient_telegram_id, FSInputFile(zip_path))

    try:
        os.remove(zip_path)
    except Exception as e:
        print(f"[WARN] Не удалось удалить временный ZIP: {e}")
# ✅ Передать расчетчику
@router.callback_query(F.data.startswith("assign_calculator:"))
async def assign_to_calculator(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.update_data(order_id=order_id)
    await state.set_state(AssignCalculatorFSM.waiting_for_description)

    await callback.message.answer("📝 Введите описание задания для расчетчика:")
    await callback.answer()

@router.message(AssignCalculatorFSM.waiting_for_description)
async def receive_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(AssignCalculatorFSM.waiting_for_deadline)
    await message.answer("📅 Укажите дедлайн в днях (например, 3):")

@router.message(AssignCalculatorFSM.waiting_for_deadline)
async def receive_deadline(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗ Введите положительное число (например, 5)")
        return

    data = await state.get_data()
    order_id = data["order_id"]
    description = data["description"]
    deadline = date.today() + timedelta(days=days)

    order = await get_order_by_id(order_id)
    calculator = await get_specialist_by_section("рс")
    if not calculator:
        await message.answer("❗ Расчетчик не найден.")
        await state.clear()
        return

    await create_task(
        order_id=order_id,
        section="рс",
        specialist_id=calculator["telegram_id"],
        description=description,
        deadline=deadline,
        status="назначено"
    )

    await send_project_files(order["title"], calculator["telegram_id"], message.bot, "рс")

    await message.answer("✅ Задание успешно создано и передано расчетчику.")
    await state.clear()

@router.callback_query(F.data.startswith("approve_calc:"))
async def handle_calc_approval(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    await callback.message.answer(f"📌 Расчёты. Одобряем заказ: {order_id}")

    # 🗂 Обновляем статусы
    await update_order_status(order_id, "waiting_cl")
    await update_task_status(order_id=order_id, section="рс", new_status="Сделано")

    # ✅ Уведомляем специалиста
    specialist = await get_specialist_by_order_and_section(order_id, "рс")
    if specialist:
        await callback.bot.send_message(
            chat_id=specialist["telegram_id"],
            text=f"✅ Ваш расчёт по заказу #{order_id} принят ГИПом."
        )

    # Получаем путь к файлу из tasks.document_url
    relative_task_file = await get_calc_task_document(order_id)

    if not relative_task_file:
        await callback.message.answer("❗️ Не найден файл Генплана (tasks.document_url).")
        return

    # Абсолютный путь до корня проекта
    BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot"))

    # Путь к исходному файлу из папки temporary
    source_abs_path = os.path.join(BASE_PATH, "documents", "temporary", os.path.basename(relative_task_file))

    if not os.path.exists(source_abs_path):
        await callback.message.answer("❗️ Файл не найден в папке temporary.")
        return

    # Получаем путь к папке проекта из order.document_url
    order = await get_order_by_id(order_id)
    document_url = order.get("document_url")
    if not document_url:
        await callback.message.answer("❗️ Не указан document_url у заказа.")
        return

    project_folder_rel = document_url.replace("\\", "/")  # На всякий случай
    project_abs_path = os.path.join(BASE_PATH, project_folder_rel)

    if not os.path.exists(project_abs_path):
        await callback.message.answer(f"❗️ Папка проекта не найдена: {project_abs_path}")
        return

    # Целевой путь для файла
    final_path = os.path.join(project_abs_path, "calc_files.zip")

    try:
        shutil.move(source_abs_path, final_path)
    except Exception as e:
        await callback.message.answer(f"❗️ Ошибка при перемещении файла: {e}")
        return

    # 💾 Обновляем путь в БД (tasks.document_url)
    await update_task_document_url(
        order_id=order_id,
        section="рс",
        document_url=os.path.join("documents", os.path.basename(project_folder_rel), "calc_files.zip")
    )

    # ✅ Подтверждение
    await callback.message.edit_reply_markup()
    await callback.message.answer("✅ Расчёт принят и файл сохранён в папке проекта как <b>calc_files.zip</b>.")
    await callback.answer("Файл принят ✅", show_alert=True)

@router.callback_query(F.data.startswith("revise_calc:"))
async def handle_calc_revision(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewCalcCorrectionFSM.waiting_for_comment)
    await state.update_data(order_id=order_id, section="рс")

    await callback.message.edit_reply_markup()
    await callback.message.answer("✏️ Напишите замечания по расчёту:")
    await callback.answer()

@router.message(ReviewCalcCorrectionFSM.waiting_for_comment)
async def handle_calc_correction_comment(message: Message, state: FSMContext):
    from database import get_specialist_by_order_and_section

    data = await state.get_data()
    order_id = data["order_id"]
    section = data["section"]  # должно быть 'рс'
    comment = message.text.strip()

    specialist = await get_specialist_by_order_and_section(order_id, section)

    if not specialist:
        await message.answer("❗️ Специалист по расчёту не найден.")
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

    await message.answer("✅ Замечания отправлены расчётчику.")
    await state.clear()

@router.callback_query(F.data.startswith("assign_genplan:"))
async def assign_to_genplanner(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)

    if not order:
        await callback.message.answer("❗ Заказ не найден.")
        await callback.answer()
        return

    await state.update_data(order_id=order_id)
    await state.set_state(AssignGenplanFSM.waiting_for_description)

    await callback.message.answer("📝 Введите описание задачи по разделу Генплан:")
    await callback.answer()

@router.message(AssignGenplanFSM.waiting_for_description)
async def get_genplan_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(AssignGenplanFSM.waiting_for_deadline)
    await message.answer("📅 Укажите срок выполнения (Введите количество дней, например: 7):")


@router.message(AssignGenplanFSM.waiting_for_deadline)
async def get_genplan_deadline(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    description = data["description"]
    days_str = message.text.strip()

    if not days_str.isdigit():
        await message.answer("❗ Введите количество дней, например: 7")
        return

    days = int(days_str)
    deadline = datetime.now() + timedelta(days=days)

    order = await get_order_by_id(order_id)
    order_title = order["title"]
    genplan = await get_specialist_by_section("гп")
    genplan_name = genplan.get("full_name", "Без имени")
    if not genplan:
        await message.answer("❗ Генпланист не найден.")
        await state.clear()
        return

    await create_task(
        order_id=order_id,
        section="гп",
        specialist_id=genplan["telegram_id"],
        description=description,
        deadline=deadline,
        status="assigned"
    )

    await send_project_files(order_title, genplan["telegram_id"], message.bot, "гп")

    await message.answer(
    f"✅ Задание по разделу <b>Генплан</b> передано генпланисту {genplan_name} со сроком {days} дн.",
    parse_mode="HTML"
)
    await state.clear()

@router.callback_query(F.data.startswith("approve_genplan:"))
async def handle_genplan_approval(callback: CallbackQuery):

    order_id = int(callback.data.split(":")[1])
    await callback.message.answer(f"📌 Генплан. Одобряем заказ: {order_id}")

    # Обновляем статусы
    await update_order_status(order_id, "waiting_cl")
    await update_task_status(order_id=order_id, section="гп", new_status="Сделано")

    # Уведомляем генпланиста
    specialist = await get_specialist_by_order_and_section(order_id, "гп")
    if specialist:
        await callback.bot.send_message(
            chat_id=specialist["telegram_id"],
            text=f"✅ Ваш файл по разделу Генплан по заказу #{order_id} принят ГИПом."
        )

    # Получаем путь к файлу из tasks.document_url
    relative_task_file = await get_genplan_task_document(order_id)

    if not relative_task_file:
        await callback.message.answer("❗️ Не найден файл Генплана (tasks.document_url).")
        return

    # Абсолютный путь до корня проекта
    BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot"))

    # Путь к исходному файлу из папки temporary
    source_abs_path = os.path.join(BASE_PATH, "documents", "temporary", os.path.basename(relative_task_file))

    if not os.path.exists(source_abs_path):
        await callback.message.answer("❗️ Файл не найден в папке temporary.")
        return

    # Получаем путь к папке проекта из order.document_url
    order = await get_order_by_id(order_id)
    document_url = order.get("document_url")
    if not document_url:
        await callback.message.answer("❗️ Не указан document_url у заказа.")
        return

    project_folder_rel = document_url.replace("\\", "/")  # На всякий случай
    project_abs_path = os.path.join(BASE_PATH, project_folder_rel)

    if not os.path.exists(project_abs_path):
        await callback.message.answer(f"❗️ Папка проекта не найдена: {project_abs_path}")
        return

    # Целевой путь сохранения
    final_path = os.path.join(project_abs_path, "genplan_files.zip")

    try:
        shutil.move(source_abs_path, final_path)
    except Exception as e:
        await callback.message.answer(f"❗️ Ошибка при перемещении файла: {e}")
        return

    # Убираем клавиатуру и завершаем
    await callback.message.edit_reply_markup()
        # После успешного перемещения
    await update_task_document_url(
        order_id=order_id,
        section="гп",
        document_url=os.path.join("documents", os.path.basename(project_folder_rel), "genplan_files.zip")
    )

    await callback.message.answer("✅ Раздел Генплан принят. Файл сохранён в папке проекта как <b>genplan_files.zip</b>.")
    await callback.answer("Файл принят ✅", show_alert=True)

# ❌ Замечания по генплану
@router.callback_query(F.data.startswith("revise_genplan:"))
async def handle_genplan_revision(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewGenplanCorrectionFSM.waiting_for_comment)
    await state.update_data(order_id=order_id, section="гп")

    await callback.message.edit_reply_markup()
    await callback.message.answer("✏️ Напишите замечания по Генплану:")
    await callback.answer()


# 📩 Получение замечания и отправка специалисту
@router.message(ReviewGenplanCorrectionFSM.waiting_for_comment)
async def handle_genplan_correction_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    section = data["section"]
    comment = message.text.strip()

    specialist = await get_specialist_by_order_and_section(order_id, section)

    if not specialist:
        await message.answer("❗️ Специалист по Генплану не найден.")
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

    await message.answer("✅ Замечания отправлены генпланисту.")
    await state.clear()


@router.callback_query(F.data.startswith("approve_estimate:"))
async def handle_approve_estimate(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    await callback.message.answer(f"📌 Смета. Одобряем заказ: {order_id}")

    # Обновляем статусы
    await update_order_status(order_id, "completed")
    await update_task_status(order_id=order_id, section="смета", new_status="Смета сделана")

    # Получаем путь к файлу сметы из tasks.document_url
    relative_task_file = await get_estimate_task_document(order_id)

    if not relative_task_file:
        await callback.message.answer("❗️ Не найден файл сметы (tasks.document_url).")
        return

    # Абсолютный путь до корня проекта
    BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot"))

    # Путь к исходному файлу из папки temporary
    source_abs_path = os.path.join(BASE_PATH, "documents", "temporary", os.path.basename(relative_task_file))

    if not os.path.exists(source_abs_path):
        await callback.message.answer(f"❗️ Файл сметы не найден в папке temporary: {source_abs_path}")
        return

    # Получаем путь к папке проекта из order.document_url
    order = await get_order_by_id(order_id)
    document_url = order.get("document_url")
    if not document_url:
        await callback.message.answer("❗️ Не указан document_url у заказа.")
        return

    project_folder_rel = document_url.replace("\\", "/")
    project_abs_path = os.path.join(BASE_PATH, project_folder_rel)

    if not os.path.exists(project_abs_path):
        await callback.message.answer(f"❗️ Папка проекта не найдена: {project_abs_path}")
        return

    # Целевой путь сохранения
    estimate_file_path = os.path.join(project_abs_path, "estimate_files.zip")

    try:
        shutil.move(source_abs_path, estimate_file_path)
    except Exception as e:
        await callback.message.answer(f"❗️ Ошибка при перемещении файла: {e}")
        return

    # После перемещения обновляем ссылку в БД
    await update_task_document_url(
        order_id=order_id,
        section="смета",
        document_url=os.path.join("documents", os.path.basename(project_folder_rel), "estimate_files.zip")
    )

    # Завершаем
    await callback.message.edit_reply_markup()
    await callback.message.answer("✅ Смета принята. Файл сохранён в папке проекта как <b>estimate_files.zip</b>.")
    await callback.answer("Файл сметы принят ✅", show_alert=True)

@router.message(lambda m: m.text and m.text.strip() == "📁 Завершённые заказы")
async def handle_completed_orders(message: types.Message):
    await send_completed_orders_to(message, message.answer)


async def send_completed_orders_to(recipient, send_method):
    orders = await get_completed_orders()

    if not orders:
        await send_method("📭 Нет завершённых заказов.")
        return
    
    for order in orders:
        text = (
            f"📌 <b>{order['title']}</b>\n"
            f"📝 {order['description']}\n"
            f"👤 Заказчик ID: {order['customer_id']}\n"
            f"📅 Создан: {order['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
            f"✅ Завершено"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Скачать весь проект", callback_data=f"send_project_zip:{order['id']}")]
        ])

        document_path = os.path.abspath(os.path.join(BASE_DOC_PATH, os.path.relpath(order["document_url"], "documents")))
        if os.path.exists(document_path):
            await send_method(text, reply_markup=keyboard)
        else:
            await send_method(f"{text}\n\n⚠️ Документ не найден по пути: {document_path}", reply_markup=keyboard)


@router.callback_query(F.data.startswith("assign_sm:"))
async def handle_assign_sm(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    smetchik = await get_specialist_by_section("смета")

    if not smetchik:
        await callback.message.answer("❗️ Сметчик не найден.")
        return

    await state.set_state(AssignSmetchikFSM.waiting_for_deadline)
    await state.update_data(
        order_id=order_id,
        specialist_id=smetchik["telegram_id"],
        title=order["title"]
    )

    await callback.message.answer("📅 Введите количество дней до дедлайна (например: 5):")
    await callback.answer()


@router.message(AssignSmetchikFSM.waiting_for_deadline)
async def receive_sm_deadline_days(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗️ Введите положительное число — количество дней до дедлайна.")
        return

    deadline = datetime.today().date() + timedelta(days=days)
    await state.update_data(deadline=deadline, days=days)
    await state.set_state(AssignSmetchikFSM.waiting_for_description)
    await message.answer("📝 Теперь введите описание задачи для сметчика:")


@router.message(AssignSmetchikFSM.waiting_for_description)
async def receive_sm_description(message: Message, state: FSMContext):
    data = await state.get_data()

    order_id = data["order_id"]
    specialist_id = data["specialist_id"]
    title = data["title"]
    deadline = data["deadline"]
    days = data["days"]
    description = message.text.strip()

    # Получаем все разделы заказа
    sections = await get_sections_by_order_id(order_id)  # [{'section': 'ар'}, {'section': 'кж'}, ...]

    await update_order_status(order_id, "assigned_sm")
    await create_task(
        order_id=order_id,
        section="смета",
        description=description,
        deadline=deadline,
        specialist_id=specialist_id,
        status="Разработка сметы"
    )

    caption = (
        f"📄 Новый заказ на разработку сметы:\n"
        f"📌 <b>{title}</b>\n"
        f"📝 {description}\n"
        f"📅 Дедлайн через {days} дн. ({deadline.strftime('%d.%m.%Y')})"
    )

    base_dir = os.path.join(os.getcwd(), "documents", title.replace(" ", "_"))

    all_files = []
    for sec in sections:
        section_name = sec["section"] if isinstance(sec, dict) else sec.section
        print(f"[DEBUG] Обрабатываем section: {section_name}")

        files = section_files_map.get(section_name.lower())
        if not files:
            continue

        for file_name in files:
            file_path = os.path.join(base_dir, file_name)
            if os.path.exists(file_path):
                all_files.append(file_path)
            else:
                await message.answer(f"⚠️ Файл не найден: {file_path}")

    # Создаём общий архив
    if all_files:
        archive_path = os.path.join(base_dir, "combined_files.zip")
        with zipfile.ZipFile(archive_path, 'w') as archive:
            for file_path in all_files:
                archive.write(file_path, arcname=os.path.basename(file_path))

        # Отправляем архив
        await message.bot.send_document(
            chat_id=specialist_id,
            document=FSInputFile(archive_path),
            caption=caption,
            parse_mode="HTML"
        )
    else:
        await message.answer("⚠️ Не найдено ни одного файла для архивации.")

    await message.answer("✅ Задание передано сметчику.")
    await state.clear()


@router.callback_query(F.data.startswith("attach_pz:"))
async def handle_attach_pz(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.update_data(order_id=order_id, file_type="pz")
    await callback.message.answer("📎 Отправьте файл пояснительной записки (ZIP)")
    await state.set_state("waiting_for_pz_file")

@router.message(AttachFilesFSM.waiting_for_pz_file, F.document)
async def save_pz_file(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]

    order = await get_order_by_id(order_id)
    project_folder = os.path.join(BASE_DOC_PATH, os.path.basename(order["document_url"]))
    os.makedirs(project_folder, exist_ok=True)

    file = await message.document.download(destination_file=os.path.join(project_folder, "ПЗ.zip"))
    await message.answer("✅ Пояснительная записка сохранена в проекте.")
    await state.clear()


@router.callback_query(F.data.startswith("attach_pos:"))
async def handle_attach_pos(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.update_data(order_id=order_id, file_type="pos")
    await callback.message.answer("📎 Отправьте файл ПОС (ZIP)")
    await state.set_state(AttachFilesFSM.waiting_for_pos_file)

@router.message(AttachFilesFSM.waiting_for_pos_file, F.document)
async def save_pos_file(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]

    order = await get_order_by_id(order_id)
    project_folder = os.path.join(BASE_DOC_PATH, os.path.basename(order["document_url"]))
    os.makedirs(project_folder, exist_ok=True)

    await message.document.download(destination_file=os.path.join(project_folder, "ПОС.zip"))
    await message.answer("✅ ПОС сохранён в проекте.")
    await state.clear()