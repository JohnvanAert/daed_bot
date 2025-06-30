from aiogram import Router
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from database import add_customer, get_customer_by_telegram_id
from states.states import RegisterCustomer
from keyboards.customer_menu import customer_menu

router = Router()

@router.message(RegisterCustomer.waiting_for_full_name)
async def process_full_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    await state.update_data(full_name=full_name)
    await message.answer("Введите ваш ИИН или БИН (12 цифр):")
    await state.set_state(RegisterCustomer.waiting_for_iin_or_bin)

@router.message(RegisterCustomer.waiting_for_iin_or_bin)
async def process_iin_or_bin(message: Message, state: FSMContext):
    iin_or_bin = message.text.strip()
    if not iin_or_bin.isdigit() or len(iin_or_bin) != 12:
        await message.answer("❗️ ИИН или БИН должен содержать ровно 12 цифр. Попробуйте снова:")
        return

    await state.update_data(iin_or_bin=iin_or_bin)
    await message.answer("📞 Введите ваш номер телефона:")
    await state.set_state(RegisterCustomer.waiting_for_phone)

@router.message(RegisterCustomer.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+") or not phone[1:].isdigit():
        await message.answer("❗️ Введите номер в формате +7XXXXXXXXXX:")
        return

    await state.update_data(phone=phone)
    await message.answer("📧 Введите ваш адрес электронной почты:")
    await state.set_state(RegisterCustomer.waiting_for_email)

@router.message(RegisterCustomer.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    email = message.text.strip()
    if "@" not in email or "." not in email:
        await message.answer("❗️ Введите корректный адрес электронной почты:")
        return

    data = await state.get_data()

    await add_customer(
        telegram_id=message.from_user.id,
        full_name=data.get("full_name"),
        iin_or_bin=data.get("iin_or_bin"),
        phone=data.get("phone"),
        email=email
    )

    await message.answer(
        f"✅ Регистрация завершена!\n"
        f"<b>ФИО:</b> {data.get('full_name')}\n"
        f"<b>ИИН/БИН:</b> {data.get('iin_or_bin')}\n"
        f"<b>Телефон:</b> {data.get('phone')}\n"
        f"<b>Email:</b> {email}",
        reply_markup=customer_menu()
    )

    await state.clear()
