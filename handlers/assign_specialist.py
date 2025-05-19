from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from database import get_user_by_telegram_id, assign_specialist_to_section, search_specialists_by_name
from states.assign_states import AssignSpecialist
from keyboards.main_menu import send_main_menu

router = Router()

SECTIONS = ["Архитектура", "Конструктив", "ВК", "ОВиК", "ЭОМ", "ГП", "Сметы"]

@router.message(F.text == "📋 Управление пользователями")
async def gip_manage(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if user and user["role"] == "гип":
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=section)] for section in SECTIONS],
            resize_keyboard=True
        )
        await message.answer("Выберите раздел для назначения специалиста:", reply_markup=kb)
        await state.set_state(AssignSpecialist.choosing_section)

@router.message(AssignSpecialist.choosing_section)
async def enter_specialist_name(message: Message, state: FSMContext):
    section = message.text
    if section not in SECTIONS:
        await message.answer("Выберите раздел из клавиатуры.")
        return

    await state.update_data(section=section)
    await message.answer("Введите имя или фамилию специалиста для поиска:")
    await state.set_state(AssignSpecialist.entering_specialist_name)

@router.message(AssignSpecialist.entering_specialist_name)
async def search_specialist(message: Message, state: FSMContext):
    query = message.text.strip()
    matches = await search_specialists_by_name(query)

    if not matches:
        await message.answer("❌ Специалисты не найдены. Попробуйте снова:")
        return

    await state.update_data(found_specialists=matches)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=spec["full_name"])] for spec in matches],
        resize_keyboard=True
    )
    await message.answer("🔍 Найдено. Выберите специалиста из списка:", reply_markup=kb)
    await state.set_state(AssignSpecialist.confirming_specialist)

@router.message(AssignSpecialist.confirming_specialist)
async def confirm_specialist(message: Message, state: FSMContext):
    selected_name = message.text
    data = await state.get_data()
    matches = data.get("found_specialists", [])
    section = data.get("section")

    chosen = next((s for s in matches if s["full_name"] == selected_name), None)
    if not chosen:
        await message.answer("❗ Специалист не найден в списке. Попробуйте снова.")
        return

    await assign_specialist_to_section(section, chosen["telegram_id"])
    await message.answer(
        f"✅ Специалист <b>{selected_name}</b> назначен на раздел <b>{section}</b>.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()
    await send_main_menu(message, role="гип")
