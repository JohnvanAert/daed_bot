from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import CommandStart

from keyboards.main_menu import send_main_menu
from keyboards.customer_menu import customer_menu
from keyboards.expert_menu import send_expert_main_menu

from states.registration_states import RegisterState, ExpertRegistrationFSM, RoleSelectionFSM
from states.states import RegisterCustomer  # Для заказчика

from database import (
    get_user_by_telegram_id,
    get_customer_by_telegram_id,
    get_expert_by_telegram_id,
)

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # 1. Заказчик
    customer = await get_customer_by_telegram_id(user_id)
    if customer:
        if customer.get("archived"):  # предполагается что в таблице customers есть поле archived BOOLEAN
            await message.answer(
                "⚠️ Ваша учетная запись в архиве. Обратитесь к администратору для восстановления."
            )
            return

        await message.answer("👋 Добро пожаловать, уважаемый заказчик!", reply_markup=customer_menu())
        return

    # 2. Эксперт
    expert = await get_expert_by_telegram_id(user_id)
    if expert:
        if expert.get("archived"):  # предполагается что и для экспертов есть поле archived
            await message.answer(
                "⚠️ Ваша учетная запись в архиве. Обратитесь к администратору для восстановления."
            )
            return

        await message.answer(
            f"👋 Добро пожаловать, <b>{expert['full_name']}</b>! Вы уже зарегистрированы как эксперт.",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML"
        )
        await send_expert_main_menu(message)
        return

    # 3. Исполнитель / специалист
    user = await get_user_by_telegram_id(user_id)
    if user:
        if user.get("is_archived"):
            await send_main_menu(message, role=user["role"], section=user["section"], archived=True)
            return


        await message.answer(
            f"👋 Вы уже зарегистрированы как <b>{user['role'].capitalize()}</b>.",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML"
        )
        await send_main_menu(message, role=user["role"], section=user["section"])
        return

    # 4. Новый пользователь — выбрать роль
    keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [KeyboardButton(text="👷 Я проектировщик")],
            [KeyboardButton(text="📦 Я заказчик")],
            [KeyboardButton(text="🧠 Я эксперт")]
        ]
    )
    await message.answer("🚀 Привет! Выберите, кто вы:", reply_markup=keyboard)
    await state.set_state(RoleSelectionFSM.choosing_role)


@router.message(RoleSelectionFSM.choosing_role)
async def handle_role_selection(message: Message, state: FSMContext):
    text = message.text.strip().lower()

    if "заказчик" in text:
        await message.answer("📝 Введите ваше ФИО:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(RegisterCustomer.waiting_for_full_name)

    elif "эксперт" in text:
        await message.answer("📝 Введите ваше имя и фамилию:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(ExpertRegistrationFSM.waiting_for_name)

    elif "проектировщик" in text or "исполнитель" in text:
        await message.answer("📝 Введите ваше имя и фамилию:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(RegisterState.waiting_for_name)

    else:
        await message.answer("❗ Пожалуйста, выберите роль с помощью кнопок.")
