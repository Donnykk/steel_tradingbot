from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Literal, Dict
import datetime as dt

Side = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]
TimeInForce = Literal["GTC", "IOC", "FOK"]

@dataclass
class Bar:
    ts: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass
class Order:
    symbol: str
    side: Side
    type: OrderType
    qty: float
    price: Optional[float] = None
    tif: TimeInForce = "GTC"
    reduce_only: bool = False
    post_only: bool = False

@dataclass
class Fill:
    order_id: str
    ts: dt.datetime
    price: float
    qty: float
    fee: float
    maker: bool

@dataclass
class Position:
    symbol: str
    qty: float
    avg_price: float
    realized_pnl: float

class Strategy(ABC):
    @abstractmethod
    def warmup(self, bars: List[Bar]) -> None:
        ...

    @abstractmethod
    def on_bar(self, bar: Bar) -> Optional[Order]:
        ...

    def on_fill(self, fill: Fill) -> None:
        ...

class RiskManager(ABC):
    @abstractmethod
    def approve(self, order: Order, position: Position, account: Dict) -> bool:
        ...

class Broker(ABC):
    @abstractmethod
    def submit(self, order: Order) -> str:
        ...

    @abstractmethod
    def cancel(self, order_id: str) -> None:
        ...

    @abstractmethod
    def account(self) -> Dict:
        ...

