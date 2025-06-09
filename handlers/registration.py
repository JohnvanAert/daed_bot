from aiogram import Router
from aiogram.types import Message, ReplyKeyboardRemove
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

    data = await state.get_data()
    full_name = data.get("full_name")

    # ✅ Устанавливаем роль по умолчанию
    role = "исполнитель"

    await add_user(
        telegram_id=message.from_user.id,
        full_name=full_name,
        iin=iin,
        role=role
    )

    await message.answer(
        f"✅ Регистрация завершена!\n"
        f"<b>Имя:</b> {full_name}\n"
        f"<b>ИИН:</b> {iin}\n"
        f"<b>Роль:</b> {role.capitalize()}",
        reply_markup=ReplyKeyboardRemove()
    )

    await state.clear()
    await send_main_menu(message, role)
