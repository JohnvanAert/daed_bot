from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def customer_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Создать заказ")],
            [KeyboardButton(text="📦 Мои заказы")]
            # Можно позже добавить просмотр заказов
        ],
        resize_keyboard=True
    )
