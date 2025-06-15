import asyncpg
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import os
from datetime import date

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


async def get_order_by_id(order_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
        return dict(row) if row else None

async def get_specialist_by_section(order_id: int, section: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT u.telegram_id
            FROM order_specialists os
            JOIN users u ON u.id = os.specialist_id
            WHERE os.order_id = $1 AND os.section = $2
        """, order_id, section)
        return row["telegram_id"] if row else None

async def update_order_status(order_id: int, status: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET status = $1 WHERE id = $2",
            status, order_id
        )


async def set_order_gip(order_id: int, gip_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET gip_id = $1 WHERE id = $2",
            gip_id, order_id
        )

async def get_specialists_by_order(order_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT os.section, u.telegram_id, u.name
            FROM order_specialist os
            JOIN users u ON u.id = os.specialist_id
            WHERE os.order_id = $1
        """, order_id)
        return [dict(row) for row in rows]

async def get_orders_by_specialist_id(specialist_telegram_id: int, section: str):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT o.*
            FROM tasks t
            JOIN users u ON u.telegram_id = $1
            JOIN orders o ON o.id = t.order_id
            WHERE t.specialist_id = u.telegram_id AND t.section = $2
        """, specialist_telegram_id, section)
        return [dict(row) for row in rows]


async def get_section_specialist(section: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id AS specialist_id, telegram_id
            FROM users
            WHERE role = 'специалист' AND section = $1
            LIMIT 1
        """, section.lower())
        return row

async def insert_order_specialist(order_id: int, section: str, specialist_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO order_specialists (order_id, section, specialist_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
        """, order_id, section.lower(), specialist_id)

# Получить специалиста по разделу
async def get_specialist_by_section(section: str):
    async with pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT id, telegram_id FROM users
            WHERE role = 'специалист' AND section = $1
            LIMIT 1
        """, section)

# Создать задачу для специалиста
async def create_task(order_id: int, section: str, description: str, deadline: int, specialist_id: int, status: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO tasks (order_id, section, description, deadline, specialist_id, status, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
        """, order_id, section, description, deadline, specialist_id, status)

async def get_ar_executors_by_order(order_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.telegram_id, u.full_name
            FROM task_executors te
            JOIN users u ON te.executor_id = u.telegram_id
            WHERE te.order_id = $1
        """, order_id)
        return [dict(row) for row in rows]

async def get_available_ar_executors(order_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, full_name, telegram_id
            FROM users
            WHERE role = 'исполнитель' AND section = 'ар'
              AND telegram_id NOT IN (
                  SELECT executor_id FROM task_executors
                  WHERE order_id = $1
              )
            LIMIT 3
        """, order_id)
        return [dict(row) for row in rows]

# Назначить исполнителя (используем telegram_id, не id)
async def assign_ar_executor_to_order(order_id: int, executor_telegram_id: int, specialist_telegram_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO task_executors (order_id, executor_id, specialist_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
        """, order_id, executor_telegram_id, specialist_telegram_id)

async def get_executors_for_order(order_id: int, section: str):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT te.id AS task_executor_id, u.full_name, u.telegram_id
            FROM task_executors te
            JOIN users u ON u.telegram_id = te.executor_id
            WHERE te.order_id = $1 AND u.section = $2
        """, order_id, section)
        return [dict(row) for row in rows]

async def update_task_for_executor(task_executor_id: int, description: str, deadline: date):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE task_executors
            SET description = $1,
                deadline = $2,
                status = 'В работе'
            WHERE id = $3
        """, description, deadline, task_executor_id)


# Получить исполнителей без отдела
async def get_unassigned_executors():
    async with pool.acquire() as conn:
        query = """
            SELECT id, full_name
            FROM users
            WHERE role = 'исполнитель' AND section IS NULL
        """
        rows = await conn.fetch(query)
        return [dict(row) for row in rows]

# Назначить исполнителя в АР
async def assign_executor_to_ar(executor_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE users
            SET section = 'ар'
            WHERE id = $1
        """, executor_id)

async def get_user_by_id(user_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        return dict(row) if row else None


# Подсчитать количество назначенных исполнителей на заказ
async def count_executors_for_order(order_id: int) -> int:
    async with pool.acquire() as conn:
        result = await conn.fetchval("""
            SELECT COUNT(*) FROM task_executors te
            WHERE te.order_id = $1
        """, order_id)
        return result


async def get_task_executor_id(order_id: int, executor_id: int) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id FROM task_executors
            WHERE order_id = $1 AND executor_id = $2
        """, order_id, executor_id)
        return row["id"] if row else None


async def get_tasks_for_executor(executor_telegram_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                te.id AS task_executor_id,
                o.title,
                te.description,
                te.deadline,
                te.status,
                o.document_url
            FROM task_executors te
            JOIN orders o ON o.id = te.order_id
            WHERE te.executor_id = $1
            ORDER BY te.deadline
        """, executor_telegram_id)
        return [dict(row) for row in rows]

async def get_ar_executor_by_task_executor_id(task_executor_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT te.executor_id, u.full_name, te.order_id, o.title
            FROM task_executors te
            JOIN users u ON u.telegram_id = te.executor_id
            JOIN orders o ON o.id = te.order_id
            WHERE te.id = $1
        """, task_executor_id)
        return dict(row) if row else None


async def mark_task_as_submitted(task_executor_id: int, file_url: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE task_executors
            SET status = 'Ожидает проверки',
                submission_file = $1
            WHERE id = $2
        """, file_url, task_executor_id)


async def get_specialist_by_task_executor_id(task_executor_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT t.specialist_id, u.full_name
            FROM task_executors te
            JOIN tasks t ON te.order_id = t.order_id AND t.section = 'ар'
            JOIN users u ON u.telegram_id = t.specialist_id
            WHERE te.id = $1
            LIMIT 1
        """, task_executor_id)
        return dict(row) if row else None

async def update_task_status(task_executor_id: int, status: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE task_executors
            SET status = $1
            WHERE id = $2
        """, status, task_executor_id)

async def get_executor_by_task_executor_id(task_executor_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT executor_id FROM task_executors
            WHERE id = $1
        """, task_executor_id)
        return dict(row) if row else None


async def get_upcoming_deadlines():
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                te.id AS task_executor_id,
                te.deadline,
                te.status,
                te.executor_id,
                t.specialist_id,
                o.title
            FROM task_executors te
            JOIN tasks t ON te.task_id = t.id
            JOIN orders o ON t.order_id = o.id
            WHERE te.deadline IS NOT NULL
              AND te.status != 'Готово'
        """)
        return [dict(row) for row in rows]


async def get_specialist_by_order_and_section(order_id: int, section: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT t.specialist_id, u.full_name, u.telegram_id
            FROM tasks t
            JOIN users u ON u.telegram_id = t.specialist_id
            WHERE t.order_id = $1 AND LOWER(t.section) = LOWER($2)
            LIMIT 1
        """, order_id, section)
        return dict(row) if row else None

async def get_latest_submitted_file_for_order(order_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT submission_file  -- ИЛИ другой правильный столбец
            FROM task_executors
            WHERE order_id = $1 AND submission_file IS NOT NULL
            ORDER BY assigned_at DESC
            LIMIT 1
        """, order_id)
        return row["submission_file"] if row else None


async def mark_ar_file_submission(order_id: int, relative_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE orders SET document_url = $1 WHERE id = $2
        """, relative_path, order_id)


async def set_task_document_url(order_id: int, section: str, file_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET document_url = $1
            WHERE order_id = $2 AND LOWER(section) = LOWER($3)
        """, file_path, order_id, section)


async def get_ar_task_document(order_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT document_url FROM tasks
            WHERE order_id = $1 AND LOWER(section) = 'ар'
        """, order_id)
        return row["document_url"] if row else None

async def save_ar_file_path_to_tasks(order_id: int, relative_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET document_url = $1
            WHERE order_id = $2 AND LOWER(section) = 'ар'
        """, relative_path, order_id)

async def save_calc_file_path_to_tasks(order_id: int, relative_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET document_url = $1
            WHERE order_id = $2 AND section = 'расчет'
        """, relative_path, order_id)

async def save_genplan_file_path_to_tasks(order_id: int, relative_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET document_url = $1
            WHERE order_id = $2 AND section = 'генплан'
        """, relative_path, order_id)

async def get_orders_by_specialist_id_tg(specialist_telegram_id: int, section: str):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT o.*
            FROM tasks t
            JOIN orders o ON o.id = t.order_id
            WHERE t.specialist_id = $1 AND t.section = $2
        """, specialist_telegram_id, section)
        print(f"[DEBUG] Найдено заказов: {len(rows)}")
        return [dict(row) for row in rows]