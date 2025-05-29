from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import get_order_by_id, get_customer_telegram_id, get_specialist_by_section
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import FSInputFile
import os
from aiogram.types import Document

router = Router()

class ReviewCorrectionFSM(StatesGroup):
    waiting_for_comment = State()
    waiting_for_fixed_file = State()
    waiting_for_customer_question = State()
    waiting_for_customer_zip = State()

@router.callback_query(F.data.startswith("gip_approve:"))
async def handle_gip_approval(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    customer_id = await get_customer_telegram_id(order["customer_id"])
    
    # 📎 Путь к принятому файлу ЭП (обнови под свою структуру хранения)
    ep_file_path = os.path.abspath(os.path.join("..", "clientbot", order["document_url"]))

    if os.path.exists(ep_file_path):
        caption = (
            f"📦 По вашему заказу <b>{order['title']}</b> выполнен раздел ЭП.\n"
            f"📄 Пожалуйста, предоставьте следующие документы:\n"
            f"🔷 ГПЗУ\n🔷 ТУ\n🔷 ПДП"
        )
        await callback.bot.send_document(
            chat_id=customer_id,
            document=FSInputFile(ep_file_path),
            caption=caption,
            parse_mode="HTML"
        )
    else:
        await callback.message.answer("❗ Файл ЭП не найден.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍 Всё получено", callback_data=f"customer_received:{order_id}"),
            InlineKeyboardButton(text="📣 Есть вопросы", callback_data=f"customer_has_questions:{order_id}")
        ]
    ])
    await callback.bot.send_message(
        chat_id=customer_id,
        text="❓ Уточните статус: вы получили и всё понятно?",
        reply_markup=keyboard
    )

    # Очистка кнопок
    await callback.message.edit_reply_markup()
    await callback.message.answer("✅ Заказ передан заказчику.")
    await callback.answer("Передано заказчику ✅", show_alert=True)

@router.callback_query(F.data.startswith("gip_reject:"))
async def handle_gip_rejection(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewCorrectionFSM.waiting_for_comment)
    await state.update_data(order_id=order_id)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❗ Напишите комментарий с замечаниями по ЭП:")

@router.message(ReviewCorrectionFSM.waiting_for_comment)
async def send_correction_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    comment = message.text.strip()
    order = await get_order_by_id(order_id)

    specialist = await get_specialist_by_section("эп")
    if not specialist:
        await message.answer("❗ Специалист не найден.")
        await state.clear()
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Прикрепить исправленный файл", callback_data=f"resubmit_ep:{order['id']}")]
    ])
    await message.bot.send_message(
        chat_id=specialist["telegram_id"],
        text=(
            f"❗ <b>Замечания по ЭП</b> по заказу: <b>{order['title']}</b>\n\n"
            f"{comment}"
        ),
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await message.answer("✉️ Замечания отправлены специалисту.")
    await state.clear()


@router.callback_query(F.data.startswith("customer_received:"))
async def handle_customer_received(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    specialist = await get_specialist_by_section("эп")

    # Уведомление исполнителям
    await callback.bot.send_message(
        chat_id=specialist["telegram_id"],
        text=f"✅ Заказчик подтвердил получение ЭП по заказу: <b>{order['title']}</b>",
        parse_mode="HTML"
    )
    await callback.bot.send_message(
        chat_id=order["gip_id"],
        text=f"✅ Заказчик подтвердил получение ЭП по заказу: <b>{order['title']}</b>",
        parse_mode="HTML"
    )

    # Устанавливаем состояние
    await state.set_state(ReviewCorrectionFSM.waiting_for_customer_zip)
    await state.update_data(order_id=order_id)

    await callback.message.edit_reply_markup()
    await callback.message.answer("📦 Пожалуйста, отправьте ZIP-архив с документами (ГПЗУ, ТУ, ПДП).")
    await callback.answer("Ожидаю ZIP-файл 📂", show_alert=True)

@router.callback_query(F.data.startswith("customer_has_questions:"))
async def handle_customer_has_questions(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewCorrectionFSM.waiting_for_customer_question)
    await state.update_data(order_id=order_id)
    
    await callback.message.edit_reply_markup()
    await callback.message.answer("📩 Напишите, пожалуйста, свой вопрос по заказу:")
    await callback.answer()

@router.message(ReviewCorrectionFSM.waiting_for_customer_question)
async def receive_customer_question(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    question = message.text.strip()

    order = await get_order_by_id(order_id)
    specialist = await get_specialist_by_section("эп")
    
    if not specialist:
        await message.answer("❗ Не удалось найти специалиста по ЭП.")
        await state.clear()
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📄 Прикрепить файл", callback_data=f"spec_attach_file:{order_id}"),
            InlineKeyboardButton(text="💬 Ответить комментарием", callback_data=f"spec_reply_comment:{order_id}")
        ]
    ])

    # Отправляем специалисту с кнопками
    await message.bot.send_message(
        chat_id=specialist["telegram_id"],
        text=(
            f"📣 <b>Вопрос от заказчика</b> по заказу: <b>{order['title']}</b>\n\n"
            f"{question}"
        ),
        parse_mode="HTML",
        reply_markup=keyboard
    )

    # Отправляем ГИПу
    await message.bot.send_message(
        chat_id=order["gip_id"],
        text=(
            f"📣 <b>Вопрос от заказчика</b> по заказу: <b>{order['title']}</b>\n\n"
            f"{question}"
        ),
        parse_mode="HTML"
    )

    await message.answer("✅ Ваш вопрос был передан специалисту и ГИПу.")
    await state.clear()

@router.callback_query(F.data.startswith("resubmit_ep:"))
async def handle_resubmit_ep(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(ReviewCorrectionFSM.waiting_for_fixed_file)
    await state.update_data(order_id=order_id)
    await callback.message.answer("📎 Прикрепите исправленный PDF файл ЭП:")
    await callback.answer()

@router.message(ReviewCorrectionFSM.waiting_for_fixed_file, F.document)
async def receive_fixed_ep(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    order = await get_order_by_id(order_id)

    document: Document = message.document
    if not document.file_name.lower().endswith(".pdf"):
        await message.answer("❗ Пожалуйста, прикрепите файл в формате PDF.")
        return

    # Отправим ГИПу
    await message.bot.send_document(
        chat_id=order["gip_id"],
        document=document,
        caption=f"📩 Исправленный ЭП по заказу: <b>{order['title']}</b>",
        parse_mode="HTML"
    )

    await message.answer("✅ Исправленный файл отправлен ГИПу на проверку.")
    await state.clear()


@router.message(ReviewCorrectionFSM.waiting_for_customer_zip, F.document)
async def receive_customer_zip(message: Message, state: FSMContext):
    document = message.document

    # Проверим, ZIP ли это
    if not document.file_name.lower().endswith(".zip"):
        await message.answer("❗ Пожалуйста, отправьте архив в формате .zip")
        return

    data = await state.get_data()
    order = await get_order_by_id(data["order_id"])

    # Уведомим ГИПа и специалиста
    for user_id in [order["gip_id"], (await get_specialist_by_section("эп"))["telegram_id"]]:
        await message.bot.send_document(
            chat_id=user_id,
            document=document,
            caption=f"📥 Получен ZIP-файл от заказчика по заказу: <b>{order['title']}</b>",
            parse_mode="HTML"
        )

    await message.answer("✅ Спасибо! ZIP-файл передан исполнителям.")
    await state.clear()
