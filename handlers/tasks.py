from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from states.task_states import TaskCreateState
from database import add_task, get_executors_by_specialist_and_section
from datetime import datetime

router = Router()

SECTIONS = ["Архитектура", "Конструктив", "ВК", "ОВиК", "ЭОМ", "ГП", "Сметы"]

@router.message(F.text.casefold() == "создать задачу")
async def start_task_creation(message: Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=section)] for section in SECTIONS],
        resize_keyboard=True
    )
    await message.answer("Выберите раздел проекта:", reply_markup=kb)
    await state.set_state(TaskCreateState.choosing_section)

@router.message(TaskCreateState.choosing_section)
async def choose_section(message: Message, state: FSMContext):
    section = message.text
    if section not in SECTIONS:
        await message.answer("Выберите раздел из клавиатуры.")
        return

    await state.update_data(section=section)
    specialist_id = message.from_user.id
    executors = await get_executors_by_specialist_and_section(specialist_id, section)

    if not executors:
        await message.answer("❗️Нет исполнителей, закреплённых за этим разделом.")
        await state.clear()
        return

    await state.update_data(available_executors=executors)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=e["full_name"])] for e in executors],
        resize_keyboard=True
    )
    await message.answer("Выберите исполнителя:", reply_markup=kb)
    await state.set_state(TaskCreateState.choosing_executor)

@router.message(TaskCreateState.choosing_executor)
async def choose_executor(message: Message, state: FSMContext):
    executor_name = message.text
    data = await state.get_data()
    executors = data.get("available_executors", [])

    match = next((e for e in executors if e["full_name"] == executor_name), None)
    if not match:
        await message.answer("❗ Исполнитель не найден. Попробуйте снова.")
        return

    await state.update_data(executor_id=match["telegram_id"])

    await message.answer("Введите дедлайн (в формате ГГГГ-ММ-ДД):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(TaskCreateState.entering_deadline)

@router.message(TaskCreateState.entering_deadline)
async def enter_deadline(message: Message, state: FSMContext):
    try:
        deadline = datetime.strptime(message.text, "%Y-%m-%d").date()
        await state.update_data(deadline=str(deadline))
    except ValueError:
        await message.answer("Неверный формат. Введите дедлайн в формате ГГГГ-ММ-ДД:")
        return

    await message.answer("Введите описание задачи:")
    await state.set_state(TaskCreateState.entering_description)

@router.message(TaskCreateState.entering_description)
async def enter_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    data = await state.get_data()

    await add_task(
        section=data['section'],
        description=data['description'],
        deadline=data['deadline'],
        specialist_id=message.from_user.id,
        executor_id=data["executor_id"]
    )

    await message.answer("✅ Задача успешно создана и отправлена исполнителю.")
    await state.clear()
