from typing import Dict
from src.core.types import Broker, Order

class NoopBroker(Broker):
    def __init__(self):
        self._account = {}

    def submit(self, order: Order) -> str:
        return "noop"

    def cancel(self, order_id: str) -> None:
        return None

    def account(self) -> Dict:
        return self._account

