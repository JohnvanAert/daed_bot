from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def send_main_menu(message, role: str, section: str = None, archived=False):
    if archived:
        return message.answer(
            "⚠️ Ваша учетная запись в архиве. Обратитесь к администратору для восстановления.",
            reply_markup=ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text="👤 Мой профиль")]])
        )
    profile_button = [KeyboardButton(text="👤 Мой профиль")]
    

    section_menus = {
        "эп": [
            [KeyboardButton(text="📄 Мои заказы")],
            profile_button
        ],
        "ар": [
            [KeyboardButton(text="📄 Мои задачи")],
            [KeyboardButton(text=" Нанять исполнителя")],
            profile_button
        ],
        "рс": [
            [KeyboardButton(text="📄 Мои расч.задачи")],
            profile_button
        ],
        "гп": [
            [KeyboardButton(text="📄 Мои задачи по гп")],
            profile_button
        ],
        "кж": [
            [KeyboardButton(text="📄 Мои задачи по кж")],
            [KeyboardButton(text=" Нанять исполнителя по кж")],
            profile_button
        ],
        "овик": [
            [KeyboardButton(text="📄 Мои задачи по тс/ов")],
            [KeyboardButton(text=" Нанять исполнителя по тс/ов")],
            profile_button
        ],
        "вк": [
            [KeyboardButton(text="📄 Мои задачи по вк")],
            [KeyboardButton(text=" Нанять исполнителя по вк")],
            profile_button
        ],
        "гс": [
            [KeyboardButton(text="📄 Мои задачи по гс")],
            [KeyboardButton(text=" Нанять исполнителя по гс")],
            profile_button
        ],
        "эом": [
            [KeyboardButton(text="📄 Мои задачи по эом")],
            [KeyboardButton(text=" Нанять исполнителя по эом")],
            profile_button
        ],
        "сс": [
            [KeyboardButton(text="📄 Мои задачи по сс")],
            [KeyboardButton(text=" Нанять исполнителя по сс")],
            profile_button
        ],
        "сметчик": [
            [KeyboardButton(text="📄 Мои задачи по смете")],
            profile_button
        ]
    }

    # 🧠 Сначала проверяем конкретные роли
    if role == "гип":
        kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="📋 Управление пользователями")],
            [KeyboardButton(text="📦 Заказы")],
            [KeyboardButton(text="⚙️ Редактировать пользователей")],
            profile_button
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
                [KeyboardButton(text="👥 Назначить исполнителя")],
                profile_button
            ])
    elif role == "исполнитель":
        # 👷 Меню исполнителя не зависит от секции
        kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="📌 Мои задачи")],
            profile_button
        ])
    else:
        return message.answer("⚠️ Ваша роль не распознана. Обратитесь к администратору.")

    return message.answer(f"Добро пожаловать в панель {role.capitalize()}!", reply_markup=kb)
