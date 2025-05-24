from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def send_main_menu(message, role: str):
    if role == "гип":
        kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="📋 Управление пользователями")],
            [KeyboardButton(text="📦 Заказы")],
            [KeyboardButton(text="📊 Аналитика")]
        ])
    elif role == "специалист":
        kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="Создать задачу")],
            [KeyboardButton(text="📁 Мои задачи")],
            [KeyboardButton(text="👥 Назначить исполнителя")]
        ])
    elif role == "исполнитель":
        kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="📌 Мои задачи")],
            [KeyboardButton(text="✅ Отметить как сделано")]
        ])
    else:
        return message.answer("Ваша роль не распознана. Обратитесь к администратору.")
    return message.answer(f"Добро пожаловать в панель {role.capitalize()}!", reply_markup=kb)
