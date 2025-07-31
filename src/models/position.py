# ==================== src/models/position.py ====================
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Position:
    """Enhanced position model with multi-strategy support"""
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
    
    def __init__(self, symbol: str, quantity: int, average_price: float, 
                 current_price: float, pnl: float, unrealized_pnl: float, 
                 instrument_key: str = ""):
        
        # Existing fields
        self.symbol = symbol
        self.quantity = quantity
        self.average_price = average_price
        self.current_price = current_price
        self.pnl = pnl
        self.unrealized_pnl = unrealized_pnl
        self.instrument_key = instrument_key
        
        # Enhanced fields for multi-strategy
        self.strategy_name = ""  # Which strategy created this position
        self.option_type = "CE"  # CE or PE
        self.strategy_mode = ""  # CE_ONLY, PE_ONLY, BIDIRECTIONAL
        self.entry_time = datetime.now()
        self.last_update = datetime.now()
        
        # Additional tracking
        self.max_profit = 0.0
        self.max_loss = 0.0
        self.trade_duration = 0  # in minutes