from typing import Dict
from src.core.types import RiskManager, Order, Position

class BasicRisk(RiskManager):
    def __init__(self, max_order_qty: float = 5.0, max_position_qty: float = 10.0):
        self.max_order_qty = max_order_qty
        self.max_position_qty = max_position_qty

    def approve(self, order: Order, position: Position, account: Dict) -> bool:
        if order.qty <= 0:
            return False
        if order.qty > self.max_order_qty:
            return False
        new_qty = position.qty + (order.qty if order.side == "buy" else -order.qty)
        if abs(new_qty) > self.max_position_qty:
            return False
        return True

