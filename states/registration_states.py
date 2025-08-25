from aiogram.fsm.state import State, StatesGroup

class RegisterState(StatesGroup):
    waiting_for_name = State()
    waiting_for_iin = State()
    waiting_for_address = State()
    waiting_for_bank = State()
    waiting_for_iban = State()
    waiting_for_bik = State()
    waiting_for_email = State()
    waiting_for_phone = State()

class ExpertRegistrationFSM(StatesGroup):
    waiting_for_name = State()

class RoleSelectionFSM(StatesGroup):
    choosing_role = State()
