# clientbot/states/review_states.py
from aiogram.fsm.state import State, StatesGroup

class ReviewCorrectionFSM(StatesGroup):
    waiting_for_comment = State()
    waiting_for_fixed_file = State()
    waiting_for_customer_question = State()
    waiting_for_customer_zip = State()
    waiting_for_customer_error_comment = State()
