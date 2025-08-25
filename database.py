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
async def add_user(
    telegram_id: int,
    full_name: str,
    iin: str,
    role: str,
    address: str = None,
    bank: str = None,
    iban: str = None,
    bik: str = None,
    kbe: str = "19",
    email: str = None,
    phone: str = None
):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (
                telegram_id, full_name, iin, role,
                address, bank, iban, bik, kbe, email, phone
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (telegram_id) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                iin = EXCLUDED.iin,
                role = EXCLUDED.role,
                address = EXCLUDED.address,
                bank = EXCLUDED.bank,
                iban = EXCLUDED.iban,
                bik = EXCLUDED.bik,
                kbe = EXCLUDED.kbe,
                email = EXCLUDED.email,
                phone = EXCLUDED.phone
        """, telegram_id, full_name, iin, role,
             address, bank, iban, bik, kbe, email, phone)

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
            SELECT * FROM orders
            WHERE status != 'completed'
            ORDER BY created_at DESC
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
            WHERE order_id = $2 AND section = 'рс'
        """, relative_path, order_id)

async def save_genplan_file_path_to_tasks(order_id: int, relative_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET document_url = $1
            WHERE order_id = $2 AND section = 'гп'
        """, relative_path, order_id)

async def get_orders_by_specialist_id_tg(specialist_telegram_id: int, section: str):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT o.*
            FROM tasks t
            JOIN orders o ON o.id = t.order_id
            WHERE t.specialist_id = $1 AND t.section = $2
        """, specialist_telegram_id, section)
        return [dict(row) for row in rows]
    

async def get_tasks_by_order(order_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT section FROM tasks WHERE order_id = $1", order_id)
        return [dict(row) for row in rows]

async def update_task_status(order_id: int, section: str, new_status: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET status = $1
            WHERE order_id = $2 AND section = $3
        """, new_status, order_id, section)

async def get_genplan_task_document(order_id: int) -> str | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT document_url
            FROM tasks
            WHERE order_id = $1 AND section = 'гп' AND document_url IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
        """, order_id)
        if row:
            return row["document_url"]
        return None
async def get_calc_task_document(order_id: int) -> str | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT document_url
            FROM tasks
            WHERE order_id = $1 AND section = 'рс' AND document_url IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
        """, order_id)
        if row:
            return row["document_url"]
        return None
    
async def update_task_document_path(order_id: int, section: str, new_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET document_url = $1
            WHERE order_id = $2 AND section = $3
        """, new_path, order_id, section)


async def save_kj_file_path_to_tasks(order_id: int, relative_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET document_url = $1
            WHERE order_id = $2 AND section = 'кж'
        """, relative_path, order_id)

async def get_kj_task_document(order_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT document_url FROM tasks
            WHERE order_id = $1 AND LOWER(section) = 'кж'
        """, order_id)
        return row["document_url"] if row else None


async def save_ovik_file_path_to_tasks(order_id: int, relative_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET document_url = $1
            WHERE order_id = $2 AND section = 'овик'
        """, relative_path, order_id)

async def save_vk_file_path_to_tasks(order_id: int, relative_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET document_url = $1
            WHERE order_id = $2 AND section = 'вк'
        """, relative_path, order_id)

async def save_gs_file_path_to_tasks(order_id: int, relative_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET document_url = $1
            WHERE order_id = $2 AND section = 'гс'
        """, relative_path, order_id)


async def get_ovik_task_document(order_id: int) -> str | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT document_url FROM tasks
            WHERE order_id = $1 AND section = 'овик'
        """, order_id)
        return row["document_url"] if row else None

async def get_gs_task_document(order_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT document_url FROM tasks
            WHERE order_id = $1 AND section = 'гс'
        """, order_id)
        return row["document_url"] if row else None

async def get_available_kj_executors(order_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, full_name, telegram_id
            FROM users
            WHERE role = 'исполнитель' AND section = 'кж'
              AND telegram_id NOT IN (
                  SELECT executor_id FROM task_executors
                  WHERE order_id = $1
              )
            LIMIT 3
        """, order_id)
        return [dict(row) for row in rows]


async def assign_executor_to_kj_order(order_id: int, executor_telegram_id: int, specialist_telegram_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO task_executors (order_id, executor_id, specialist_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
        """, order_id, executor_telegram_id, specialist_telegram_id)


async def get_available_ovik_executors(order_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, full_name, telegram_id
            FROM users
            WHERE role = 'исполнитель' AND section = 'овик'
              AND telegram_id NOT IN (
                  SELECT executor_id FROM task_executors
                  WHERE order_id = $1
              )
            LIMIT 3
        """, order_id)
        return [dict(row) for row in rows]


async def assign_executor_to_ovik_order(order_id: int, executor_telegram_id: int, specialist_telegram_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO task_executors (order_id, executor_id, specialist_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
        """, order_id, executor_telegram_id, specialist_telegram_id)

async def get_available_gs_executors(order_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, full_name, telegram_id
            FROM users
            WHERE role = 'исполнитель' AND section = 'гс'
              AND telegram_id NOT IN (
                  SELECT executor_id FROM task_executors
                  WHERE order_id = $1
              )
            LIMIT 3
        """, order_id)
        return [dict(row) for row in rows]

async def assign_executor_to_gs_order(order_id: int, executor_telegram_id: int, specialist_telegram_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO task_executors (order_id, executor_id, specialist_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
        """, order_id, executor_telegram_id, specialist_telegram_id)

async def get_available_vk_executors(order_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, full_name, telegram_id
            FROM users
            WHERE role = 'исполнитель' AND section = 'вк'
              AND telegram_id NOT IN (
                  SELECT executor_id FROM task_executors
                  WHERE order_id = $1
              )
            LIMIT 3
        """, order_id)
        return [dict(row) for row in rows]

async def assign_executor_to_vk_order(order_id: int, executor_telegram_id: int, specialist_telegram_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO task_executors (order_id, executor_id, specialist_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
        """, order_id, executor_telegram_id, specialist_telegram_id)


async def get_eom_task_document(order_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT document_url FROM tasks
            WHERE order_id = $1 AND section = 'эом'
        """, order_id)
        return row["document_url"] if row else None


async def save_eom_file_path_to_tasks(order_id: int, relative_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET document_url = $1
            WHERE order_id = $2 AND LOWER(section) = 'эом'
        """, relative_path, order_id)


async def get_available_eom_executors(order_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, full_name, telegram_id
            FROM users
            WHERE role = 'исполнитель' AND section = 'эом'
              AND telegram_id NOT IN (
                  SELECT executor_id FROM task_executors
                  WHERE order_id = $1
              )
            LIMIT 3
        """, order_id)
        return [dict(row) for row in rows]


async def assign_executor_to_eom_order(order_id: int, executor_telegram_id: int, specialist_telegram_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO task_executors (order_id, executor_id, specialist_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
        """, order_id, executor_telegram_id, specialist_telegram_id)

async def assign_executor_to_ss_order(order_id: int, executor_telegram_id: int, specialist_telegram_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO task_executors (order_id, executor_id, specialist_id)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
        """, order_id, executor_telegram_id, specialist_telegram_id)


async def get_available_ss_executors(order_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, full_name, telegram_id
            FROM users
            WHERE role = 'исполнитель' AND section = 'сс'
              AND telegram_id NOT IN (
                  SELECT executor_id FROM task_executors
                  WHERE order_id = $1
              )
            LIMIT 3
        """, order_id)
        return [dict(row) for row in rows]

async def save_ss_file_path_to_tasks(order_id: int, relative_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET document_url = $1
            WHERE order_id = $2 AND LOWER(section) = 'сс'
        """, relative_path, order_id)

async def get_ss_task_document(order_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT document_url FROM tasks
            WHERE order_id = $1 AND section = 'сс'
        """, order_id)
        return row["document_url"] if row else None


# Для task_executors
async def get_upcoming_executor_deadlines():
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                te.id AS task_executor_id,
                te.deadline,
                te.status,
                te.executor_id,
                o.title,
                t.section
            FROM task_executors te
            JOIN orders o ON te.order_id = o.id
            JOIN tasks t ON te.task_id = t.id
            WHERE te.deadline IS NOT NULL
              AND te.status != 'Готово'
        """)
        return [dict(row) for row in rows]


# Для tasks
async def get_upcoming_specialist_deadlines():
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                t.id,
                t.deadline,
                t.status,
                t.specialist_id,
                t.section,
                t.order_id
            FROM tasks t
            WHERE t.deadline IS NOT NULL
              AND t.status != 'Сделано'
        """)
        return [dict(row) for row in rows]

async def get_vk_task_document(order_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT document_url FROM tasks
            WHERE order_id = $1 AND section = 'вк'
        """, order_id)
        return row["document_url"] if row else None

async def save_estimate_file_path_to_tasks(order_id: int, relative_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET document_url = $1
            WHERE order_id = $2 AND LOWER(section) = 'смета'
        """, relative_path, order_id)

async def get_all_experts():
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT telegram_id, section
            FROM users
            WHERE role = 'эксперт'
        """)
        return [dict(r) for r in rows]

async def get_task_document_by_section(order_id: int, section: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT document_url FROM tasks
            WHERE order_id = $1 AND LOWER(section) = $2
        """, order_id, section.lower())
        return row["document_url"] if row else None


async def register_expert(full_name: str, telegram_id: int, section: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO experts (full_name, telegram_id, section)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id) DO NOTHING
        """, full_name, telegram_id, section)

async def get_expert_tasks(telegram_id: int, completed: bool = False):
    async with pool.acquire() as conn:
        expert_row = await conn.fetchrow(
            "SELECT id FROM experts WHERE telegram_id = $1", telegram_id
        )
        if not expert_row:
            return []

        expert_id = expert_row["id"]

        status_filter = "et.status = 'Одобрено'" if completed else "et.status != 'Одобрено'"

        rows = await conn.fetch(f"""
            SELECT
                et.id AS task_id,
                et.status,
                t.section,
                t.description AS order_description,
                t.document_url,
                t.expert_note_url,
                o.title AS order_title
            FROM expert_tasks et
            JOIN tasks t ON t.id = et.task_id
            JOIN orders o ON o.id = t.order_id
            WHERE et.expert_id = $1
              AND {status_filter}
            ORDER BY o.created_at DESC
        """, expert_id)

        return [dict(row) for row in rows]


async def is_expert_registered(telegram_id: int) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM experts WHERE telegram_id = $1", telegram_id)
        return row is not None

async def get_expert_by_telegram_id(telegram_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM experts WHERE telegram_id = $1", telegram_id)


async def add_expert(telegram_id: int, full_name: str, section: str = "не назначен"):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO experts (telegram_id, full_name, section)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id) DO NOTHING
        """, telegram_id, full_name, section)

async def update_expert_note_file(task_id: int, file_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET expert_note_url = $1
            WHERE id = $2
        """, file_path, task_id)



#database client
# Добавление нового заказчика
async def add_customer(telegram_id: int, full_name: str, iin_or_bin: str, phone: str, email: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO customers (telegram_id, full_name, iin_or_bin, phone, email)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (telegram_id) DO UPDATE 
            SET full_name = EXCLUDED.full_name,
                iin_or_bin = EXCLUDED.iin_or_bin,
                phone = EXCLUDED.phone,
                email = EXCLUDED.email
        """, telegram_id, full_name, iin_or_bin, phone, email)

# Получение информации о заказчике
async def get_customer_by_telegram_id(telegram_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM customers WHERE telegram_id = $1", telegram_id)
        return dict(row) if row else None

# Получение всех заказов
async def add_order(title: str, description: str, document_url: str, customer_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO orders (title, description, document_url, customer_id, created_at)
            VALUES ($1, $2, $3, $4, NOW())
        """, title, description, document_url, customer_id)


# Получение заказчика по Telegram ID
async def get_customer_by_telegram_id(telegram_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM customers WHERE telegram_id = $1
        """, telegram_id)
        return dict(row) if row else None

# Получить всех ГИПов
async def get_all_gips():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT telegram_id FROM users WHERE role = 'гип'")
        return [row["telegram_id"] for row in rows]

async def update_order_document(order_id: int, new_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE orders
            SET document_url = $1
            WHERE id = $2
        """, new_path, order_id)

async def get_order_by_customer_id(customer_telegram_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT o.*
            FROM orders o
            JOIN users u ON o.customer_id = u.id
            WHERE u.telegram_id = $1
            ORDER BY o.created_at DESC
            LIMIT 1
        """, customer_telegram_id)
        return dict(row) if row else None


async def get_orders_by_customer_telegram(telegram_id: int):
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT o.id, o.title, o.status
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            WHERE c.telegram_id = $1
            ORDER BY o.created_at DESC
        """, telegram_id)


async def get_order_by_id(order_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
        return dict(row) if row else None


# Получить специалиста по разделу
async def get_specialist_by_section(section: str):
    async with pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT id, telegram_id FROM users
            WHERE role = 'специалист' AND section = $1
            LIMIT 1
        """, section)


async def update_order_status(order_id: int, status: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET status = $1 WHERE id = $2",
            status, order_id
        )


async def get_order_pending_fix_by_customer(customer_telegram_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT o.*
            FROM orders o
            JOIN users u ON o.customer_id = u.id
            WHERE u.telegram_id = $1 AND o.status = 'pending_correction'
            LIMIT 1
        """, customer_telegram_id)


async def update_task_status_by_id(task_id: int, new_status: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET status = $1
            WHERE id = $2
        """, new_status, task_id)


async def mark_order_section_done(order_id: int, section: str):
    # Например, section = "эом" → эом_status = 'done'
    section_field = f"{section}_status"

    async with pool.acquire() as conn:
        await conn.execute(f"""
            UPDATE orders
            SET {section_field} = 'done'
            WHERE id = $1
        """, order_id)



async def is_section_task_done(order_id: int, section: str):
    async with pool.acquire() as conn:
        result = await conn.fetchval("""
            SELECT status FROM tasks
            WHERE order_id = $1 AND section = $2
        """, order_id, section.upper())  # section хранится в верхнем регистре, как "КЖ", "ОВИК" и т.п.
        return result == "сделано"


async def are_all_sections_done(order_id: int):
    required_sections = ['овик', 'вк', 'гс', 'кж', 'эом', 'сс']
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT section, status FROM tasks
            WHERE order_id = $1
        """, order_id)

    done_sections = {row['section'].lower() for row in rows if row['status'].lower() == 'сделано'}
    return all(section in done_sections for section in required_sections)


async def add_bonus_or_penalty(user_id, order_id, type, description):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO bonuses_penalties (user_id, order_id, type, description)
            VALUES ($1, $2, $3, $4)
        """, user_id, order_id, type, description)

async def check_existing_penalty(user_id, order_id):
    async with pool.acquire() as conn:
        result = await conn.fetchval("""
            SELECT 1 FROM bonuses_penalties
            WHERE user_id=$1 AND order_id=$2 AND type='penalty'
        """, user_id, order_id)
        return bool(result)

async def get_user_bonuses_and_penalties(user_id):
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT type, description, order_id
            FROM bonuses_penalties
            WHERE user_id=$1
        """, user_id)
    
# database.py
async def get_user_profile(telegram_id):
    async with pool.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT full_name, iin AS iin, telegram_id, NULL AS phone, NULL AS email, role, section, registered_at
            FROM users
            WHERE telegram_id = $1
            UNION
            SELECT full_name, iin_or_bin AS iin, telegram_id, phone, email, 'customer' AS role, NULL AS section, registered_at
            FROM customers
            WHERE telegram_id = $1
            UNION
            SELECT full_name, NULL AS iin, telegram_id, NULL AS phone, NULL AS email, 'expert' AS role, NULL AS section, created_at AS registered_at
            FROM experts
            WHERE telegram_id = $1
        """, telegram_id)
        return user


async def get_all_users_sorted_by_id():
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT id, full_name FROM users ORDER BY id
        """)

async def update_user_field(user_id: int, field: str, value):
    allowed_fields = {"full_name", "iin", "phone", "role", "section"}
    if field not in allowed_fields:
        raise ValueError("Попытка изменить запрещённое поле.")
    async with pool.acquire() as conn:
        await conn.execute(f"""
            UPDATE users
            SET {field} = $1
            WHERE id = $2
        """, value, user_id)


async def get_all_users_sorted_by_id():
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT id, full_name FROM users ORDER BY id
        """)


async def move_user_to_experts(user_id):
    async with pool.acquire() as conn:
        # Получим данные пользователя
        user = await conn.fetchrow("SELECT telegram_id, full_name FROM users WHERE id = $1", user_id)
        if user:
            # Добавим в таблицу экспертов
            await conn.execute(
                "INSERT INTO experts (telegram_id, full_name) VALUES ($1, $2)",
                user["telegram_id"], user["full_name"]
            )
            # Удалим из users
            await conn.execute("DELETE FROM users WHERE id = $1", user_id)

async def archive_user_by_id(user_id):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET is_archived = TRUE, section = NULL WHERE id = $1",
            user_id
        )


async def get_all_users_sorted_by_id():
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT id, full_name, telegram_id, section, role
            FROM users
            WHERE is_archived = FALSE
            ORDER BY id
        """)

async def get_active_users_sorted_by_id():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users WHERE is_archived = FALSE ORDER BY id")

async def get_archived_users_sorted_by_id():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users WHERE is_archived = TRUE ORDER BY id")

async def restore_user(user_id):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_archived = FALSE WHERE id = $1", user_id)

async def get_my_customers():
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, full_name, iin_or_bin, telegram_id, phone, email, registered_at
            FROM customers
            ORDER BY id
        """)
        return [dict(row) for row in rows]


async def get_all_customers():
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM customers WHERE archived = FALSE ORDER BY id"
        )
        return [dict(r) for r in rows]

async def get_all_experts():
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, full_name
            FROM experts
            WHERE archived = FALSE
            ORDER BY id
        """)
        return [dict(r) for r in rows]

async def update_expert_field(expert_id, field, value):
    async with pool.acquire() as conn:
        await conn.execute(f"""
            UPDATE experts SET {field} = $1 WHERE id = $2
        """, value, expert_id)

async def delete_expert_by_id(expert_id):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM experts WHERE id = $1", expert_id)


async def update_customer_field(customer_id, field, value):
    async with pool.acquire() as conn:
        await conn.execute(f"""
            UPDATE customers SET {field} = $1 WHERE id = $2
        """, value, customer_id)


async def archive_expert_by_id(expert_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE experts SET archived = TRUE WHERE id = $1",
            expert_id
        )

async def restore_expert(expert_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE experts SET archived = FALSE WHERE id = $1",
            expert_id
        )

# database.py
async def get_archived_experts_sorted_by_id():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM experts WHERE archived = TRUE ORDER BY id")


# Получение всех архивированных заказчиков, отсортированных по ID
async def get_archived_customers_sorted_by_id():
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM customers WHERE archived = TRUE ORDER BY id"
        )
        return [dict(r) for r in rows]

# Архивирование заказчика по ID
async def archive_customer_by_id(customer_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE customers SET archived = TRUE WHERE id = $1",
            customer_id
        )

# Восстановление заказчика по ID
async def restore_customer(customer_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE customers SET archived = FALSE WHERE id = $1",
            customer_id
        )


async def update_order_document_url(order_id: int, new_path: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET document_url = $1 WHERE id = $2",
            new_path, order_id
        )

async def update_task_document_url(order_id: int, section: str, document_url: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET document_url = $1
            WHERE order_id = $2 AND section = $3
        """, document_url, order_id, section)

async def get_task_id_by_order_and_section(order_id: int, section: str) -> int | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id FROM tasks
            WHERE order_id = $1 AND section = $2
        """, order_id, section)
        return row["id"] if row else None


async def update_all_sections_status(order_id: int, new_status: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET status = $1
            WHERE order_id = $2
        """, new_status, order_id)


async def get_all_experts_i():
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, telegram_id, section
            FROM experts
            WHERE archived = false
        """)
        return [dict(r) for r in rows]


async def assign_task_to_expert(task_id: int, expert_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO expert_tasks (task_id, expert_id)
            VALUES ($1, $2)
        """, task_id, expert_id)


async def update_expert_task_status(expert_task_id: int, new_status: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE expert_tasks
            SET status = $1
            WHERE id = $2
        """, new_status, expert_task_id)


async def create_or_get_task(order_id: int, section: str, document_url: str) -> int:
    async with pool.acquire() as conn:
        # Проверка — существует ли уже задача
        row = await conn.fetchrow("""
            SELECT id FROM tasks
            WHERE order_id = $1 AND section = $2
        """, order_id, section)
        if row:
            return row["id"]

        # Иначе создаём новую
        row = await conn.fetchrow("""
            INSERT INTO tasks (order_id, section, document_url, status)
            VALUES ($1, $2, $3, 'Передано экспертам')
            RETURNING id
        """, order_id, section, document_url)
        return row["id"]


async def assign_task_to_expert(task_id: int, expert_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO expert_tasks (task_id, expert_id, status)
            VALUES ($1, $2, 'в работе')
            ON CONFLICT (task_id, expert_id)
            DO UPDATE SET status = 'в работе'
        """, task_id, expert_id)


async def get_task_by_id(task_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                et.id AS task_id,
                o.title AS order_title,
                o.description AS order_description,
                t.section,  -- Исправлено
                t.document_url,
                t.expert_note_url,
                t.status AS order_status,
                et.expert_id,
                t.order_id  -- order_id тоже из tasks
            FROM expert_tasks et
            JOIN tasks t ON t.id = et.task_id
            JOIN orders o ON o.id = t.order_id
            WHERE et.id = $1
        """, task_id)
        return dict(row) if row else None

async def update_expert_note_url(task_id: int, file_path: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE expert_tasks
            SET expert_note_url = $1
            WHERE task_id = $2
        """, file_path, task_id)


async def get_task_id_by_expert_task(expert_task_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT t.id AS task_id, t.section, t.document_url
            FROM expert_tasks et
            JOIN tasks t ON et.task_id = t.id
            WHERE et.id = $1
        """, expert_task_id)
        return dict(row) if row else None

async def update_expert_note_url(expert_task_id: int, url: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE expert_tasks
            SET expert_note_url = $1
            WHERE id = $2
        """, url, expert_task_id)


async def get_task_users(task_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                t.specialist_id AS section_user_id,
                o.gip_id,
                o.title AS order_title
            FROM tasks t
            JOIN orders o ON t.order_id = o.id
            WHERE t.id = $1
        """, task_id)

        return dict(row) if row else None

async def update_task_created_at_and_status(task_id: int):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tasks
            SET created_at = $1,
                status = 'Экспертиза'
            WHERE id = $2
        """, datetime.utcnow(), task_id)


async def update_expert_task_status(task_id: int, status: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE expert_tasks
            SET status = $1
            WHERE id = $2
        """, status, task_id)



async def get_task_by_id_ex(expert_task_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT t.id AS task_id, t.section, t.document_url
            FROM expert_tasks et
            JOIN tasks t ON et.task_id = t.id
            WHERE et.id = $1
        """, expert_task_id)
        return dict(row) if row else None


# Получить задачу и её данные по expert_task_id
async def get_task_by_expert_task_id(expert_task_id: int) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
        SELECT
            tasks.id AS task_id,
            tasks.section,
            tasks.status,
            expert_tasks.id AS expert_task_id
        FROM expert_tasks
        JOIN tasks ON expert_tasks.task_id = tasks.id
        WHERE expert_tasks.id = $1
    """, expert_task_id)
    return dict(row) if row else None


# Обновить статус в expert_tasks
async def approve_expert_task(expert_task_id: int, status: str):
    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE expert_tasks
        SET status = $2
        WHERE id = $1
    """, expert_task_id, status)


# Обновить статус в tasks
async def approve_task(task_id: int, status: str):
    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE tasks
        SET status = $2
        WHERE id = $1
    """, task_id, status)


# database.py

async def get_user_by_tg_id(tg_id: int) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, telegram_id, role, section, is_archived
            FROM users
            WHERE telegram_id = $1
        """, tg_id)
        return dict(row) if row else None


async def get_completed_orders():
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM orders
            WHERE status = 'completed'
            ORDER BY created_at DESC
        """)
        return [dict(row) for row in rows]
    

async def get_sections_by_order_id(order_id: int):
    async with pool.acquire() as conn:
        # Сначала пробуем получить только "Одобрено экспертом"
        approved_rows = await conn.fetch("""
            SELECT section, document_url
            FROM tasks
            WHERE order_id = $1
              AND status = 'Одобрено экспертом'
        """, order_id)

        if approved_rows:
            print(f"[DEBUG] Одобрено экспертом найдено: {approved_rows}")
            return [dict(row) for row in approved_rows]

        # Если таких нет — берём "Сделано"
        done_rows = await conn.fetch("""
            SELECT section, document_url
            FROM tasks
            WHERE order_id = $1
              AND status = 'Сделано'
        """, order_id)

        print(f"[DEBUG] Сделано найдено: {done_rows}")
        return [dict(row) for row in done_rows] if done_rows else []


async def get_estimate_task_document(order_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT document_url FROM tasks
            WHERE order_id = $1 AND section = 'смета'
        """, order_id)
        return row["document_url"] if row else None


async def get_order_document_url(order_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT document_url, id AS order_id
            FROM orders
            WHERE id = $1
        """, order_id)
        return dict(row) if row else None


# database.py
async def get_completed_tasks_by_specialist_id(specialist_id: int, section: str):
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT t.*, o.title, o.description 
            FROM tasks t
            JOIN orders o ON o.id = t.order_id
            WHERE t.specialist_id = $1
              AND t.section = $2
              AND t.status = 'completed'
            ORDER BY t.created_at DESC
        """, specialist_id, section)
        return [dict(row) for row in rows]
    
    
async def add_bonus_penalty(telegram_id: int, task_id: int, type: str, description: str):
    async with pool.acquire() as conn:
        async with conn.transaction():
            # ищем user_id по telegram_id
            row = await conn.fetchrow("""
                SELECT id FROM users WHERE telegram_id = $1
            """, telegram_id)

            if not row:
                raise ValueError(f"❌ User with telegram_id={telegram_id} not found in users")

            internal_user_id = row["id"]

            # вставляем бонус/штраф
            await conn.execute("""
                INSERT INTO bonuses_penalties (user_id, task_id, type, description)
                VALUES ($1, $2, $3, $4)
            """, internal_user_id, task_id, type, description)
