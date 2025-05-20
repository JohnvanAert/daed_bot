from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from states.assign_states import AssignSpecialist
from database import (
    get_user_by_telegram_id,
    get_orders_for_gip,
    assign_specialist_to_order_section,
    search_specialists_by_name
)
from keyboards.main_menu import send_main_menu

router = Router()

SECTIONS = ["Архитектура", "Конструктив", "ВК", "ОВиК", "ЭОМ", "ГП", "Сметы"]

@router.message(F.text == "📋 Управление пользователями")
async def gip_manage(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or user["role"] != "гип":
        await message.answer("❌ Команда доступна только для ГИПов.")
        return

    orders = await get_orders_for_gip(user["telegram_id"])
    if not orders:
        await message.answer("❓ У вас нет активных заказов.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=o["title"], callback_data=f"assign_order:{o['id']}")]
            for o in orders
        ]
    )
    await message.answer("✏️ Выберите заказ:", reply_markup=keyboard)
    await state.set_state(AssignSpecialist.choosing_order)

@router.callback_query(F.data.startswith("assign_order:"))
async def choose_section(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.update_data(order_id=order_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=section, callback_data=f"assign_section:{section}")]
            for section in SECTIONS
        ]
    )
    await callback.message.edit_text("✏️ Выберите раздел:", reply_markup=keyboard)
    await state.set_state(AssignSpecialist.choosing_section)

@router.callback_query(F.data.startswith("assign_section:"))
async def enter_specialist_name(callback: CallbackQuery, state: FSMContext):
    section = callback.data.split(":")[1]
    await state.update_data(section=section)
    await callback.message.edit_text(f"✏️ Раздел: <b>{section}</b>\n\nВведите имя или фамилию специалиста:")
    await state.set_state(AssignSpecialist.entering_specialist_name)

@router.message(AssignSpecialist.entering_specialist_name)
async def search_specialist(message: Message, state: FSMContext):
    query = message.text.strip()
    matches = await search_specialists_by_name(query)

    if not matches:
        await message.answer("❌ Специалисты не найдены. Попробуйте снова:")
        return

    await state.update_data(found_specialists=matches)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=s["full_name"], callback_data=f"confirm_spec:{s['telegram_id']}")]
            for s in matches
        ]
    )
    await message.answer("🔍 Найдено. Выберите специалиста:", reply_markup=keyboard)
    await state.set_state(AssignSpecialist.confirming_specialist)

@router.callback_query(F.data.startswith("confirm_spec:"))
async def confirm_specialist(callback: CallbackQuery, state: FSMContext):
    specialist_id = int(callback.data.split(":")[1])
    data = await state.get_data()

    section = data["section"]
    order_id = data["order_id"]
    matches = data.get("found_specialists", [])

    chosen = next((s for s in matches if s["telegram_id"] == specialist_id), None)
    if not chosen:
        await callback.message.answer("❌ Специалист не найден в списке. Попробуйте снова.")
        return

    await assign_specialist_to_order_section(order_id, section, specialist_id)
    await callback.message.edit_text(
        f"✅ Специалист <b>{chosen['full_name']}</b> назначен на раздел <b>{section}</b> заказа №{order_id}.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()
    await send_main_menu(callback.message, role="гип")