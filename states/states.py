from aiogram.fsm.state import State, StatesGroup

class AssignExecutor(StatesGroup):
    choosing_section = State()
    entering_executor_name = State()
    confirming_executor = State()

# states/states.py
class EditOrder(StatesGroup):
    waiting_for_comment = State()

class AssignKJFSM(StatesGroup):
    waiting_for_deadline = State()
    waiting_for_description = State()

# Состояния для создания заказа
class CreateOrder(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_document = State()

class FixOrder(StatesGroup):
    waiting_for_document = State()

# Состояния для регистрации заказчика
class RegisterCustomer(StatesGroup):
    waiting_for_full_name = State()
    waiting_for_iin_or_bin = State()
    waiting_for_phone = State()
    waiting_for_email = State()
