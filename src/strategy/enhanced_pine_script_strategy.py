# ==================== src/strategy/enhanced_pine_script_strategy.py ====================
from typing import Dict, Optional, List
import numpy as np
import pandas as pd
from src.strategy.base_strategy import BaseStrategy
from src.models.order import Order, OrderType, TransactionType
from src.models.position import Position
from datetime import datetime, time
from src.utils.position_sizing import PositionSizer

class EnhancedPineScriptStrategy(BaseStrategy):
    """
    Enhanced Pine Script Strategy supporting multiple trading modes:
    - CE_ONLY: Call options only (bullish)
    - PE_ONLY: Put options only (bearish) 
    - BIDIRECTIONAL: Both calls and puts
    """
    
    def __init__(self, name: str, params: Optional[Dict] = None):
        if params is None:
            params = {}
        super().__init__(name, params)
        
        # Strategy parameters
        self.adx_length = params.get('adx_length', 14)
        self.adx_threshold = params.get('adx_threshold', 20)
        self.strong_candle_threshold = params.get('strong_candle_threshold', 0.6)
        self.max_positions = params.get('max_positions', 1)
        self.risk_per_trade = params.get('risk_per_trade', 1000)
        
        # Trading mode configuration
        self.trading_mode = params.get('trading_mode', 'CE_ONLY')  # CE_ONLY, PE_ONLY, BIDIRECTIONAL
        self.strategy_id = params.get('strategy_id', name)
        
        # Position sizing
        total_capital = params.get('total_capital', 20000)
        max_risk_pct = params.get('max_risk_pct', 0.75)
        self.position_sizer = PositionSizer(total_capital, max_risk_pct)
        
        # Trading state
        self.in_ce_trade = False
        self.in_pe_trade = False
        
        # Data storage for calculations
        self.ha_candles_history: List[Dict] = []
        self.max_history = 50
        
        # Enhanced monitoring
        self.last_analysis_log = datetime.now()
        self.analysis_log_interval = 180  # Log detailed analysis every 3 minutes
        self.signal_attempts = 0
        self.last_signal_time = None
        
        self.logger.info(f"Initialized Enhanced PineScript Strategy: {name}")
        self.logger.info(f"Trading Mode: {self.trading_mode}")
        self.logger.info(f"Capital: Rs.{total_capital:,} | Max Risk: Rs.{total_capital * max_risk_pct:,.0f}")
    
    def add_ha_candle(self, ha_candle: Dict):
        """Add new Heikin Ashi candle to history"""
        self.ha_candles_history.append(ha_candle)
        
        # Keep only last max_history candles
        if len(self.ha_candles_history) > self.max_history:
            self.ha_candles_history = self.ha_candles_history[-self.max_history:]
        
        self.logger.debug(f"Added HA candle: O:{ha_candle.get('ha_open', 0):.2f} "
                         f"H:{ha_candle.get('ha_high', 0):.2f} L:{ha_candle.get('ha_low', 0):.2f} "
                         f"C:{ha_candle.get('ha_close', 0):.2f} | Total: {len(self.ha_candles_history)}")
    
    def calculate_trend_line(self, candles: List[Dict]) -> Optional[float]:
        """Calculate trend line: (EMA9 + SMA9) / 2"""
        if len(candles) < 9:
            return None
        
        # Extract close prices (using Heikin Ashi close)
        closes = [candle['ha_close'] for candle in candles]
        
        # Calculate EMA9
        ema9 = self.calculate_ema(closes, 9)
        
        # Calculate SMA9
        sma9 = self.calculate_sma(closes, 9)
        
        if ema9 is None or sma9 is None:
            return None
        
        # Trend line = (EMA9 + SMA9) / 2
        trend_line = (ema9 + sma9) / 2
        
        return trend_line
    
    def calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return None
        
        price_series = pd.Series(prices)
        ema = price_series.ewm(span=period, adjust=False).mean()
        
        return float(ema.iloc[-1]) if not pd.isna(ema.iloc[-1]) else None
    
    def calculate_sma(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return None
        
        return float(np.mean(prices[-period:]))
    
    def calculate_adx(self, candles: List[Dict]) -> tuple:
        """Calculate ADX, +DI, -DI"""
        if len(candles) < self.adx_length + 1:
            return None, None, None
        
        # Extract OHLC data (using Heikin Ashi values)
        highs = [candle['ha_high'] for candle in candles]
        lows = [candle['ha_low'] for candle in candles]
        closes = [candle['ha_close'] for candle in candles]
        
        # Calculate True Range and Directional Movement
        plus_dm = []
        minus_dm = []
        tr_values = []
        
        for i in range(1, len(candles)):
            curr_high = highs[i]
            curr_low = lows[i]
            curr_close = closes[i]
            prev_high = highs[i-1]
            prev_low = lows[i-1]
            prev_close = closes[i-1]
            
            # Up Move and Down Move
            up_move = curr_high - prev_high
            down_move = prev_low - curr_low
            
            # Plus DM and Minus DM
            plus_dm_val = up_move if up_move > 0 and up_move > down_move else 0
            minus_dm_val = down_move if down_move > 0 and down_move > up_move else 0
            
            plus_dm.append(plus_dm_val)
            minus_dm.append(minus_dm_val)
            
            # True Range
            tr1 = curr_high - curr_low
            tr2 = abs(curr_high - prev_close)
            tr3 = abs(curr_low - prev_close)
            tr = max(tr1, tr2, tr3)
            tr_values.append(tr)
        
        if len(tr_values) < self.adx_length:
            return None, None, None
        
        # Calculate smoothed values using RMA
        smooth_tr = self.calculate_rma(tr_values, self.adx_length)
        smooth_plus_dm = self.calculate_rma(plus_dm, self.adx_length)
        smooth_minus_dm = self.calculate_rma(minus_dm, self.adx_length)
        
        # Calculate +DI and -DI
        plus_di = 100 * smooth_plus_dm / smooth_tr if smooth_tr > 0 else 0
        minus_di = 100 * smooth_minus_dm / smooth_tr if smooth_tr > 0 else 0
        
        # Calculate DX
        di_sum = plus_di + minus_di
        dx = 100 * abs(plus_di - minus_di) / di_sum if di_sum > 0 else 0
        
        # Calculate ADX
        adx = dx
        
        return adx, plus_di, minus_di
    
    def calculate_rma(self, values: List[float], period: int) -> float:
        """Calculate RMA (Wilder's smoothing)"""
        if len(values) < period:
            return 0.0
        
        rma = float(np.mean(values[:period]))
        
        alpha = 1.0 / period
        for i in range(period, len(values)):
            rma = alpha * values[i] + (1 - alpha) * rma
        
        return float(rma)
    
    def analyze_candle_strength(self, ha_candle: Dict) -> tuple:
        """Analyze Heikin Ashi candle strength"""
        ha_open = ha_candle['ha_open']
        ha_close = ha_candle['ha_close']
        ha_high = ha_candle['ha_high']
        ha_low = ha_candle['ha_low']
        
        # Calculate body and candle range
        body = abs(ha_close - ha_open)
        candle_range = ha_high - ha_low
        
        # Body percentage
        body_pct = body / candle_range if candle_range > 0 else 0
        
        # Determine candle color
        is_green = ha_close > ha_open
        is_red = ha_close < ha_open
        
        # Strong candle conditions
        strong_green = is_green and body_pct > self.strong_candle_threshold
        strong_red = is_red and body_pct > self.strong_candle_threshold
        
        return strong_green, strong_red, body_pct
    
    async def should_enter(self, market_data: Dict) -> Optional[Order]:
        """Enhanced entry logic supporting multiple trading modes"""
        try:
            # Get Heikin Ashi candle data
            ha_candle = market_data.get('ha_candle')
            if not ha_candle:
                return None
            
            # Add to history
            self.add_ha_candle(ha_candle)
            
            # Need enough data for calculations
            if len(self.ha_candles_history) < self.adx_length + 1:
                current_time = datetime.now()
                if (current_time - self.last_analysis_log).total_seconds() > 60:
                    self.logger.info(f"🔄 {self.strategy_id} - Building data: {len(self.ha_candles_history)}/{self.adx_length + 1} HA candles")
                    self.last_analysis_log = current_time
                return None
            
            # Calculate trend line
            trend_line = self.calculate_trend_line(self.ha_candles_history)
            if trend_line is None:
                return None
            
            # Current price
            current_price = ha_candle['ha_close']
            
            # Market condition analysis
            price_above = current_price > trend_line
            price_below = current_price < trend_line
            price_diff = current_price - trend_line
            price_diff_pct = (price_diff / trend_line) * 100
            
            # Analyze candle strength
            strong_green, strong_red, body_pct = self.analyze_candle_strength(ha_candle)
            
            # Calculate ADX
            adx, plus_di, minus_di = self.calculate_adx(self.ha_candles_history)
            if adx is None:
                return None
            
            # Check trend strength
            trend_ok = adx > self.adx_threshold
            
            # Enhanced analysis logging
            current_time = datetime.now()
            if (current_time - self.last_analysis_log).total_seconds() > self.analysis_log_interval:
                self.logger.info(f"🎯 {self.strategy_id} Entry Analysis:")
                self.logger.info(f"   💰 Current Price: Rs.{current_price:.2f}")
                self.logger.info(f"   📈 Trend Line: Rs.{trend_line:.2f} (Diff: {price_diff:+.2f} | {price_diff_pct:+.2f}%)")
                self.logger.info(f"   🕯️ Candle: Green: {strong_green} ({body_pct:.1%}), Red: {strong_red}")
                self.logger.info(f"   📊 ADX: {adx:.2f} ({'✅' if trend_ok else '❌'} > {self.adx_threshold})")
                self.logger.info(f"   🎯 Mode: {self.trading_mode} | CE Trade: {self.in_ce_trade} | PE Trade: {self.in_pe_trade}")
                self.last_analysis_log = current_time
            
            # Trading logic based on mode
            if self.trading_mode == 'CE_ONLY':
                return await self._check_ce_entry(current_price, price_above, strong_green, trend_ok, market_data)
            
            elif self.trading_mode == 'PE_ONLY':
                return await self._check_pe_entry(current_price, price_below, strong_red, trend_ok, market_data)
            
            elif self.trading_mode == 'BIDIRECTIONAL':
                # Check CE entry first
                ce_order = await self._check_ce_entry(current_price, price_above, strong_green, trend_ok, market_data)
                if ce_order:
                    return ce_order
                
                # Then check PE entry
                pe_order = await self._check_pe_entry(current_price, price_below, strong_red, trend_ok, market_data)
                if pe_order:
                    return pe_order
            
            return None
            
        except Exception as e:
            await self.on_error(e)
            return None
    
    async def _check_ce_entry(self, current_price: float, price_above: bool, strong_green: bool, trend_ok: bool, market_data: Dict) -> Optional[Order]:
        """Check CE (Call) entry conditions"""
        # CE condition: price above trend + strong green + ADX > threshold + not in CE trade
        if price_above and strong_green and trend_ok and not self.in_ce_trade:
            
            # Smart position sizing
            lots, total_investment = self.position_sizer.calculate_position_size(current_price)
            
            if not self.position_sizer.is_trade_affordable(current_price):
                self.logger.warning(f"Cannot afford CE trade at Rs.{current_price:.2f}")
                return None
            
            # Enhanced entry logging
            self.logger.info(f"🚀 {self.strategy_id} - CE BUY SIGNAL TRIGGERED!")
            self.logger.info(f"   💰 Price: Rs.{current_price:.2f} | Strong Green: {strong_green}")
            self.logger.info(f"   🎯 Position: {lots} lots | Investment: Rs.{total_investment:,.2f}")
            
            # Set trade state
            self.in_ce_trade = True
            self.last_signal_time = datetime.now()
            
            return Order(
                symbol=str(market_data.get('symbol', 'NIFTY')),
                quantity=lots,
                price=current_price,
                order_type=OrderType.MARKET,
                transaction_type=TransactionType.BUY,
                instrument_key=str(market_data.get('instrument_key', '')),
                option_type='CE',
                strategy_name=self.strategy_id,
                strategy_mode='CE'
            )
        
        return None
    
    async def _check_pe_entry(self, current_price: float, price_below: bool, strong_red: bool, trend_ok: bool, market_data: Dict) -> Optional[Order]:
        """Check PE (Put) entry conditions"""
        # PE condition: price below trend + strong red + ADX > threshold + not in PE trade
        if price_below and strong_red and trend_ok and not self.in_pe_trade:
            
            # Smart position sizing
            lots, total_investment = self.position_sizer.calculate_position_size(current_price)
            
            if not self.position_sizer.is_trade_affordable(current_price):
                self.logger.warning(f"Cannot afford PE trade at Rs.{current_price:.2f}")
                return None
            
            # Enhanced entry logging
            self.logger.info(f"🛑 {self.strategy_id} - PE BUY SIGNAL TRIGGERED!")
            self.logger.info(f"   💰 Price: Rs.{current_price:.2f} | Strong Red: {strong_red}")
            self.logger.info(f"   🎯 Position: {lots} lots | Investment: Rs.{total_investment:,.2f}")
            
            # Set trade state
            self.in_pe_trade = True
            self.last_signal_time = datetime.now()
            
            return Order(
                symbol=str(market_data.get('symbol', 'NIFTY')),
                quantity=lots,
                price=current_price,
                order_type=OrderType.MARKET,
                transaction_type=TransactionType.BUY,
                instrument_key=str(market_data.get('instrument_key', '')),
                option_type='PE',
                strategy_name=self.strategy_id,
                strategy_mode='PE'
            )
        
        return None
    
    async def should_exit(self, position: Position, market_data: Dict) -> Optional[Order]:
        """Enhanced exit logic for both CE and PE positions"""
        try:
            # Get Heikin Ashi candle data
            ha_candle = market_data.get('ha_candle')
            if not ha_candle:
                return None
            
            # Calculate trend line
            trend_line = self.calculate_trend_line(self.ha_candles_history)
            if trend_line is None:
                return None
            
            # Current price
            current_price = ha_candle['ha_close']
            
            # Market conditions
            price_above = current_price > trend_line
            price_below = current_price < trend_line
            
            # Analyze candle strength
            strong_green, strong_red, body_pct = self.analyze_candle_strength(ha_candle)
            
            # Get position details
            option_type = getattr(position, 'option_type', 'CE')
            
            # CE Exit Logic
            if option_type == 'CE':
                exit_condition = price_below or strong_red
                
                if exit_condition:
                    self.logger.info(f"📉 {self.strategy_id} - CE EXIT SIGNAL!")
                    self.logger.info(f"   💰 Price: Rs.{current_price:.2f} | Reason: {'Price below trend' if price_below else 'Strong red candle'}")
                    
                    self.in_ce_trade = False
                    
                    return Order(
                        symbol=position.symbol,
                        quantity=position.quantity,
                        price=current_price,
                        order_type=OrderType.MARKET,
                        transaction_type=TransactionType.SELL,
                        instrument_key=position.instrument_key,
                        option_type='CE',
                        strategy_name=self.strategy_id,
                        strategy_mode='CE'
                    )
            
            # PE Exit Logic
            elif option_type == 'PE':
                exit_condition = price_above or strong_green
                
                if exit_condition:
                    self.logger.info(f"📈 {self.strategy_id} - PE EXIT SIGNAL!")
                    self.logger.info(f"   💰 Price: Rs.{current_price:.2f} | Reason: {'Price above trend' if price_above else 'Strong green candle'}")
                    
                    self.in_pe_trade = False
                    
                    return Order(
                        symbol=position.symbol,
                        quantity=position.quantity,
                        price=current_price,
                        order_type=OrderType.MARKET,
                        transaction_type=TransactionType.SELL,
                        instrument_key=position.instrument_key,
                        option_type='PE',
                        strategy_name=self.strategy_id,
                        strategy_mode='PE'
                    )
            
            return None
            
        except Exception as e:
            await self.on_error(e)
            return None
    
    async def on_order_filled(self, order: Order):
        """Enhanced order fill handling"""
        await super().on_order_filled(order)
        
        # Log strategy-specific information
        option_type = getattr(order, 'option_type', 'CE')
        strategy_mode = getattr(order, 'strategy_mode', self.trading_mode)
        
        if order.transaction_type == TransactionType.BUY:
            self.logger.info(f"📈 {self.strategy_id} - {option_type} ENTRY FILLED @ Rs.{order.filled_price}")
        else:
            self.logger.info(f"📉 {self.strategy_id} - {option_type} EXIT FILLED @ Rs.{order.filled_price}")
    
    @property
    def in_trade(self) -> bool:
        """Check if strategy is in any trade"""
        return self.in_ce_trade or self.in_pe_trade
    
    async def on_error(self, error: Exception):
        """Enhanced error handling"""
        self.logger.error(f"{self.strategy_id} Strategy Error: {error}")
        await super().on_error(error)