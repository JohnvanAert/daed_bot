from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def customer_menu():
    profile_button = [KeyboardButton(text="👤 Мой профиль")]
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Создать заказ")],
            [KeyboardButton(text="📦 Мои заказы")],
            profile_button
            # Можно позже добавить просмотр заказов
        ],
        resize_keyboard=True
    )
