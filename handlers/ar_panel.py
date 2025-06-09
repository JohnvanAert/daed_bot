from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, Document
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database import get_orders_by_specialist_id, get_order_by_id, get_available_ar_executors, assign_ar_executor_to_order, get_ar_executors_by_order, get_executors_for_order, update_task_for_executor, get_unassigned_executors, assign_executor_to_ar, get_user_by_id, get_user_by_telegram_id
import os
from datetime import datetime, date, timedelta


class GiveTaskARFSM(StatesGroup):
    waiting_for_comment = State()
    waiting_for_deadline = State()

router = Router()
BASE_DOC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents"))

class SubmitArFSM(StatesGroup):
    waiting_for_file = State()

def get_gip_review_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Передать заказчику", callback_data=f"gip_approve:{order_id}"),
            InlineKeyboardButton(text="❌ Требует исправлений", callback_data=f"gip_reject:{order_id}")
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
async def receive_ar_document(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")

    document: Document = message.document
    if not document.file_name.lower().endswith(".pdf"):
        await message.answer("❗ Пожалуйста, отправьте файл в формате PDF.")
        return

    order = await get_order_by_id(order_id)
    gip_telegram_id = order["gip_id"]

    await message.bot.send_document(
        chat_id=gip_telegram_id,
        document=document.file_id,
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
    specialist_tg_id = callback.from_user.id  # кто нажал — это и есть специалист

    # Вызов с именованными аргументами
    await assign_ar_executor_to_order(
        order_id=int(order_id),
        executor_telegram_id=int(exec_tg_id),
        specialist_telegram_id=int(specialist_tg_id)
    )

    executor_telegram_id = int(exec_tg_id)
    executor_user = await get_user_by_telegram_id(executor_telegram_id)
    if executor_user:
        await callback.bot.send_message(
            chat_id=executor_telegram_id,
            text=f"📌 Вам назначена новая задача по заказу #{order_id} от специалиста АР.",
        )

    await callback.message.answer("✅ Исполнитель назначен.")
    await callback.answer("Назначено ✅", show_alert=True)

@router.callback_query(F.data.startswith("give_task_ar:"))
async def handle_give_task_ar(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    executors = await get_executors_for_order(order_id, section='ар')

    if not executors:
        await callback.message.answer("❗ Нет назначенных исполнителей для этого заказа.")
        return

    # Сохраняем order_id в FSM
    await state.update_data(order_id=order_id)

    # Показываем всех исполнителей как инлайн кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=executor['username'], callback_data=f"select_ar_executor:{executor['id']}")]
        for executor in executors
    ])

    await callback.message.answer("👤 Выберите исполнителя, которому вы хотите выдать задачу:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("select_ar_executor:"))
async def handle_select_ar_executor(callback: CallbackQuery, state: FSMContext):
    executor_id = int(callback.data.split(":")[1])
    await state.update_data(executor_id=executor_id)

    await state.set_state(GiveTaskARFSM.waiting_for_comment)
    await callback.message.answer("📝 Введите описание задания:")
    await callback.answer()


@router.message(GiveTaskARFSM.waiting_for_comment)
async def handle_task_comment(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(GiveTaskARFSM.waiting_for_deadline)
    await message.answer("📅 Введите дедлайн в формате ГГГГ-ММ-ДД (например, 2025-06-15):")


@router.message(GiveTaskARFSM.waiting_for_deadline)
async def handle_task_deadline(message: Message, state: FSMContext):
    try:
        deadline = datetime.strptime(message.text.strip(), "%Y-%m-%d").date()
    except ValueError:
        await message.answer("❗ Неверный формат. Введите дату как: 2025-06-15")
        return

    data = await state.get_data()
    order_id = data["order_id"]
    executor_id = data["executor_id"]
    description = data["description"]
    specialist_id = message.from_user.id  # Текущий специалист

    # Обновляем задачу
    await update_task_for_executor(order_id, executor_id, description, deadline)

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