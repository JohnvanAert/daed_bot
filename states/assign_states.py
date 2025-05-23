from aiogram.fsm.state import State, StatesGroup

class AssignSpecialist(StatesGroup):
    choosing_order = State()
    choosing_section = State()
    entering_specialist_name = State()
    confirming_specialist = State()
