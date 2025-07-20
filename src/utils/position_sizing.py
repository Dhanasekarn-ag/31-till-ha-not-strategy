# ==================== src/utils/position_sizing.py ====================
from typing import Tuple
import logging

class PositionSizer:
    """Smart position sizing for limited capital"""
    
    def __init__(self, total_capital: float = 20000, max_risk_pct: float = 0.75):
        self.total_capital = total_capital
        self.max_risk_amount = total_capital * max_risk_pct
        self.logger = logging.getLogger(__name__)
    
    def calculate_position_size(self, option_price: float, lot_size: int = 75) -> Tuple[int, float]:
        """
        Calculate safe position size based on available capital
        
        Args:
            option_price: Current option price per share
            lot_size: Number of shares per lot (NIFTY = 75)
            
        Returns:
            (lots, total_investment)
        """
        
        # Calculate cost per lot
        cost_per_lot = option_price * lot_size
        
        # Calculate maximum affordable lots
        max_affordable_lots = int(self.max_risk_amount / cost_per_lot)
        
        # Ensure at least 1 lot (minimum trade)
        lots = max(1, max_affordable_lots)
        
        # Calculate actual investment
        total_investment = lots * cost_per_lot
        
        # Safety check - don't exceed capital
        if total_investment > self.total_capital:
            lots = int(self.total_capital / cost_per_lot)
            total_investment = lots * cost_per_lot
        
        self.logger.info(f"Position Sizing: {lots} lots × ₹{option_price:.2f} = ₹{total_investment:,.2f}")
        
        return lots, total_investment
    
    def is_trade_affordable(self, option_price: float, lot_size: int = 75) -> bool:
        """Check if we can afford at least 1 lot"""
        min_cost = option_price * lot_size
        return min_cost <= self.total_capital