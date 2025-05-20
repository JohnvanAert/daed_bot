from aiogram.fsm.state import State, StatesGroup

class AssignExecutor(StatesGroup):
    choosing_section = State()
    entering_executor_name = State()
    confirming_executor = State()
