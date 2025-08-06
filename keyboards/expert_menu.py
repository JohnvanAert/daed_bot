from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

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
