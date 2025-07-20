# ==================== src/models/order.py ====================
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from enum import Enum

class OrderStatus(Enum):
    PENDING = "pending"
    PLACED = "placed"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

class TransactionType(Enum):
    BUY = "BUY"
    SELL = "SELL"

@dataclass
class Order:
    """Order model"""
    symbol: str
    quantity: int
    price: float
    order_type: OrderType
    transaction_type: TransactionType
    status: OrderStatus = OrderStatus.PENDING
    order_id: Optional[str] = None
    instrument_key: Optional[str] = None
    timestamp: datetime = None
    filled_price: Optional[float] = None
    filled_quantity: Optional[int] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()