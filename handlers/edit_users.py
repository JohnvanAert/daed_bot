from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import get_all_users_sorted_by_id, update_user_field, move_user_to_experts, archive_user_by_id, get_active_users_sorted_by_id,get_archived_users_sorted_by_id, restore_user

router = Router()

USERS_PER_PAGE = 5

class EditUserFSM(StatesGroup):
    waiting_for_new_value = State()

# ====== Старт панели выбора кого редактировать ======
@router.message(F.text == "⚙️ Редактировать пользователей")
async def edit_users_main(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👷 Исполнители/Специалисты", callback_data="edit_type:users")],
        [InlineKeyboardButton(text="📦 Заказчики", callback_data="edit_type:customers")],
        [InlineKeyboardButton(text="🎓 Эксперты", callback_data="edit_type:experts")]
    ])
    await message.answer("Кого хотите редактировать?", reply_markup=kb)


@router.callback_query(F.data == "edit_type:users")
async def edit_users_list(callback: CallbackQuery):
    await show_users_page(callback.message, page=0, edit=True)
    await callback.answer()
    
# 🔄 Переключение страниц
@router.callback_query(F.data.startswith("users_page:"))
async def paginate_users(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await show_users_page(callback.message, page, edit=True)
    await callback.answer()

async def show_users_page(message: Message, page: int, edit=False):
    users = await get_active_users_sorted_by_id()
    await show_page_common(message, page, users, edit, is_archive=False)


@router.callback_query(F.data.startswith("archive_page:"))
async def paginate_archived_users(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await show_archived_users_page(callback.message, page, edit=True)
    await callback.answer()

# 📋 Страница архива
async def show_archived_users_page(message: Message, page: int, edit=False):
    users = await get_archived_users_sorted_by_id()
    await show_page_common(message, page, users, edit, is_archive=True)

# 📋 Отображаем страницу пользователей
async def show_page_common(message: Message, page: int, users, edit, is_archive=False):
    total_pages = (len(users) - 1) // USERS_PER_PAGE + 1

    start_idx = page * USERS_PER_PAGE
    end_idx = start_idx + USERS_PER_PAGE
    page_users = users[start_idx:end_idx]

    if not page_users:
        text = "❗ Пользователи не найдены."
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return

    kb_buttons = []
    for u in page_users:
        text_btn = f"🆔{u['id']} {u['full_name']}"
        cb_data = f"{'restore' if is_archive else 'edit_user'}:{u['id']}"
        kb_buttons.append([InlineKeyboardButton(text=text_btn, callback_data=cb_data)])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Предыдущая",
            callback_data=f"{'archive_page' if is_archive else 'users_page'}:{page - 1}"
        ))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(
            text="➡️ Следующая",
            callback_data=f"{'archive_page' if is_archive else 'users_page'}:{page + 1}"
        ))
    if nav_buttons:
        kb_buttons.append(nav_buttons)
    
    if not is_archive:
        kb_buttons.append([
            InlineKeyboardButton(text="📁 Архив пользователей", callback_data="archive_page:0")
        ])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    title = "📁 Архив пользователей" if is_archive else "📋 Пользователи"
    text = f"{title}\nСтраница <b>{page + 1}</b> из <b>{total_pages}</b>"

    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")

# 🛠 Выбор пользователя для редактирования
@router.callback_query(F.data.startswith("edit_user:"))
async def select_user_to_edit(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split(":")[1])
    await state.update_data(edit_user_id=user_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить ФИО", callback_data="edit_field:full_name")],
        [InlineKeyboardButton(text="🆔 Изменить ИИН", callback_data="edit_field:iin")],
        [InlineKeyboardButton(text="📱 Изменить телефон", callback_data="edit_field:phone")],
        [InlineKeyboardButton(text="📝 Изменить роль", callback_data="edit_role")],
        [InlineKeyboardButton(text="🛠 Изменить секцию", callback_data="edit_section")],
        [InlineKeyboardButton(text="🗑 Удалить пользователя", callback_data="delete_user")]
    ])
    await callback.message.edit_text(
        f"🔧 Что хотите изменить у пользователя ID <b>{user_id}</b>?",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

# 🔥 Изменяем роль через кнопки
@router.callback_query(F.data == "edit_role")
async def choose_role(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👷 Исполнитель", callback_data="set_role:исполнитель")],
        [InlineKeyboardButton(text="🛠 Специалист", callback_data="set_role:специалист")],
        [InlineKeyboardButton(text="🎓 Эксперт", callback_data="set_role:эксперт")]
    ])
    await callback.message.edit_text("Выберите новую роль для пользователя:", reply_markup=kb)
    await callback.answer()

# 🏗 Устанавливаем роль
@router.callback_query(F.data.startswith("set_role:"))
async def set_role(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = data["edit_user_id"]
    new_role = callback.data.split(":")[1]

    if new_role == "эксперт":
        await move_user_to_experts(user_id)
        await callback.message.edit_text(f"✅ Пользователь ID {user_id} перемещён в таблицу экспертов.")
    else:
        await update_user_field(user_id, "role", new_role)
        await callback.message.edit_text(f"✅ Роль пользователя ID {user_id} обновлена на <b>{new_role}</b>.", parse_mode="HTML")
    await state.clear()
    await callback.answer()

# 🔥 Изменяем секцию через кнопки
@router.callback_query(F.data == "edit_section")
async def choose_section(callback: CallbackQuery, state: FSMContext):
    sections = ["эп", "ар", "кж", "гп", "рс", "сс", "овик", "гс", "вк", "эом"]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=sec.upper(), callback_data=f"set_section:{sec}")] for sec in sections
    ])
    await callback.message.edit_text("Выберите новую секцию для пользователя:", reply_markup=kb)
    await callback.answer()

# 🏗 Устанавливаем секцию
@router.callback_query(F.data.startswith("set_section:"))
async def set_section(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = data["edit_user_id"]
    new_section = callback.data.split(":")[1]
    await update_user_field(user_id, "section", new_section)
    await callback.message.edit_text(f"✅ Секция пользователя ID {user_id} обновлена на <b>{new_section.upper()}</b>.", parse_mode="HTML")
    await state.clear()
    await callback.answer()

# ✏️ Запрашиваем новое значение
@router.callback_query(F.data.startswith("edit_field:"))
async def ask_new_value(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]
    await state.update_data(edit_field=field)
    await state.set_state(EditUserFSM.waiting_for_new_value)
    await callback.message.edit_text(
        f"✏️ Введите новое значение для поля <b>{field}</b>:",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "delete_user")
async def archive_user(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = data["edit_user_id"]

    await archive_user_by_id(user_id)
    await callback.message.edit_text(
        f"📦 Пользователь с ID <b>{user_id}</b> был перенесён в архив.",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer("Архивировано ✅")

# ✅ Обновляем поле
@router.message(EditUserFSM.waiting_for_new_value)
async def update_user_value(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data["edit_user_id"]
    field = data["edit_field"]
    new_value = message.text.strip()

    allowed_fields = {"full_name", "iin", "phone", "role", "section"}
    if field not in allowed_fields:
        await message.answer("🚫 Нельзя редактировать это поле.")
        await state.clear()
        return

    await update_user_field(user_id, field, new_value)
    await message.answer(f"✅ Поле <b>{field}</b> успешно обновлено для пользователя ID {user_id}.", parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data.startswith("restore:"))
async def restore_user_callback(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    await restore_user(user_id)
    await callback.message.edit_text("✅ Пользователь восстановлен.")
    await callback.answer("Восстановлен ✅")