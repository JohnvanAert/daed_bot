from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from database import get_all_orders, get_customer_telegram_id, create_task, get_order_by_id, get_specialist_by_section, get_specialist_by_order_and_section, update_task_status, get_genplan_task_document, get_calc_task_document, update_task_document_path
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
import zipfile
import shutil
load_dotenv()
router = Router()
ALLOWED_STATUSES = {
    "assigned_vk", "approved_gs", "assigned_gs", "approved_ovik", "approve_ovik",
    "assigned_ovik", "approved_kj", "approve_kj", "assigned_kj", "approved_ss",
    "gip_ss_approve", "assigned_ss", "approved_eom", "gip_eom_approve", "assigned_eom",
    "approved_vk", "gip_vk_approve"
}
BASE_DOC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents"))
# Initialize the client bot with the token from environment variables
client_bot = Bot(
    token=os.getenv("CLIENT_BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

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
        elif order["status"] in ALLOWED_STATUSES:
            keyboard_buttons = [
                [
                    InlineKeyboardButton(text="📤 Передать ОВиК/ТС", callback_data=f"assign_ovik:{order['id']}"),
                    InlineKeyboardButton(text="📤 Передать ВК/НВК", callback_data=f"assign_vk:{order['id']}")
                ],
                [
                    InlineKeyboardButton(text="📤 Передать ВГС/НГС", callback_data=f"assign_gs:{order['id']}"),
                    InlineKeyboardButton(text="📤 Передать КЖ", callback_data=f"assign_kj:{order['id']}")
                ],
                [
                    InlineKeyboardButton(text="📤 Передать ЭОМ", callback_data=f"assign_eom:{order['id']}"),
                    InlineKeyboardButton(text="📤 Передать СС", callback_data=f"assign_ss:{order['id']}")
                ],
                [
                    InlineKeyboardButton(text="📤 Передать экспертам", callback_data=f"send_to_expert:{order['id']}")
                ]
            ]
            
        else:
                keyboard_buttons = []

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        document_path = os.path.abspath(os.path.join(BASE_DOC_PATH, os.path.relpath(order["document_url"], "documents")))

        if os.path.exists(document_path):
            doc = FSInputFile(document_path)
            await bot.send_document(chat_id=recipient.chat.id, document=doc, caption=text, reply_markup=keyboard)
        else:
            await send_method(f"{text}\n\n⚠️ Документ не найден по пути: {document_path}", reply_markup=keyboard)

@router.callback_query(F.data.startswith("order_accept:"))
async def accept_order(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    await update_order_status(order_id, "approved")
    gip_id = callback.from_user.id  # получаем telegram ID ГИПа
    await set_order_gip(order_id, gip_id)
    original_caption = callback.message.caption or ""
    updated_caption = original_caption + "\n\n✅ Заказ был принят. Теперь можно передать его эскизчику."
    new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Передать ЭП", callback_data=f"assign_sketch:{order_id}")]
        ])
    await callback.message.edit_caption(caption=updated_caption, reply_markup=new_keyboard)
    await callback.answer("Заказ принят ✅", show_alert=True)
    await callback.message.answer("✅ Заказ был принят. Теперь можно передать его эскизчику.")




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
        await client_bot.send_message(
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

@router.message(F.text == "📦 Заказы")
async def show_orders_message(message: Message):
    await send_orders_to(message, message.answer)

@router.callback_query(F.data == "view_orders")
async def show_orders_callback(callback: CallbackQuery):
    await send_orders_to(callback.message, callback.message.answer)

# 💬 Общая функция отправки файлов
async def send_project_files(order_title: str, recipient_telegram_id: int, bot, role: str):
    folder_path = os.path.join(BASE_DOC_PATH, order_title)

    if not os.path.exists(folder_path):
        await bot.send_message(recipient_telegram_id, f"❗️ Папка проекта {order_title} не найдена.")
        return

    if not os.listdir(folder_path):
        await bot.send_message(recipient_telegram_id, f"📁 Папка проекта {order_title} пуста.")
        return

    # 📁 Временный ZIP архив
    zip_filename = f"{order_title}.zip"
    zip_path = os.path.join(BASE_DOC_PATH, "temporary", zip_filename)

    os.makedirs(os.path.dirname(zip_path), exist_ok=True)

    # 🗜 Архивация папки
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, folder_path)
                zipf.write(abs_path, arcname=rel_path)

    # 📤 Отправка архива
    await bot.send_message(
        recipient_telegram_id,
        f"📦 Передан архив проекта <b>{order_title}</b> для роли: {role}",
        parse_mode="HTML"
    )
    await bot.send_document(recipient_telegram_id, FSInputFile(zip_path))

    # ✅ При желании: удалить ZIP после отправки
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

    # 🗂 Обновляем статус заказа и задачи
    await update_order_status(order_id, "waiting_cl")
    await update_task_status(order_id=order_id, section="рс", new_status="Сделано")

    # ✅ Уведомляем специалиста
    specialist = await get_specialist_by_order_and_section(order_id, "рс")
    if specialist:
        await callback.bot.send_message(
            chat_id=specialist["telegram_id"],
            text=f"✅ Ваш расчёт по заказу #{order_id} принят ГИПом."
        )

    # 📥 Получаем путь к файлу
    relative_path = await get_calc_task_document(order_id)
    if not relative_path:
        await callback.message.answer("❗️ Не удалось найти файл расчёта в tasks.")
        return

    # 📂 Пути
    TEMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents", "temporary"))
    SOURCE_PATH = os.path.join(TEMP_DIR, os.path.basename(relative_path))

    order = await get_order_by_id(order_id)
    project_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", order["document_url"]))
    PROJECT_DIR = os.path.dirname(project_file_path)

    os.makedirs(PROJECT_DIR, exist_ok=True)
    TARGET_PATH = os.path.join(PROJECT_DIR, "calc_files.zip")

    try:
        shutil.move(SOURCE_PATH, TARGET_PATH)
    except Exception as e:
        await callback.message.answer(f"❗️ Ошибка при перемещении файла: {e}")
        return

    # 💾 Обновляем путь в tasks.document_url
    new_relative_path = os.path.relpath(TARGET_PATH, os.path.join(PROJECT_DIR, ".."))
    await update_task_document_path(order_id, "рс", new_relative_path)

    # ✅ Ответы
    await callback.message.edit_reply_markup()
    await callback.message.answer("✅ Расчёт принят и файл сохранён в папке проекта как <b>calc_files.zip</b>.")
    await callback.answer("Принято ✅", show_alert=True)

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
        f"✅ Задание по разделу <b>Генплан</b> передано генпланисту {genplan['full_name']} со сроком {days} дн.",
        parse_mode="HTML"
    )
    await state.clear()

@router.callback_query(F.data.startswith("approve_genplan:"))
async def handle_genplan_approval(callback: CallbackQuery):

    order_id = int(callback.data.split(":")[1])

    # Обновляем статус заказа
    await update_order_status(order_id, "waiting_cl")

    # Обновляем статус задачи по генплану
    await update_task_status(order_id=order_id, section="гп", new_status="Сделано")

    # Уведомляем генпланиста
    specialist = await get_specialist_by_order_and_section(order_id, "гп")
    if specialist:
        await callback.bot.send_message(
            chat_id=specialist["telegram_id"],
            text=f"✅ Ваш файл по разделу Генплан по заказу #{order_id} принят ГИПом."
        )

    # 🔍 Получаем путь к файлу генплана из tasks.document_url
    relative_path = await get_genplan_task_document(order_id)
    if not relative_path:
        await callback.message.answer("❗️ Не удалось найти файл Генплана в tasks.")
        return

    # Абсолютный путь к исходному файлу
    TEMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents", "temporary"))
    SOURCE_PATH = os.path.join(TEMP_DIR, os.path.basename(relative_path))

    # Папка проекта
    order = await get_order_by_id(order_id)
    project_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", order["document_url"]))
    PROJECT_DIR = os.path.dirname(project_folder)  # убираем имя файла, оставляем только папку
    
    os.makedirs(PROJECT_DIR, exist_ok=True)
    TARGET_PATH = os.path.join(PROJECT_DIR, "genplan_files.zip")

    try:
        shutil.move(SOURCE_PATH, TARGET_PATH)
    except Exception as e:
        await callback.message.answer(f"❗️ Ошибка при перемещении файла: {e}")
        return

    await callback.message.edit_reply_markup()
    await callback.message.answer("✅ Генплан принят и файл сохранён в папке проекта как <b>genplan_files.zip</b>.")
    await callback.answer("Принято ✅", show_alert=True)

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