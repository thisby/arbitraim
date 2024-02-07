class Trade:
    exit_price = 0
    entry_price = 0
    MODE = 0
    color = "white"

    def __init__(self) -> None:
        print("Trade manager initialized")

    def getTradeLevel(self):
        if self.MODE == 0:
            return "light_green"
        elif self.MODE == 1:
            return "light_yellow"
        else:
            return "red"