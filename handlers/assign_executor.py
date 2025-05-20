from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from states.states import AssignExecutor
from database import get_all_executors, assign_executor_to_section, get_specialist_sections
from keyboards.main_menu import send_main_menu

router = Router()
SECTIONS = ["Архитектура", "Конструктив", "ВК", "ОВиК", "ЭОМ", "ГП", "Сметы"]
@router.message(F.text == "👥 Назначить исполнителя")
async def choose_section_for_executor(message: Message, state: FSMContext):
    sections = await get_specialist_sections(message.from_user.id)

    if not sections:
        await message.answer("❗ У вас нет закреплённых разделов.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=section, callback_data=f"assign_section:{section}")]
                         for section in SECTIONS]
    )
    await message.answer("Выберите раздел:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("assign_section:"))
async def process_section_callback(callback: CallbackQuery, state: FSMContext):
    section = callback.data.split(":")[1]
    await state.update_data(section=section)
    await callback.message.edit_text(f"Раздел: <b>{section}</b>\n\nВведите имя или фамилию исполнителя для поиска:")
    await state.set_state(AssignExecutor.entering_executor_name)

@router.message(AssignExecutor.entering_executor_name)
async def search_executor(message: Message, state: FSMContext):
    query = message.text.strip()
    matches = await get_all_executors(query)

    if not matches:
        await message.answer("❌ Исполнители не найдены. Попробуйте снова:")
        return

    await state.update_data(found_executors=matches)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=ex["full_name"], callback_data=f"assign_exec:{ex['telegram_id']}")]
                         for ex in matches]
    )
    await message.answer("🔍 Найдено. Выберите исполнителя из списка:", reply_markup=kb)
    await state.set_state(AssignExecutor.confirming_executor)

@router.callback_query(F.data.startswith("assign_exec:"))
async def confirm_executor(callback: CallbackQuery, state: FSMContext):
    executor_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    section = data.get("section")
    specialist_id = callback.from_user.id
    matches = data.get("found_executors", [])

    chosen = next((e for e in matches if e["telegram_id"] == executor_id), None)
    if not chosen:
        await callback.message.answer("❗ Исполнитель не найден в списке. Попробуйте снова.")
        return

    await assign_executor_to_section(section, specialist_id, executor_id)
    await callback.message.edit_text(
        f"✅ Исполнитель <b>{chosen['full_name']}</b> назначен на раздел <b>{section}</b>."
    )
    await state.clear()
    await send_main_menu(callback.message, role="специалист")