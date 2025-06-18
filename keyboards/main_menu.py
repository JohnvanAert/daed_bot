from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def send_main_menu(message, role: str, section: str = None):
    section_menus = {
        "эп": [
            [KeyboardButton(text="📄 Мои заказы")]
        ],
        "ар": [
            [KeyboardButton(text="📄 Мои задачи")],
            [KeyboardButton(text=" Нанять исполнителя")]
        ],
        "рс": [
            [KeyboardButton(text="📄 Мои расч.задачи")]
        ],
        "гп": [
            [KeyboardButton(text="📄 Мои задачи по гп")]
        ],
        "кж": [
            [KeyboardButton(text="📄 Мои задачи по кж")],
            [KeyboardButton(text=" Нанять исполнителя по кж")]
        ],
        "овик": [
            [KeyboardButton(text="📄 Мои задачи по тс/ов")],
            [KeyboardButton(text=" Нанять исполнителя по тс/ов")]
        ],
        "вк": [
            [KeyboardButton(text="📄 Мои задачи по вк")],
            [KeyboardButton(text=" Нанять исполнителя по вк")]
        ],
        "гс": [
            [KeyboardButton(text="📄 Мои задачи по гс")],
            [KeyboardButton(text=" Нанять исполнителя по гс")]
        ],
        "эом": [
            [KeyboardButton(text="📄 Мои задачи по эом")],
            [KeyboardButton(text=" Нанять исполнителя по эом")]
        ],
        "сс": [
            [KeyboardButton(text="📄 Мои задачи по сс")],
            [KeyboardButton(text=" Нанять исполнителя по сс")]
        ]
    }

    # 🧠 Сначала проверяем конкретные роли
    if role == "гип":
        kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="📋 Управление пользователями")],
            [KeyboardButton(text="📦 Заказы")],
            [KeyboardButton(text="📊 Аналитика")]
        ])
    elif role == "специалист":
        # 🔍 Если у специалиста есть секция — показываем конкретное меню
        if section and section.lower() in section_menus:
            kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=section_menus[section.lower()])
        else:
            # 🔄 Общее меню специалиста
            kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
                [KeyboardButton(text="Создать задачу")],
                [KeyboardButton(text="📁 Мои задачи")],
                [KeyboardButton(text="👥 Назначить исполнителя")]
            ])
    elif role == "исполнитель":
        # 👷 Меню исполнителя не зависит от секции
        kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="📌 Мои задачи")],
            [KeyboardButton(text="✅ Отметить как сделано")]
        ])
    else:
        return message.answer("⚠️ Ваша роль не распознана. Обратитесь к администратору.")

    return message.answer(f"Добро пожаловать в панель {role.capitalize()}!", reply_markup=kb)
