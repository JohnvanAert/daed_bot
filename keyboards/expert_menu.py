from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

async def send_expert_main_menu(message: Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📂 Мои заказы")],
            [KeyboardButton(text="🆘 Поддержка")]
        ],
        resize_keyboard=True
    )
    await message.answer("📋 Главное меню эксперта:", reply_markup=keyboard)
