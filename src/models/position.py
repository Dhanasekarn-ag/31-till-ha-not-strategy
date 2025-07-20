# ==================== src/models/position.py ====================
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Position:
    """Position model"""
    symbol: str
    quantity: int
    average_price: float
    current_price: float
    pnl: float
    unrealized_pnl: float
    instrument_key: str
    entry_time: datetime = None
    
    def __post_init__(self):
        if self.entry_time is None:
            self.entry_time = datetime.now()
    
    @property
    def market_value(self) -> float:
        """Current market value of position"""
        return self.quantity * self.current_price
    
    @property
    def pnl_percentage(self) -> float:
        """PnL percentage"""
        if self.average_price == 0:
            return 0
        return (self.pnl / (self.quantity * self.average_price)) * 100