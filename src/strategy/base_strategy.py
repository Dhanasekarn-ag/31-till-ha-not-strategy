# ==================== src/strategy/base_strategy.py (FIXED) ====================
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import logging
from src.models.order import Order, OrderType, TransactionType
from src.models.position import Position

class BaseStrategy(ABC):
    """Base strategy class"""
    
    def __init__(self, name: str, params: Optional[Dict] = None):  # FIX: Optional[Dict] instead of Dict = None
        self.name = name
        self.params = params or {}
        self.logger = logging.getLogger(f'trading.strategy.{name}')
        self.positions: Dict[str, Position] = {}
        self.orders: List[Order] = []
        self.is_active = True
        
    @abstractmethod
    async def should_enter(self, market_data: Dict) -> Optional[Order]:
        """
        Determine if should enter a trade
        
        Args:
            market_data: Current market data
            
        Returns:
            Order object if should enter, None otherwise
        """
        pass
    
    @abstractmethod
    async def should_exit(self, position: Position, market_data: Dict) -> Optional[Order]:
        """
        Determine if should exit a position
        
        Args:
            position: Current position
            market_data: Current market data
            
        Returns:
            Order object if should exit, None otherwise
        """
        pass
    
    async def on_order_filled(self, order: Order):
        """Called when an order is filled"""
        self.logger.info(f"Order filled: {order.symbol} {order.transaction_type.value} {order.quantity} @ {order.filled_price}")
    
    async def on_error(self, error: Exception):
        """Called when an error occurs"""
        self.logger.error(f"Strategy error: {error}")
        
    async def calculate_position_size(self, price: float, risk_amount: float) -> int:
        """Calculate position size based on risk"""
        # Simple position sizing - can be enhanced
        if price <= 0:
            return 0
        return max(1, int(risk_amount / price))