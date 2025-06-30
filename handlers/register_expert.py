from aiogram import Router
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from states.registration_states import ExpertRegistrationFSM
from database import add_expert
from keyboards.expert_menu import send_expert_main_menu

router = Router()

@router.message(ExpertRegistrationFSM.waiting_for_name)
async def process_expert_name(message: Message, state: FSMContext):
    full_name = message.text.strip()

    # Сохраняем в базу
    await add_expert(
        telegram_id=message.from_user.id,
        full_name=full_name
    )

    await message.answer(
        f"✅ Регистрация завершена!\n"
        f"<b>Имя:</b> {full_name}\n"
        f"<b>Роль:</b> Эксперт",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )

    await state.clear()
    await send_expert_main_menu(message)
