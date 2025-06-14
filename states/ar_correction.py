from aiogram.fsm.state import StatesGroup, State

class ReviewArCorrectionFSM(StatesGroup):
    waiting_for_comment = State()
