from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile, Document
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import get_orders_by_specialist_id, save_ovik_file_path_to_tasks, get_order_by_id, assign_executor_to_section, get_user_by_id, get_unassigned_executors, get_available_ovik_executors, count_executors_for_order, assign_executor_to_ovik_order, get_user_by_telegram_id

import os
from datetime import datetime

router = Router()

OVIK_TEMP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents", "temporary"))

class SubmitOvikFSM(StatesGroup):
    waiting_for_file = State()

# 📄 Панель ОВиК
@router.message(F.text == "📄 Мои задачи по тс/ов")
async def show_ovik_tasks(message: Message):
    orders = await get_orders_by_specialist_id(message.from_user.id, section="овик")
    if not orders:
        await message.answer("📭 У вас пока нет задач.")
        return

    for order in orders:
        order_id = order["id"]
        status = order["status"]
        caption = (
            f"📌 <b>{order['title']}</b>\n"
            f"📝 {order['description']}\n"
            f"📅 {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )
        buttons = []
        if status == "assigned_ovik":
            buttons.append(InlineKeyboardButton(text="👥 Назначить исполнителей", callback_data=f"assign_ovik_execs:{order_id}"))
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Отправить результат", callback_data=f"submit_ovik:{order['id']}")]
        ])
        await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)

# 🔄 Ожидание загрузки файла
@router.callback_query(F.data.startswith("submit_ovik:"))
async def handle_ovik_submit(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(SubmitOvikFSM.waiting_for_file)
    await state.update_data(order_id=order_id)
    await callback.message.answer("📎 Прикрепите ZIP файл с результатами по ОВиК.")
    await callback.answer()

# 📥 Получение файла
@router.message(SubmitOvikFSM.waiting_for_file, F.document)
async def receive_ovik_file(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    order_id = data["order_id"]
    document: Document = message.document

    if not document.file_name.lower().endswith(".zip"):
        await message.answer("❗️ Пожалуйста, отправьте файл в формате ZIP.")
        return

    os.makedirs(OVIK_TEMP_PATH, exist_ok=True)
    filename = f"ovik_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{document.file_name}"
    save_path = os.path.join(OVIK_TEMP_PATH, filename)

    file = await bot.get_file(document.file_id)
    await bot.download_file(file.file_path, destination=save_path)

    relative_path = os.path.relpath(save_path, os.path.join(OVIK_TEMP_PATH, ".."))
    await save_ovik_file_path_to_tasks(order_id, relative_path)

    # Отправка ГИПу
    order = await get_order_by_id(order_id)
    gip_id = order["gip_id"]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_ovik:{order_id}"),
            InlineKeyboardButton(text="❌ Требует исправлений", callback_data=f"revise_ovik:{order_id}")
        ]
    ])

    await bot.send_document(
        chat_id=gip_id,
        document=FSInputFile(save_path),
        caption=f"📩 Получен ZIP файл от ОВиК-специалиста по заказу <b>{order['title']}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await message.answer("✅ Файл отправлен ГИПу.")
    await state.clear()

@router.callback_query(F.data.startswith("assign_ovik_execs:"))
async def assign_ovik_execs(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    available_execs = await get_available_ovik_executors(order_id)

    if not available_execs:
        await callback.message.answer("❗ Нет доступных исполнителей для ОВиК.")
        await callback.answer()
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ex["full_name"], callback_data=f"ovik_pick_exec:{order_id}:{ex['telegram_id']}")]
        for ex in available_execs
    ])
    await callback.message.answer("👥 Выберите исполнителя для раздела ОВиК/ТС:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("ovik_pick_exec:"))
async def confirm_ovik_exec(callback: CallbackQuery):
    _, order_id, exec_tg_id = callback.data.split(":")
    specialist_tg_id = callback.from_user.id

    # 🔒 Проверка: не более 3 исполнителей
    current_count = await count_executors_for_order(order_id=int(order_id), section="овик")
    if current_count >= 3:
        await callback.answer("❗ Уже назначено 3 исполнителя на ОВиК.", show_alert=True)
        return

    # Назначение исполнителя
    await assign_executor_to_ovik_order(
        order_id=int(order_id),
        executor_telegram_id=int(exec_tg_id),
        specialist_telegram_id=int(specialist_tg_id)
    )

    # Уведомление исполнителю
    executor_user = await get_user_by_telegram_id(int(exec_tg_id))
    if executor_user:
        await callback.bot.send_message(
            chat_id=executor_user["telegram_id"],
            text=f"📌 Вы были назначены на задачу ОВиК по заказу #{order_id}."
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


@router.message(F.text == "Нанять исполнителя по тс/ов")
async def handle_hire_executor_ovik(message: Message):
    executors = await get_unassigned_executors()

    if not executors:
        await message.answer("📭 Нет доступных исполнителей без отдела.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=executor["full_name"], callback_data=f"hire_ovik:{executor['id']}")]
            for executor in executors
        ]
    )

    await message.answer("👥 Выберите исполнителя для отдела ОВиК/ТС:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("hire_ovik:"))
async def process_executor_hire_ovik(callback: CallbackQuery):
    executor_id = int(callback.data.split(":")[1])

    # Назначаем исполнителя в раздел "овик"
    await assign_executor_to_section(executor_id, section="овик")

    # Получаем информацию об исполнителе
    executor = await get_user_by_id(executor_id)

    if executor and executor["telegram_id"]:
        try:
            await callback.bot.send_message(
                chat_id=executor["telegram_id"],
                text="👷 Вы были назначены исполнителем в отдел ОВиК/ТС. Ожидайте задачи от специалиста."
            )
        except Exception as e:
            print(f"Ошибка при отправке уведомления исполнителю: {e}")

    await callback.answer("✅ Исполнитель назначен в отдел ОВиК/ТС", show_alert=True)
    await callback.message.edit_text("✅ Исполнитель успешно назначен в отдел ОВиК/ТС.")
