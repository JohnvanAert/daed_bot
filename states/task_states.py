from aiogram.fsm.state import State, StatesGroup

class TaskCreateState(StatesGroup):
    choosing_section = State()
    choosing_executor = State()
    entering_deadline = State()
    entering_description = State()

class AssignCalculatorFSM(StatesGroup):
    waiting_for_description = State()
    waiting_for_deadline = State()
    waiting_for_price = State()

class AssignGenplanFSM(StatesGroup):
    waiting_for_description = State()
    waiting_for_deadline = State()
    waiting_for_price = State()
class ReviewGenplanCorrectionFSM(StatesGroup):
    waiting_for_comment = State()

class AssignARFSM(StatesGroup):
    waiting_for_deadline = State()
    waiting_for_description = State()
    waiting_for_price = State()

class AssignKJFSM(StatesGroup):
    waiting_for_deadline = State()
    waiting_for_description = State()
    waiting_for_price = State()

class ReviewKjCorrectionFSM(StatesGroup):
    waiting_for_comment = State()

class AssignOVIKFSM(StatesGroup):
    waiting_for_deadline = State()
    waiting_for_description = State()
    waiting_for_price = State()
class ReviewOvikCorrectionFSM(StatesGroup):
    waiting_for_comment = State()
    waiting_for_description = State()

class AssignGSFSM(StatesGroup):
    waiting_for_deadline = State()
    waiting_for_description = State()
    waiting_for_price = State()
class ReviewGSCorrectionFSM(StatesGroup):
    waiting_for_comment = State()

class AssignVKFSM(StatesGroup):
    waiting_for_deadline = State()
    waiting_for_description = State()
    waiting_for_price = State()
class ReviewVkCorrectionFSM(StatesGroup):
    waiting_for_comment = State()

class SubmitKjFSM(StatesGroup):
    waiting_for_file = State()

class AssignEOMFSM(StatesGroup):
    waiting_for_deadline = State()
    waiting_for_description = State()
    waiting_for_price = State()

class ReviewEomCorrectionFSM(StatesGroup):
    waiting_for_comment = State()

class AssignSSFSM(StatesGroup):
    waiting_for_deadline = State()
    waiting_for_description = State()
    waiting_for_price = State()
class ReviewSSCorrectionFSM(StatesGroup):
    waiting_for_comment = State()
