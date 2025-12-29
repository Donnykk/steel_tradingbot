import uuid
from typing import Dict, List, Optional
from src.core.types import Broker, Order, Fill, Bar, Position

class SimulatedBroker(Broker):
    def __init__(self, initial_cash: float = 100000.0, maker_fee: float = 0.0002, taker_fee: float = 0.0005):
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.fills: List[Fill] = []
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee

    def submit(self, order: Order) -> str:
        order_id = str(uuid.uuid4())
        self.orders[order_id] = order
        return order_id

    def cancel(self, order_id: str) -> None:
        if order_id in self.orders:
            del self.orders[order_id]

    def account(self) -> Dict:
        return {
            "cash": self.cash,
            "positions": self.positions,
            "equity": self.get_total_equity()
        }

    def get_total_equity(self) -> float:
        equity = self.cash
        for pos in self.positions.values():
            equity += pos.qty * pos.avg_price 
        return equity

    def process_bar(self, bar: Bar, symbol: str) -> List[Fill]:
        new_fills = []
        for order_id in list(self.orders.keys()):
            order = self.orders[order_id]
            if order.symbol != symbol:
                continue
            
            fill = self._match(order, bar, order_id)
            if fill:
                self._apply_fill(fill, symbol)
                new_fills.append(fill)
                self.fills.append(fill)
                del self.orders[order_id]
        return new_fills

    def _match(self, order: Order, bar: Bar, order_id: str) -> Optional[Fill]:
        price = 0.0
        is_maker = False
        
        if order.type == "market":
            price = bar.close
            is_maker = False
        elif order.type == "limit":
            if order.side == "buy":
                if bar.low <= (order.price or bar.close):
                    # Optimistic fill for limit buy: if open < limit, fill at open, else limit
                    limit_price = order.price or bar.close
                    price = bar.open if bar.open < limit_price else limit_price
                    is_maker = True
                else:
                    return None
            else:
                if bar.high >= (order.price or bar.close):
                    limit_price = order.price or bar.close
                    price = bar.open if bar.open > limit_price else limit_price
                    is_maker = True
                else:
                    return None
        else:
            return None
            
        qty = order.qty if order.side == "buy" else -order.qty
        fee_rate = self.maker_fee if is_maker else self.taker_fee
        fee = price * abs(qty) * fee_rate
        
        return Fill(
            order_id=order_id,
            ts=bar.ts,
            price=price,
            qty=qty,
            fee=fee,
            maker=is_maker
        )

    def _apply_fill(self, fill: Fill, symbol: str):
        # Update cash
        cost = fill.qty * fill.price
        self.cash -= cost
        self.cash -= fill.fee
        
        # Update position
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol, qty=0.0, avg_price=0.0, realized_pnl=0.0)
            
        pos = self.positions[symbol]
        
        prev_qty = pos.qty
        prev_avg_price = pos.avg_price
        
        # Logic to update average price and realized PnL
        if pos.qty == 0.0:
            pos.qty = fill.qty
            pos.avg_price = fill.price
        elif (pos.qty > 0 and fill.qty > 0) or (pos.qty < 0 and fill.qty < 0):
            # Increasing position
            new_qty = pos.qty + fill.qty
            total_cost = (abs(pos.qty) * pos.avg_price) + (abs(fill.qty) * fill.price)
            pos.avg_price = total_cost / abs(new_qty)
            pos.qty = new_qty
        else:
            # Closing/Reducing position
            closing_qty = min(abs(pos.qty), abs(fill.qty))
            pnl_per_share = fill.price - pos.avg_price
            if pos.qty < 0: # Short position being closed
                pnl_per_share = pos.avg_price - fill.price
            
            pos.realized_pnl += closing_qty * pnl_per_share
            
            new_qty = pos.qty + fill.qty
            if new_qty == 0.0:
                pos.qty = 0.0
                pos.avg_price = 0.0
            else:
                # If we flipped position (e.g. long 1 to short 1)
                if (pos.qty > 0 and new_qty < 0) or (pos.qty < 0 and new_qty > 0):
                    pos.qty = new_qty
                    pos.avg_price = fill.price
                else:
                    pos.qty = new_qty
                    # Avg price stays same when reducing


