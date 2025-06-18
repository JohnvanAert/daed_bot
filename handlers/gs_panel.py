from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile, Document
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import get_orders_by_specialist_id, save_gs_file_path_to_tasks, get_order_by_id, assign_executor_to_section, get_user_by_id, get_unassigned_executors, get_available_gs_executors, count_executors_for_order, assign_executor_to_gs_order, get_user_by_telegram_id
import os
from datetime import datetime

router = Router()
VGS_TEMP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "clientbot", "documents", "temporary"))

class SubmitVgsFSM(StatesGroup):
    waiting_for_file = State()

@router.message(F.text == "📄 Мои задачи по гс")
async def show_gs_tasks(message: Message):
    orders = await get_orders_by_specialist_id(message.from_user.id, section="гс")
    if not orders:
        await message.answer("📭 У вас пока нет задач.")
        return

    for order in orders: 
        order_id = order["id"]
        status = order["status"]
        caption = f"📌 <b>{order['title']}</b>\n📝 {order['description']}\n📅 {order['created_at'].strftime('%Y-%m-%d %H:%M')}"

        buttons = []
        if status == "assigned_gs":
            buttons.append(InlineKeyboardButton(text="👥 Назначить исполнителей", callback_data=f"assign_gs_execs:{order_id}"))
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Отправить результат", callback_data=f"submit_gs:{order['id']}")]
        ])
        await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)

@router.callback_query(F.data.startswith("submit_gs:"))
async def handle_gs_submit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubmitVgsFSM.waiting_for_file)
    await state.update_data(order_id=int(callback.data.split(":")[1]))
    await callback.message.answer("📎 Прикрепите ZIP файл по ВГС/НГС.")
    await callback.answer()

@router.message(SubmitVgsFSM.waiting_for_file, F.document)
async def receive_gs_file(message: Message, state: FSMContext, bot):
    data = await state.get_data()
    order_id = data["order_id"]
    document = message.document

    if not document.file_name.lower().endswith(".zip"):
        await message.answer("❗️ Отправьте файл в формате ZIP.")
        return

    os.makedirs(VGS_TEMP_PATH, exist_ok=True)
    filename = f"gs_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{document.file_name}"
    save_path = os.path.join(VGS_TEMP_PATH, filename)

    file = await bot.get_file(document.file_id)
    await bot.download_file(file.file_path, destination=save_path)
    relative_path = os.path.relpath(save_path, os.path.join(VGS_TEMP_PATH, ".."))
    await save_gs_file_path_to_tasks(order_id, relative_path)

    order = await get_order_by_id(order_id)
    gip_id = order["gip_id"]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_gs:{order_id}"),
         InlineKeyboardButton(text="❌ Исправить", callback_data=f"revise_gs:{order_id}")]
    ])

    await bot.send_document(
        chat_id=gip_id,
        document=FSInputFile(save_path),
        caption=f"📩 ZIP от ВГС-специалиста по заказу <b>{order['title']}</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await message.answer("✅ Файл отправлен ГИПу.")
    await state.clear()

@router.callback_query(F.data.startswith("assign_gs_execs:"))
async def assign_gs_execs(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    available_execs = await get_available_gs_executors(order_id)

    if not available_execs:
        await callback.message.answer("❗ Нет доступных исполнителей для назначения.")
        await callback.answer()
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ex["full_name"], callback_data=f"gs_pick_exec:{order_id}:{ex['telegram_id']}")]
        for ex in available_execs
    ])
    await callback.message.answer("👷 Выберите исполнителя для раздела ГС:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("gs_pick_exec:"))
async def confirm_gs_exec(callback: CallbackQuery):
    _, order_id, exec_tg_id = callback.data.split(":")
    specialist_tg_id = callback.from_user.id

    current_count = await count_executors_for_order(order_id=int(order_id), section="гс")
    if current_count >= 3:
        await callback.answer("❗ Уже назначено 3 исполнителя для этого заказа.", show_alert=True)
        return

    await assign_executor_to_gs_order(
        order_id=int(order_id),
        executor_telegram_id=int(exec_tg_id),
        specialist_telegram_id=specialist_tg_id
    )

    # Уведомление исполнителю
    executor_user = await get_user_by_telegram_id(int(exec_tg_id))
    if executor_user:
        await callback.bot.send_message(
            chat_id=executor_user["telegram_id"],
            text=f"📌 Вам назначена новая задача по разделу ГС (заказ #{order_id})."
        )

    # Удаление назначенной кнопки
    original_markup = callback.message.reply_markup
    if original_markup:
        new_buttons = []
        for row in original_markup.inline_keyboard:
            new_row = [btn for btn in row if callback.data not in btn.callback_data]
            if new_row:
                new_buttons.append(new_row)

        await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=new_buttons))

    await callback.answer("Назначено ✅", show_alert=True)


@router.message(F.text == "Нанять исполнителя по гс")
async def handle_hire_executor_gs(message: Message):
    executors = await get_unassigned_executors()

    if not executors:
        await message.answer("📭 Нет доступных исполнителей без отдела.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=executor["full_name"], callback_data=f"hire_gs:{executor['id']}")]
            for executor in executors
        ]
    )

    await message.answer("👥 Выберите исполнителя для отдела ГС:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("hire_gs:"))
async def process_executor_hire_gs(callback: CallbackQuery):
    executor_id = int(callback.data.split(":")[1])

    # Назначаем исполнителя в раздел "гс"
    await assign_executor_to_section(executor_id, section="гс")

    # Получаем исполнителя
    executor = await get_user_by_id(executor_id)

    if executor and executor["telegram_id"]:
        try:
            await callback.bot.send_message(
                chat_id=executor["telegram_id"],
                text="👷 Вы были назначены исполнителем в отдел ГС. Ожидайте задачи от специалиста."
            )
        except Exception as e:
            print(f"Ошибка при отправке уведомления исполнителю: {e}")

    await callback.answer("✅ Исполнитель добавлен в отдел ГС", show_alert=True)
    await callback.message.edit_text("✅ Исполнитель успешно назначен в отдел ГС.")
