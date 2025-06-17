from aiogram.fsm.state import State, StatesGroup

class TaskCreateState(StatesGroup):
    choosing_section = State()
    choosing_executor = State()
    entering_deadline = State()
    entering_description = State()

class AssignCalculatorFSM(StatesGroup):
    waiting_for_description = State()
    waiting_for_deadline = State()

class AssignGenplanFSM(StatesGroup):
    waiting_for_description = State()
    waiting_for_deadline = State()

class ReviewGenplanCorrectionFSM(StatesGroup):
    waiting_for_comment = State()

class AssignARFSM(StatesGroup):
    waiting_for_deadline = State()
    waiting_for_description = State()