from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from states.edit_user_states import EditCustomerFSM
from database import get_all_customers, update_customer_field, archive_customer_by_id, restore_customer, get_archived_customers_sorted_by_id

USERS_PER_PAGE = 5
router = Router()

# ====== Пагинация заказчиков ======
@router.callback_query(F.data == "edit_type:customers")
async def show_customers_start(callback: CallbackQuery):
    await show_customers_page(callback.message, page=0, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("customers_page:"))
async def paginate_customers(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await show_customers_page(callback.message, page, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("archive_customers_page:"))
async def paginate_archived_customers(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await show_customers_page(callback.message, page, edit=True, is_archive=True)
    await callback.answer()


async def show_customers_page(message: Message, page: int, edit=False, is_archive=False):
    customers = await (get_archived_customers_sorted_by_id() if is_archive else get_all_customers())
    total_pages = (len(customers) - 1) // USERS_PER_PAGE + 1

    start_idx = page * USERS_PER_PAGE
    end_idx = start_idx + USERS_PER_PAGE
    page_customers = customers[start_idx:end_idx]

    if not page_customers:
        text = "❌ Заказчики не найдены."
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return

    kb_buttons = [[
        InlineKeyboardButton(
            text=f"🆔 {c['id']} {c['full_name']}",
            callback_data=f"{'restore_customer' if is_archive else 'edit_customer'}:{c['id']}"
        )
    ] for c in page_customers]

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"{'archive_customers_page' if is_archive else 'customers_page'}:{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️ Следующая", callback_data=f"{'archive_customers_page' if is_archive else 'customers_page'}:{page + 1}"))

    if nav_buttons:
        kb_buttons.append(nav_buttons)

    if not is_archive:
        kb_buttons.append([
            InlineKeyboardButton(text="📁 Архив заказчиков", callback_data="archive_customers_page:0")
        ])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    title = "📁 Архив заказчиков" if is_archive else "📦 Страница заказчиков"
    text = f"{title} <b>{page + 1}</b> из <b>{total_pages}</b>"

    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


# ====== Меню редактирования конкретного заказчика ======
@router.callback_query(F.data.startswith("edit_customer:"))
async def edit_customer_profile(callback: CallbackQuery, state: FSMContext):
    customer_id = int(callback.data.split(":")[1])
    await state.update_data(edit_customer_id=customer_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить ФИО", callback_data="edit_customer_field:full_name")],
        [InlineKeyboardButton(text="🆔 Изменить ИИН/БИН", callback_data="edit_customer_field:iin_or_bin")],
        [InlineKeyboardButton(text="📱 Изменить телефон", callback_data="edit_customer_field:phone")],
        [InlineKeyboardButton(text="✉️ Изменить Email", callback_data="edit_customer_field:email")],
        [InlineKeyboardButton(text="🗑 Удалить заказчика", callback_data="delete_customer")]
    ])
    await callback.message.edit_text(
        f"🔧 Что хотите изменить у заказчика ID <b>{customer_id}</b>?",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


# ====== FSM для ввода нового значения ======
@router.callback_query(F.data.startswith("edit_customer_field:"))
async def ask_new_customer_value(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]
    await state.update_data(edit_customer_field=field)
    await state.set_state(EditCustomerFSM.waiting_for_new_value)
    await callback.message.edit_text(
        f"✏️ Введите новое значение для поля <b>{field}</b>:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(EditCustomerFSM.waiting_for_new_value)
async def save_customer_new_value(message: Message, state: FSMContext):
    data = await state.get_data()
    customer_id = data["edit_customer_id"]
    field = data["edit_customer_field"]
    new_value = message.text.strip()

    await update_customer_field(customer_id, field, new_value)
    await message.answer(f"✅ Данные заказчика ID <b>{customer_id}</b> успешно обновлены.", parse_mode="HTML")
    await state.clear()


# ====== Архивирование заказчика ======
@router.callback_query(F.data == "delete_customer")
async def archive_customer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    customer_id = data["edit_customer_id"]

    await archive_customer_by_id(customer_id)
    await callback.message.edit_text(
        f"📦 Заказчик ID <b>{customer_id}</b> был перенесён в архив.",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer("Архивировано ✅")


# ====== Восстановление заказчика ======
@router.callback_query(F.data.startswith("restore_customer:"))
async def restore_customer_callback(callback: CallbackQuery):
    customer_id = int(callback.data.split(":")[1])
    await restore_customer(customer_id)
    await callback.message.edit_text("✅ Заказчик восстановлен.")
    await callback.answer("Восстановлен ✅")
