from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import get_orders_by_gip  # уже реализована

router = Router()

@router.message(F.text == "/orders")
async def show_orders(message: Message):
    gip_id = message.from_user.id
    orders = await get_orders_by_gip(gip_id)

    if not orders:
        await message.answer("📭 У вас пока нет заказов.")
        return

    for order in orders:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔛 Подключить АР", callback_data=f"connect_ar:{order['id']}")]
            ]
        )

        text = (
            f"📄 <b>{order['title']}</b>\n"
            f"📝 {order['description'] or 'Без описания'}\n"
            f"📎 <a href=\"{order['document_url']}\">Документ</a>"
        )

        await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("connect_ar:"))
async def handle_connect_ar(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])

    # Здесь логика для назначения специалиста по разделу АР
    await callback.message.edit_text(
        f"✅ Раздел <b>АР</b> подключен к заказу #{order_id}. Назначьте специалиста."
    )
