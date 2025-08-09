from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram import Router

router = Router()

async def send_expert_main_menu(message: Message):
    profile_button = [KeyboardButton(text="👤 Мой профиль")]
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📄 Мои экспертизы")],
            [KeyboardButton(text="🆘 Поддержка")],
            profile_button
        ],
        resize_keyboard=True
    )
    await message.answer("📋 Главное меню эксперта:", reply_markup=keyboard)

@router.message(lambda message: message.text == "📄 Мои экспертизы")
async def send_expert_tasks_menu(message: Message):
    kb = ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [KeyboardButton(text="📄 Текущие экспертизы")],
            [KeyboardButton(text="📁 Завершённые экспертизы")],
            [KeyboardButton(text="🔙 Назад в меню экспертов")]
        ]
    )
    await message.answer("Выберите тип экспертиз:", reply_markup=kb)


@router.message(lambda message: message.text == "🔙 Назад в меню экспертов")
async def handle_back_to_expert_menu(message: Message):
    await send_expert_main_menu(message)
    await message.answer("Главное меню эксперта.")