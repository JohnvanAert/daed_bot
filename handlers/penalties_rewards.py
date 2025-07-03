# penalties_rewards.py
from datetime import datetime
from database import (
    get_order_by_id,
    add_bonus_or_penalty,
    check_existing_penalty
)

async def complete_project(order_id):
    order = await get_order_by_id(order_id)
    deadline = order["deadline"]
    completed_at = datetime.now()
    user_id = order["specialist_id"]

    if completed_at <= deadline:
        # Добавляем бонус
        await add_bonus_or_penalty(
            user_id=user_id,
            order_id=order_id,
            type="bonus",
            description="Проект завершён в срок и без ошибок"
        )
    else:
        # Проверим, есть ли уже штраф
        exists_penalty = await check_existing_penalty(user_id, order_id)
        if not exists_penalty:
            await add_bonus_or_penalty(
                user_id=user_id,
                order_id=order_id,
                type="penalty",
                description=f"Просрочка проекта на {(completed_at - deadline).days} дн."
            )
