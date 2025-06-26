from aiogram.fsm.state import State, StatesGroup

class RegisterState(StatesGroup):
    waiting_for_name = State()
    waiting_for_iin = State()

class ExpertRegistrationFSM(StatesGroup):
    waiting_for_name = State()

class RoleSelectionFSM(StatesGroup):
    choosing_role = State()
