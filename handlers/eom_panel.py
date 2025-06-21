from aiogram import Router, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, FSInputFile, Document
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import (
    get_orders_by_specialist_id,
    save_eom_file_path_to_tasks,
    get_order_by_id,
    get_unassigned_executors,
    get_user_by_id,
    get_available_eom_executors,
    count_executors_for_order,
    assign_executor_to_eom_order,
    get_user_by_telegram_id,
    assign_executor_to_section
)
from datetime import datetime
import os

router = Router()

EOM_TEMP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents", "temporary"))

class SubmitEomFSM(StatesGroup):
    waiting_for_file = State()

# 📄 Панель ЭОМ
@router.message(F.text == "📄 Мои задачи по эом")
async def show_eom_tasks(message: Message):
    orders = await get_orders_by_specialist_id(message.from_user.id, section="эом")
    

    if not orders:
        await message.answer("📭 У вас пока нет задач.")
        return

    for order in orders:
        order_id = order["id"]
        status = order.get("status", "не указано")
        caption = (
            f"📌 <b>{order.get('title', 'Без названия')}</b>\n"
            f"📝 {order.get('description', 'Без описания')}\n"
            f"📅 Дата: {order.get('created_at', '???')}"
        )

        buttons = []
        if status == "assigned_eom":
            buttons.append(InlineKeyboardButton(text="👥 Назначить исполнителей по ЭОМ", callback_data=f"assign_eom_execs:{order_id}"))
        buttons.append(InlineKeyboardButton(text="📤 Отправить на проверку ЭОМ", callback_data=f"submit_eom:{order_id}"))

        keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])
        await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)

# 📨 Ожидание ZIP от ЭОМ-специалиста
@router.callback_query(F.data.startswith("submit_eom:"))
async def handle_eom_submit(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(SubmitEomFSM.waiting_for_file)
    await state.update_data(order_id=order_id)

    await callback.message.answer("📎 Прикрепите ZIP файл по разделу ЭОМ.")
    await callback.answer()

# 💾 Обработка файла ЭОМ
@router.message(SubmitEomFSM.waiting_for_file, F.document)
async def receive_eom_file(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    order_id = data["order_id"]
    document: Document = message.document

    if not document.file_name.lower().endswith(".zip"):
        await message.answer("❗️ Отправьте файл в формате ZIP.")
        return

    os.makedirs(EOM_TEMP_PATH, exist_ok=True)

    filename = f"eom_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{document.file_name}"
    save_path = os.path.join(EOM_TEMP_PATH, filename)

    file = await bot.get_file(document.file_id)
    await bot.download_file(file.file_path, destination=save_path)

    relative_path = os.path.relpath(save_path, os.path.join(EOM_TEMP_PATH, ".."))
    await save_eom_file_path_to_tasks(order_id, relative_path)

    order = await get_order_by_id(order_id)
    gip_id = order["gip_id"]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"gip_eom_approve:{order_id}"),
            InlineKeyboardButton(text="❌ Исправить", callback_data=f"gip_eom_reject:{order_id}")
        ]
    ])

    await bot.send_document(
        chat_id=gip_id,
        document=FSInputFile(save_path),
        caption=f"📩 Получен ZIP файл от специалиста по ЭОМ по заказу <b>{order['title']}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await message.answer("✅ Файл ЭОМ отправлен ГИПу.")
    await state.clear()


@router.callback_query(F.data.startswith("assign_eom_execs:"))
async def assign_eom_execs(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    available_execs = await get_available_eom_executors(order_id)

    if not available_execs:
        await callback.message.answer("❗ Нет доступных исполнителей для назначения.")
        await callback.answer()
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ex["full_name"], callback_data=f"eom_pick_exec:{order_id}:{ex['telegram_id']}")]
        for ex in available_execs
    ])
    await callback.message.answer("Выберите исполнителя для ЭОМ:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("eom_pick_exec:"))
async def confirm_eom_exec(callback: CallbackQuery):
    _, order_id, exec_tg_id = callback.data.split(":")
    specialist_tg_id = callback.from_user.id

    # Проверка: не более 3 исполнителей
    current_count = await count_executors_for_order(order_id=int(order_id), section="эом")
    if current_count >= 3:
        await callback.answer("❗ Уже назначено 3 исполнителя на ЭОМ.", show_alert=True)
        return

    # Назначение исполнителя
    await assign_executor_to_eom_order(
        order_id=int(order_id),
        executor_telegram_id=int(exec_tg_id),
        specialist_telegram_id=int(specialist_tg_id)
    )

    # Уведомление исполнителю
    executor_user = await get_user_by_telegram_id(int(exec_tg_id))
    if executor_user:
        await callback.bot.send_message(
            chat_id=executor_user["telegram_id"],
            text=f"📌 Вы были назначены на задачу ЭОМ по заказу #{order_id}."
        )

    # Удаление кнопки из клавиатуры
    original_markup = callback.message.reply_markup
    if original_markup:
        new_buttons = []
        for row in original_markup.inline_keyboard:
            new_row = [btn for btn in row if callback.data not in btn.callback_data]
            if new_row:
                new_buttons.append(new_row)

        await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=new_buttons))

    await callback.answer("Назначено ✅", show_alert=True)


@router.message(F.text == "Нанять исполнителя по эом")
async def handle_hire_executor_eom(message: Message):
    executors = await get_unassigned_executors()

    if not executors:
        await message.answer("📭 Нет доступных исполнителей без отдела.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=executor["full_name"], callback_data=f"hire_eom:{executor['id']}")]
            for executor in executors
        ]
    )

    await message.answer("👥 Выберите исполнителя для отдела ЭОМ:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("hire_eom:"))
async def process_executor_hire_eom(callback: CallbackQuery):
    executor_id = int(callback.data.split(":")[1])

    # Привязываем исполнителя к разделу "эом"
    await assign_executor_to_section(executor_id, section="эом")

    # Получаем информацию об исполнителе
    executor = await get_user_by_id(executor_id)

    if executor and executor["telegram_id"]:
        try:
            await callback.bot.send_message(
                chat_id=executor["telegram_id"],
                text="👷 Вы были назначены исполнителем в отдел ЭОМ. Ожидайте задачи от специалиста."
            )
        except Exception as e:
            print(f"Ошибка при отправке уведомления исполнителю: {e}")

    await callback.answer("✅ Исполнитель назначен в отдел ЭОМ", show_alert=True)
    await callback.message.edit_text("✅ Исполнитель успешно добавлен в отдел ЭОМ.")

