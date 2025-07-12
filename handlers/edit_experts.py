from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from states.edit_states import EditExpertFSM
from database import (
    get_all_experts,
    get_archived_experts_sorted_by_id,
    update_expert_field,
    archive_expert_by_id,
    restore_expert
)

router = Router()
EXPERTS_PER_PAGE = 5

# 📋 Показать список экспертов
@router.callback_query(F.data == "edit_type:experts")
async def show_experts_list(callback: CallbackQuery):
    experts = await get_all_experts()
    if not experts:
        await callback.message.edit_text("❌ Эксперты не найдены.")
        await callback.answer()
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🆔 {e['id']} {e['full_name']}", callback_data=f"edit_expert:{e['id']}")]
        for e in experts
    ] + [[InlineKeyboardButton(text="📁 Архив экспертов", callback_data="archive_expert_page:0")]])

    await callback.message.edit_text("🎓 Список экспертов:", reply_markup=kb)
    await callback.answer()

# 🖐 Меню управления экспертом
@router.callback_query(F.data.startswith("edit_expert:"))
async def edit_expert(callback: CallbackQuery, state: FSMContext):
    expert_id = int(callback.data.split(":")[1])
    await state.update_data(edit_expert_id=expert_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить ФИО", callback_data="edit_expert_field:full_name")],
        [InlineKeyboardButton(text="🛠 Изменить секцию", callback_data="edit_expert_field:section")],
        [InlineKeyboardButton(text="🗑 Удалить эксперта", callback_data="delete_expert")]
    ])
    await callback.message.edit_text(
        f"🖐 Что хотите изменить у эксперта ID <b>{expert_id}</b>?",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "edit_expert_field:section")
async def choose_expert_section(callback: CallbackQuery, state: FSMContext):
    sections = ["эп", "ар", "кж", "гп", "рс", "сс", "овик", "гс", "вк", "эом"]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=sec.upper(), callback_data=f"set_expert_section:{sec}")] for sec in sections
    ])
    await callback.message.edit_text("Выберите новую секцию для эксперта:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("set_expert_section:"))
async def set_expert_section(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    expert_id = data["edit_expert_id"]
    new_section = callback.data.split(":")[1]

    await update_expert_field(expert_id, "section", new_section)
    await callback.message.edit_text(
        f"✅ Секция эксперта ID <b>{expert_id}</b> обновлена на <b>{new_section.upper()}</b>.",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()

@router.message(F.state == EditExpertFSM.waiting_for_new_field_value)
async def save_expert_value(message: Message, state: FSMContext):
    data = await state.get_data()
    expert_id = data["edit_expert_id"]
    field = data["edit_field"]
    value = message.text.strip()

    await update_expert_field(expert_id, field, value)
    await message.answer(
        f"✅ Поле <b>{field}</b> эксперта ID <b>{expert_id}</b> обновлено.",
        parse_mode="HTML"
    )
    await state.clear()

# 🗑 Архивируем
@router.callback_query(F.data == "delete_expert")
async def archive_expert(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    expert_id = data["edit_expert_id"]

    await archive_expert_by_id(expert_id)
    await callback.message.edit_text(
        f"📆 Эксперт ID <b>{expert_id}</b> был перенесён в архив.",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer("Архивировано ✅")

@router.callback_query(F.data.startswith("restore_expert:"))
async def restore_expert_callback(callback: CallbackQuery):
    expert_id = int(callback.data.split(":")[1])
    await restore_expert(expert_id)
    await callback.message.edit_text("✅ Эксперт восстановлен.")
    await callback.answer("Восстановлен ✅")

@router.callback_query(F.data.startswith("archive_expert_page:"))
async def paginate_archived_experts(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await show_archived_experts_page(callback.message, page, edit=True)
    await callback.answer()

async def show_archived_experts_page(message: Message, page: int, edit=False):
    experts = await get_archived_experts_sorted_by_id()
    await show_experts_page_common(message, page, experts, edit, is_archive=True)

async def show_experts_page_common(message: Message, page: int, experts, edit, is_archive=False):
    total_pages = (len(experts) - 1) // EXPERTS_PER_PAGE + 1
    start_idx = page * EXPERTS_PER_PAGE
    end_idx = start_idx + EXPERTS_PER_PAGE
    page_experts = experts[start_idx:end_idx]

    if not page_experts:
        text = "❗ Эксперты не найдены."
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return

    kb_buttons = []
    for e in page_experts:
        text_btn = f"🆔{e['id']} {e['full_name']}"
        cb_data = f"restore_expert:{e['id']}" if is_archive else f"edit_expert:{e['id']}"
        kb_buttons.append([InlineKeyboardButton(text=text_btn, callback_data=cb_data)])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Предыдущая",
            callback_data=f"{'archive_expert_page' if is_archive else 'experts_page'}:{page - 1}"
        ))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(
            text="➡️ Следующая",
            callback_data=f"{'archive_expert_page' if is_archive else 'experts_page'}:{page + 1}"
        ))
    if nav_buttons:
        kb_buttons.append(nav_buttons)

    if not is_archive:
        kb_buttons.append([
            InlineKeyboardButton(text="📁 Архив экспертов", callback_data="archive_expert_page:0")
        ])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    title = "📁 Архив экспертов" if is_archive else "📋 Эксперты"
    text = f"{title}\nСтраница <b>{page + 1}</b> из <b>{total_pages}</b>"

    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
