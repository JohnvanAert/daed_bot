from aiogram.fsm.state import State, StatesGroup

class EditExpertFSM(StatesGroup):
    waiting_for_new_name = State()
    waiting_for_new_field_value = State()
