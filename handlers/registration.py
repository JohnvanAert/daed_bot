from aiogram import Router
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from database import add_user
from states.registration_states import RegisterState
from keyboards.main_menu import send_main_menu

router = Router()

@router.message(RegisterState.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await message.answer("Введите ваш ИИН (12 цифр):")
    await state.set_state(RegisterState.waiting_for_iin)

@router.message(RegisterState.waiting_for_iin)
async def process_iin(message: Message, state: FSMContext):
    iin = message.text.strip()
    if not iin.isdigit() or len(iin) != 12:
        await message.answer("❗️ ИИН должен содержать ровно 12 цифр. Попробуйте снова:")
        return
    await state.update_data(iin=iin)
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="ГИП"), KeyboardButton(text="специалист"), KeyboardButton(text="исполнитель")]
    ])
    await message.answer("Выберите вашу роль:", reply_markup=kb)
    await state.set_state(RegisterState.waiting_for_role)

@router.message(RegisterState.waiting_for_role)
async def process_role(message: Message, state: FSMContext):
    role = message.text.lower()
    if role not in ["гип", "специалист", "исполнитель"]:
        await message.answer("Пожалуйста, выберите роль с клавиатуры.")
        return

    data = await state.get_data()
    await add_user(
        telegram_id=message.from_user.id,
        full_name=data.get("full_name"),
        iin=data.get("iin"),
        role=role
    )

    await message.answer(
        f"✅ Регистрация завершена!\n"
        f"<b>Имя:</b> {data.get('full_name')}\n"
        f"<b>ИИН:</b> {data.get('iin')}\n"
        f"<b>Роль:</b> {role.capitalize()}",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()
    await send_main_menu(message, role)
