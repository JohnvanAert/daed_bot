from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from keyboards.main_menu import send_main_menu
from states.registration_states import RegisterState
from database import get_user_by_telegram_id

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = await get_user_by_telegram_id(message.from_user.id)
    if user:
        await message.answer(f"👋 Вы уже зарегистрированы как <b>{user['role'].capitalize()}</b>.", reply_markup=ReplyKeyboardRemove())
        await send_main_menu(message, role=user["role"], section=user["section"])
    else:
        await message.answer("Добро пожаловать! Введите ваше имя и фамилию:")
        await state.set_state(RegisterState.waiting_for_name)
