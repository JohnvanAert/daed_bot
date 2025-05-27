from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def send_main_menu(message, role: str, section: str = None):
    section_menus = {
        "эп": [
            [KeyboardButton(text="📄 Мои заказы")],
            [KeyboardButton(text="📤 Передать ГИПу на проверку")]
        ],
        "ар": [
            [KeyboardButton(text="📄 Мои АР-задачи")],
            [KeyboardButton(text="📤 Передать Рассчёт")]
        ],
        "рс": [
            [KeyboardButton(text="📄 Мои РС-задачи")],
            [KeyboardButton(text="📤 Передать КЖ")]
        ],
        "кж": [
            [KeyboardButton(text="📄 Мои КЖ-задачи")],
            [KeyboardButton(text="📤 Передать ОВиК")]
        ],
        "овик": [
            [KeyboardButton(text="📄 Мои ОВиК-задачи")],
            [KeyboardButton(text="📤 Передать ВК")]
        ],
        "вк": [
            [KeyboardButton(text="📄 Мои ВК-задачи")],
            [KeyboardButton(text="📤 Передать ЭОМ")]
        ],
        "эом": [
            [KeyboardButton(text="📄 Мои ЭОМ-задачи")],
            [KeyboardButton(text="📤 Передать СС")]
        ],
        "сс": [
            [KeyboardButton(text="📄 Мои СС-задачи")],
            [KeyboardButton(text="📤 Передать сметчику")]
        ]
    }

    if role == "гип":
        kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="📋 Управление пользователями")],
            [KeyboardButton(text="📦 Заказы")],
            [KeyboardButton(text="📊 Аналитика")]
        ])
    elif section in section_menus:
        # ✅ Если есть секция — показываем только её меню
        kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=section_menus[section])
    elif role == "специалист":
        # 🔄 Фоллбэк на общее меню специалиста, если секция не указана
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
