import asyncpg
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import os
# Настройки подключения к БД
load_dotenv()

DB_CONFIG = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'host': os.getenv('DB_HOST')
}

# Пул соединений
pool: asyncpg.Pool = None

# Подключение к базе данных
async def connect_db():
    global pool
    pool = await asyncpg.create_pool(**DB_CONFIG)

# Добавление пользователя в базу данных
async def add_user(telegram_id: int, full_name: str, iin: str, role: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (telegram_id, full_name, iin, role)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_id) DO NOTHING
        """, telegram_id, full_name, iin, role)

async def get_user_by_telegram_id(telegram_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        if row:
            return dict(row)
        return None


async def add_task(section: str, description: str, deadline: str, specialist_id: int, executor_id: int):
    deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO tasks (section, description, deadline, specialist_id, executor_id)
            VALUES ($1, $2, $3, $4, $5)
        """, section, description, deadline_date, specialist_id, executor_id)

async def get_executors_by_specialist_and_section(specialist_id: int, section: str):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.full_name, u.telegram_id
            FROM users u
            JOIN section_executors se ON u.telegram_id = se.executor_id
            WHERE se.specialist_id = $1 AND se.section = $2
        """, specialist_id, section)
        return [dict(row) for row in rows]


# Получить всех пользователей с ролью специалист
async def get_all_specialists():
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT telegram_id, full_name FROM users WHERE role = 'специалист'
        """)
        return [dict(row) for row in rows]

# Привязать специалиста к разделу
async def assign_specialist_to_section(section: str, specialist_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO section_specialists (section, specialist_id)
            VALUES ($1, $2)
            ON CONFLICT (section) DO UPDATE SET specialist_id = EXCLUDED.specialist_id
        """, section, specialist_id)


async def search_specialists_by_name(query: str):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT telegram_id, full_name FROM users
            WHERE role = 'специалист' AND full_name ILIKE '%' || $1 || '%'
        """, query)
        return [dict(row) for row in rows]


# Поиск исполнителей по имени
async def get_all_executors(query: str):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT telegram_id, full_name FROM users
            WHERE role = 'исполнитель' AND full_name ILIKE $1
        """, f"%{query}%")
        return [dict(row) for row in rows]

# Получить разделы специалиста
async def get_specialist_sections(specialist_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT section FROM section_specialists
            WHERE specialist_id = $1
        """, specialist_id)
        return [row['section'] for row in rows]

# Привязка исполнителя к разделу специалиста
async def assign_executor_to_section(section: str, specialist_id: int, executor_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO section_executors (section, specialist_id, executor_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
        """, section, specialist_id, executor_id)


# Добавление нового заказа
async def add_order(gip_id: int, title: str, description: str, document_url: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO orders (gip_id, title, description, document_url)
            VALUES ($1, $2, $3, $4)
        """, gip_id, title, description, document_url)

# Получить все заказы ГИПа
async def get_orders_by_gip(gip_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, title, description, document_url FROM orders
            WHERE gip_id = $1 ORDER BY created_at DESC
        """, gip_id)
        return [dict(row) for row in rows]
    
# Получить все заказы ГИПа (синоним get_orders_by_gip)
async def get_orders_for_gip(gip_id: int):
    return await get_orders_by_gip(gip_id)

# Привязать специалиста к разделу конкретного заказа
async def assign_specialist_to_order_section(order_id: int, section: str, specialist_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO order_section_specialists (order_id, section, specialist_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (order_id, section) DO UPDATE SET specialist_id = EXCLUDED.specialist_id
        """, order_id, section, specialist_id)

# Получить всех ГИПов
async def get_all_gips():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT telegram_id FROM users WHERE role = 'гип'")
        return [row["telegram_id"] for row in rows]

async def get_all_orders():
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM orders ORDER BY created_at DESC
        """)
        return [dict(row) for row in rows]

# Удаление заказа по ID
async def delete_order(order_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM orders WHERE id = $1", order_id)


# Получение telegram_id заказчика по его ID
async def get_customer_telegram_id(customer_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT telegram_id FROM customers WHERE id = $1", customer_id)
        return row["telegram_id"] if row else None
