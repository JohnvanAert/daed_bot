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
