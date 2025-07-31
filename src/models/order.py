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
            
    def __init__(self, symbol: str, quantity: int, price: float, order_type: OrderType, 
                 transaction_type: TransactionType, instrument_key: str = "",
                 option_type: str = "CE", strategy_name: str = "", strategy_mode: str = ""):
    # Existing fields
        self.symbol = symbol
        self.quantity = quantity
        self.price = price
        self.order_type = order_type
        self.transaction_type = transaction_type
        self.instrument_key = instrument_key
        
        # Enhanced fields for multi-strategy
        self.option_type = option_type  # CE, PE
        self.strategy_name = strategy_name  # Strategy identifier
        self.strategy_mode = strategy_mode  # CE_ONLY, PE_ONLY, BIDIRECTIONAL
        
        # Order status fields
        self.order_id = ""
        self.status = OrderStatus.PENDING
        self.filled_price = 0.0
        self.filled_quantity = 0
        self.timestamp = datetime.now()
        
        # Additional tracking
        self.error_message = ""
        self.broker_order_id = ""
        