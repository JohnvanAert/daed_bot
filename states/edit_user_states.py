from aiogram.fsm.state import StatesGroup, State

class EditCustomerFSM(StatesGroup):
    waiting_for_new_value = State()
