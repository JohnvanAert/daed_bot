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

    await state.update_data(iin=iin)
    await message.answer("Введите ваш адрес:")
    await state.set_state(RegisterState.waiting_for_address)


@router.message(RegisterState.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    await message.answer("Введите название вашего банка:")
    await state.set_state(RegisterState.waiting_for_bank)


@router.message(RegisterState.waiting_for_bank)
async def process_bank(message: Message, state: FSMContext):
    await state.update_data(bank=message.text.strip())
    await message.answer("Введите ваш ИИК/IBAN:")
    await state.set_state(RegisterState.waiting_for_iban)


@router.message(RegisterState.waiting_for_iban)
async def process_iban(message: Message, state: FSMContext):
    await state.update_data(iban=message.text.strip())
    await message.answer("Введите БИК:")
    await state.set_state(RegisterState.waiting_for_bik)


@router.message(RegisterState.waiting_for_bik)
async def process_bik(message: Message, state: FSMContext):
    await state.update_data(bik=message.text.strip())
    await message.answer("Введите вашу эл. почту:")
    await state.set_state(RegisterState.waiting_for_email)


@router.message(RegisterState.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    await state.update_data(email=message.text.strip())
    await message.answer("Введите ваш телефон:")
    await state.set_state(RegisterState.waiting_for_phone)


@router.message(RegisterState.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(phone=phone)

    data = await state.get_data()
    full_name = data["full_name"]
    iin = data["iin"]
    role = "исполнитель"

    await add_user(
        telegram_id=message.from_user.id,
        full_name=full_name,
        iin=iin,
        role=role,
        address=data["address"],
        bank=data["bank"],
        iban=data["iban"],
        bik=data["bik"],
        kbe="19",   # 👈 КБЕ по умолчанию
        email=data["email"],
        phone=phone
    )

    await message.answer(
        f"✅ Регистрация завершена!\n"
        f"<b>Имя:</b> {full_name}\n"
        f"<b>ИИН:</b> {iin}\n"
        f"<b>Роль:</b> {role.capitalize()}\n\n"
        f"<b>Адрес:</b> {data['address']}\n"
        f"<b>Банк:</b> {data['bank']}\n"
        f"<b>ИИК:</b> {data['iban']}\n"
        f"<b>БИК:</b> {data['bik']}\n"
        f"<b>Email:</b> {data['email']}\n"
        f"<b>Телефон:</b> {phone}",
        reply_markup=ReplyKeyboardRemove()
    )

    await state.clear()
    await send_main_menu(message, role)
