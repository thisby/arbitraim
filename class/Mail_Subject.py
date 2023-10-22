#Mail_Subject.py
from enum import Enum

class Mail_Subject(Enum):
    BUY_VAR_DUMP = 1
    SELL_VAR_DUMP = 2
    BUY_VAR_PUMP = 3
    SELL_VAR_PUMP = 4
    NEGATIVE_GAIN = 5