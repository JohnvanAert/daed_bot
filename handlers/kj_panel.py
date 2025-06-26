from aiogram import Router, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, FSInputFile, Document
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import get_orders_by_specialist_id, save_kj_file_path_to_tasks, get_order_by_id, assign_executor_to_section, get_user_by_id, get_unassigned_executors, get_available_kj_executors, count_executors_for_order, assign_executor_to_kj_order, get_user_by_telegram_id
from datetime import datetime
import os

router = Router()

KJ_TEMP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "psdbot", "documents", "temporary"))

class SubmitKjFSM(StatesGroup):
    waiting_for_file = State()

# 📄 Панель КЖ
@router.message(F.text == "📄 Мои задачи по кж")
async def show_kj_tasks(message: Message):
    orders = await get_orders_by_specialist_id(message.from_user.id, section="кж")
    if not orders:
        await message.answer("📭 У вас пока нет задач.")
        return

    for order in orders:
        order_id = order["id"]
        status = order["status"]
        caption = (
            f"📌 <b>{order['title']}</b>\n"
            f"📝 {order['description']}\n"
            f"📅 Дата: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )  

        buttons = []
        
        if status == "assigned_kj":
            buttons.append(InlineKeyboardButton(text="👥 Назначить исполнителей по КЖ", callback_data=f"assign_kj_execs:{order_id}"))
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Отправить на проверку КЖ", callback_data=f"submit_kj:{order['id']}")]
        ])

        await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)

# 📨 Ожидание ZIP от КЖ-специалиста
@router.callback_query(F.data.startswith("submit_kj:"))
async def handle_kj_submit(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(SubmitKjFSM.waiting_for_file)
    await state.update_data(order_id=order_id)

    await callback.message.answer("📎 Прикрепите ZIP файл по разделу КЖ.")
    await callback.answer()

# 💾 Обработка файла
@router.message(SubmitKjFSM.waiting_for_file, F.document)
async def receive_kj_file(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    order_id = data["order_id"]
    document: Document = message.document

    if not document.file_name.lower().endswith(".zip"):
        await message.answer("❗️ Отправьте файл в формате ZIP.")
        return

    os.makedirs(KJ_TEMP_PATH, exist_ok=True)

    filename = f"kj_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{document.file_name}"
    save_path = os.path.join(KJ_TEMP_PATH, filename)

    file = await bot.get_file(document.file_id)
    await bot.download_file(file.file_path, destination=save_path)

    relative_path = os.path.relpath(save_path, os.path.join(KJ_TEMP_PATH, ".."))
    await save_kj_file_path_to_tasks(order_id, relative_path)

    order = await get_order_by_id(order_id)
    gip_id = order["gip_id"]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_kj:{order_id}"),
            InlineKeyboardButton(text="❌ Исправить", callback_data=f"revise_kj:{order_id}")
        ]
    ])

    await bot.send_document(
        chat_id=gip_id,
        document=FSInputFile(save_path),
        caption=f"📩 Получен ZIP файл от специалиста по КЖ по заказу <b>{order['title']}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await message.answer("✅ Файл КЖ отправлен ГИПу.")
    await state.clear()

@router.callback_query(F.data.startswith("assign_kj_execs:"))
async def assign_kj_execs(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    available_execs = await get_available_kj_executors(order_id)

    if not available_execs:
        await callback.message.answer("❗ Нет доступных исполнителей для назначения.")
        await callback.answer()
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ex["full_name"], callback_data=f"kj_pick_exec:{order_id}:{ex['telegram_id']}")]
        for ex in available_execs
    ])
    await callback.message.answer("Выберите исполнителя для КЖ:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("kj_pick_exec:"))
async def confirm_kj_exec(callback: CallbackQuery):
    _, order_id, exec_tg_id = callback.data.split(":")
    specialist_tg_id = callback.from_user.id

    # Проверка: не более 3 исполнителей
    current_count = await count_executors_for_order(order_id=int(order_id), section="кж")
    if current_count >= 3:
        await callback.answer("❗ Уже назначено 3 исполнителя на КЖ.", show_alert=True)
        return

    # Назначение исполнителя
    await assign_executor_to_kj_order(
        order_id=int(order_id),
        executor_telegram_id=int(exec_tg_id),
        specialist_telegram_id=int(specialist_tg_id)
    )

    # Уведомление исполнителю
    executor_user = await get_user_by_telegram_id(int(exec_tg_id))
    if executor_user:
        await callback.bot.send_message(
            chat_id=executor_user["telegram_id"],
            text=f"📌 Вы были назначены на задачу КЖ по заказу #{order_id}."
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


@router.message(F.text == "Нанять исполнителя по кж")
async def handle_hire_executor_kj(message: Message):
    executors = await get_unassigned_executors()

    if not executors:
        await message.answer("📭 Нет доступных исполнителей без отдела.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=executor["full_name"], callback_data=f"hire_kj:{executor['id']}")]
            for executor in executors
        ]
    )

    await message.answer("👥 Выберите исполнителя для отдела КЖ:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("hire_kj:"))
async def process_executor_hire_kj(callback: CallbackQuery):
    executor_id = int(callback.data.split(":")[1])

    # Привязываем исполнителя к разделу "кж"
    await assign_executor_to_section(executor_id, section="кж")

    # Получаем информацию об исполнителе
    executor = await get_user_by_id(executor_id)

    if executor and executor["telegram_id"]:
        try:
            await callback.bot.send_message(
                chat_id=executor["telegram_id"],
                text="👷 Вы были назначены исполнителем в отдел КЖ. Ожидайте задачи от специалиста."
            )
        except Exception as e:
            print(f"Ошибка при отправке уведомления исполнителю: {e}")

    await callback.answer("✅ Исполнитель назначен в отдел КЖ", show_alert=True)
    await callback.message.edit_text("✅ Исполнитель успешно добавлен в отдел КЖ.")
