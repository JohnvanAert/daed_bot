from aiogram import Router, F
from aiogram.types import Message
from database import get_user_profile

router = Router()

@router.message(F.text == "👤 Мой профиль")
async def show_my_profile(message: Message):
    profile = await get_user_profile(message.from_user.id)

    if not profile:
        await message.answer("❗️ Ваш профиль не найден.")
        return

    text = f"👤 <b>Ваш профиль</b>\n\n"
    text += f"ФИО: <b>{profile['full_name']}</b>\n"
    text += f"ИИН/БИН: <b>{profile['iin'] if profile['iin'] else 'Не указан'}</b>\n"
    text += f"Telegram ID: <code>{profile['telegram_id']}</code>\n"
    text += f"Роль: <b>{profile['role'].capitalize()}</b>\n"

    # Покажем секцию если есть (для специалистов)
    if profile.get('section'):
        text += f"Секция: <b>{profile['section'].upper()}</b>\n"

    text += f"Зарегистрирован: <b>{profile['registered_at'].strftime('%Y-%m-%d %H:%M')}</b>"

    await message.answer(text, parse_mode="HTML")
