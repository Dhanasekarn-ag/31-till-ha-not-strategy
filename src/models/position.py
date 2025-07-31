from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Position:
    symbol: str
    quantity: int
    average_price: float
    current_price: float
    pnl: float
    unrealized_pnl: float
    instrument_key: str = ""
    
    # Strategy-specific attributes
    strategy_name: Optional[str] = None
    option_type: Optional[str] = None  # 'CE' or 'PE'
    strategy_mode: Optional[str] = None
    entry_time: Optional[datetime] = None
    
    def __post_init__(self):
        if self.entry_time is None:
            self.entry_time = datetime.now()