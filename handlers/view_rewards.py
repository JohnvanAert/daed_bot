# handlers/view_rewards.py
from aiogram import Router, F
from aiogram.types import Message
from database import get_user_bonuses_and_penalties

router = Router()

@router.message(F.text == "🎖 Мои бонусы и штрафы")
async def show_my_rewards(message: Message):
    user_id = message.from_user.id
    records = await get_user_bonuses_and_penalties(user_id)

    if not records:
        await message.answer("❌ У вас пока нет бонусов и штрафов.")
        return

    text_lines = []
    for rec in records:
        emoji = "✅" if rec["type"] == "bonus" else "🚫"
        text_lines.append(f"{emoji} <b>{rec['type'].capitalize()}</b> (заказ #{rec['order_id']}):\n{rec['description']}")

    await message.answer("\n\n".join(text_lines), parse_mode="HTML")
