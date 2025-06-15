from aiogram.fsm.state import StatesGroup, State

class ReviewCalcCorrectionFSM(StatesGroup):
    waiting_for_comment = State()
