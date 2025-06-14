from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, Document
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database import get_orders_by_specialist_id, get_order_by_id, get_available_ar_executors, assign_ar_executor_to_order, get_ar_executors_by_order, get_executors_for_order, update_task_for_executor, get_unassigned_executors, assign_executor_to_ar, get_user_by_id, get_user_by_telegram_id, count_executors_for_order, get_task_executor_id , get_ar_executor_by_task_executor_id, save_ar_file_path_to_tasks
import os
from datetime import datetime, date, timedelta
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Bot

class GiveTaskARFSM(StatesGroup):
    waiting_for_comment = State()
    waiting_for_deadline = State()


class TaskAssignmentFSM(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_deadline = State()


router = Router()
TEMP_DOC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents", "temporary"))
BASE_DOC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents"))

class SubmitArFSM(StatesGroup):
    waiting_for_file = State()

def get_gip_review_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"gip_ar_approve:{order_id}"),
            InlineKeyboardButton(text="❌ Требует исправлений", callback_data=f"gip_ar_reject:{order_id}")
        ]
    ])

@router.message(F.text == "📄 Мои задачи")
async def show_ar_orders(message: Message):
    orders = await get_orders_by_specialist_id(message.from_user.id, section="ар")

    if not orders:
        await message.answer("📭 У вас пока нет задач.")
        return

    for order in orders:
        order_id = order["id"]
        status = order["status"]
        doc_path = os.path.abspath(os.path.join(BASE_DOC_PATH, os.path.relpath(order["document_url"], "documents")))

        buttons = []

        # Если заказ на этапе назначения исполнителей
        if status == "assigned_ar":
            buttons.append(InlineKeyboardButton(text="👥 Назначить исполнителей", callback_data=f"assign_ar_execs:{order_id}"))

        # Если уже есть исполнители
        executors = await get_ar_executors_by_order(order_id)
        if executors:
            buttons.append(InlineKeyboardButton(text="📤 Дать задание", callback_data=f"give_task_ar:{order_id}"))

        # Добавляем кнопку "Отправить на проверку" всегда
        buttons.append(InlineKeyboardButton(text="📤 Отправить на проверку", callback_data=f"submit_ar:{order_id}"))

        keyboard = InlineKeyboardMarkup(inline_keyboard=[[button] for button in buttons]) if buttons else None

        if os.path.exists(doc_path):
            caption = (
                f"📌 <b>{order['title']}</b>\n"
                f"📝 {order['description']}\n"
                f"📅 Создан: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
            )
            await message.answer_document(FSInputFile(doc_path), caption=caption, reply_markup=keyboard)
        else:
            await message.answer(f"⚠️ Документ не найден: {order['title']}")

@router.callback_query(F.data.startswith("submit_ar:"))
async def handle_submit_ar(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(SubmitArFSM.waiting_for_file)
    await state.update_data(order_id=order_id)
    await callback.answer()
    await callback.message.answer("📎 Отправьте PDF файл АР для проверки ГИПом:")

@router.message(SubmitArFSM.waiting_for_file, F.document)
async def receive_ar_document(message: Message, state: FSMContext, bot: Bot):


    data = await state.get_data()
    order_id = data.get("order_id")
    document: Document = message.document

    if not document.file_name.lower().endswith(".zip"):
        await message.answer("❗️ Пожалуйста, отправьте файл в формате ZIP (.zip).")
        return

    # 📁 Путь к временной папке
    os.makedirs(TEMP_DOC_PATH, exist_ok=True)

    # 🧹 Удалим предыдущие файлы submitted_{order_id}_*
    prefix = f"submitted_{order_id}_"
    for filename in os.listdir(TEMP_DOC_PATH):
        if filename.startswith(prefix):
            path_to_delete = os.path.join(TEMP_DOC_PATH, filename)
            try:
                os.remove(path_to_delete)
            except Exception as e:
                print(f"[WARN] Не удалось удалить старый файл: {path_to_delete} — {e}")

    # 💾 Генерация имени нового файла
    filename = f"submitted_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{document.file_name}"
    save_path = os.path.join(TEMP_DOC_PATH, filename)

    # 📥 Скачиваем файл
    file = await bot.get_file(document.file_id)
    await bot.download_file(file.file_path, destination=save_path)

    # 📌 Сохраняем относительный путь (относительно documents/)
    relative_path = os.path.relpath(save_path, os.path.join(TEMP_DOC_PATH, ".."))

    # ✅ Записываем путь в tasks.document_url
    await save_ar_file_path_to_tasks(order_id, relative_path)

    # 📤 Отправляем ГИПу
    order = await get_order_by_id(order_id)
    gip_telegram_id = order["gip_id"]

    await bot.send_document(
        chat_id=gip_telegram_id,
        document=FSInputFile(save_path),
        caption=f"📩 Получен файл АР от специалиста по заказу: <b>{order['title']}</b>",
        parse_mode="HTML",
        reply_markup=get_gip_review_keyboard(order['id'])
    )

    await message.answer("✅ АР отправлен ГИПу на проверку.")
    await state.clear()


@router.callback_query(F.data.startswith("assign_ar_execs:"))
async def assign_ar_execs(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    available_execs = await get_available_ar_executors(order_id)

    if not available_execs:
        await callback.message.answer("❗ Нет доступных исполнителей для назначения.")
        await callback.answer()
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ex["full_name"], callback_data=f"ar_pick_exec:{order_id}:{ex['telegram_id']}")]
        for ex in available_execs
    ])
    await callback.message.answer("Выберите исполнителя для назначения:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("ar_pick_exec:"))
async def confirm_ar_exec(callback: CallbackQuery):
    _, order_id, exec_tg_id = callback.data.split(":")
    specialist_tg_id = callback.from_user.id
    # 🔒 Проверка: не более 3 исполнителей
    current_count = await count_executors_for_order(order_id=int(order_id))
    if current_count >= 3:
        await callback.answer("❗ Уже назначено 3 исполнителя для этого заказа.", show_alert=True)
        return
    # Назначение исполнителя
    await assign_ar_executor_to_order(
        order_id=int(order_id),
        executor_telegram_id=int(exec_tg_id),
        specialist_telegram_id=int(specialist_tg_id)
    )

    # Уведомление исполнителю
    executor_telegram_id = int(exec_tg_id)
    executor_user = await get_user_by_telegram_id(executor_telegram_id)
    if executor_user:
        await callback.bot.send_message(
            chat_id=executor_telegram_id,
            text=f"📌 Вам назначена новая задача по заказу #{order_id} от специалиста АР.",
        )

    # Удаление кнопки исполнителя из сообщения
    original_markup = callback.message.reply_markup
    if original_markup:
        new_buttons = []
        for row in original_markup.inline_keyboard:
            new_row = [btn for btn in row if callback.data not in btn.callback_data]
            if new_row:
                new_buttons.append(new_row)

        new_markup = InlineKeyboardMarkup(inline_keyboard=new_buttons)
        await callback.message.edit_reply_markup(reply_markup=new_markup)

    await callback.answer("Назначено ✅", show_alert=True)

@router.callback_query(F.data.startswith("give_task_ar:"))
async def handle_give_task_ar(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    executors = await get_executors_for_order(order_id, section='ар')

    if not executors:
        await callback.message.answer("❗ Нет назначенных исполнителей для этого заказа.")
        await callback.answer()
        return

    # Сохраняем order_id в FSM
    await state.update_data(order_id=order_id)

    # Показываем всех исполнителей (task_executor_id нужен для точного обновления)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=executor['full_name'], callback_data=f"select_ar_executor:{executor['task_executor_id']}")]
        for executor in executors
    ])

    await callback.message.answer("👤 Выберите исполнителя, которому вы хотите выдать задачу:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("select_ar_executor:"))
async def handle_select_ar_executor(callback: CallbackQuery, state: FSMContext):
    task_executor_id = int(callback.data.split(":")[1])

    # Получаем executor_id и order_id (сделаем запрос расширенным)
    executor_row = await get_ar_executor_by_task_executor_id(task_executor_id)
    if not executor_row:
        await callback.message.answer("❗ Не удалось найти исполнителя.")
        return

    await state.update_data(
        task_executor_id=task_executor_id,
        executor_id=executor_row["executor_id"],  # telegram_id
        full_name=executor_row["full_name"],
        order_id=executor_row["order_id"],        # 👈 добавляем сюда!
        title=executor_row["title"]               # 👈 если нужно для сообщения
    )

    await state.set_state(GiveTaskARFSM.waiting_for_comment)
    await callback.message.answer("📝 Введите описание задания:")
    await callback.answer()


@router.message(GiveTaskARFSM.waiting_for_comment)
async def handle_task_comment(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(GiveTaskARFSM.waiting_for_deadline)
    await message.answer("📅 Введите дедлайн в днях (например, 5):")
    
@router.message(GiveTaskARFSM.waiting_for_deadline)
async def handle_task_deadline(message: Message, state: FSMContext):
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
        deadline = date.today() + timedelta(days=days)
    except ValueError:
        await message.answer("❗ Введите положительное число дней, например: 5")
        return

    data = await state.get_data()
    order_id = data["order_id"]
    executor_id = data["executor_id"]
    description = data["description"]
    specialist_id = message.from_user.id  # Кто выдал задание

    # Получаем ID задачи в task_executors
    task_executor_id = await get_task_executor_id(order_id, executor_id)
    await update_task_for_executor(task_executor_id, description, deadline)
    # Отправляем сообщение исполнителю
    executor = await get_user_by_telegram_id(executor_id)
    if executor:
        await message.bot.send_message(
            chat_id=executor["telegram_id"],
            text=(
                f"📌 Вам назначена задача по заказу #{order_id}:\n\n"
                f"<b>{data['title']}</b>\n"
                f"{description}\n"
                f"🕒 Дедлайн: {deadline.strftime('%Y-%m-%d')} (через {days} дней)"
            ),
            parse_mode="HTML"
        )

    await message.answer("✅ Задание выдано исполнителю.")
    await state.clear()


@router.message(F.text == "Нанять исполнителя")
async def handle_hire_executor(message: Message):
    executors = await get_unassigned_executors()

    if not executors:
        await message.answer("📭 Нет доступных исполнителей без отдела.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=executor["full_name"], callback_data=f"hire_ar:{executor['id']}")]
            for executor in executors
        ]
    )

    await message.answer("👥 Выберите исполнителя для отдела АР:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("hire_ar:"))
async def process_executor_hire(callback: CallbackQuery):
    executor_id = int(callback.data.split(":")[1])

    # Обновляем section на "ар"
    await assign_executor_to_ar(executor_id)

    # Получаем исполнителя
    executor = await get_user_by_id(executor_id)

    # Уведомляем исполнителя
    if executor and executor["telegram_id"]:
        try:
            await callback.bot.send_message(
                chat_id=executor["telegram_id"],
                text="👷 Вы были назначены исполнителем в отдел АР. Ожидайте задачи от специалиста."
            )
        except Exception as e:
            print(f"Ошибка при отправке уведомления исполнителю: {e}")

    # Подтверждение специалисту
    await callback.answer("✅ Исполнитель добавлен в отдел АР", show_alert=True)
    await callback.message.edit_text("✅ Исполнитель успешно назначен в отдел АР.")
