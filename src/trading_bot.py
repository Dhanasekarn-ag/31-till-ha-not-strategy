# ==================== src/trading_bot.py (COMPLETELY FIXED) ====================
import asyncio
import logging
from datetime import datetime, time
from typing import Dict, List, Optional
from config.settings import Settings
from src.upstox_client import UpstoxClient
from src.utils.notification import TelegramNotifier
from src.strategy.base_strategy import BaseStrategy
from src.models.order import Order, OrderStatus, OrderType, TransactionType
from src.models.position import Position
from src.utils.market_utils import MarketUtils

# Import websocket manager
try:
    from src.websocket.websocket_manager import WebSocketManager
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
class TradingBot:
    """Enhanced trading bot with comprehensive monitoring and auto-reconnection"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.trading_logger = logging.getLogger('trading')
        
        # Initialize clients
        self.upstox_client = UpstoxClient(
            settings.upstox_api_key,
            settings.upstox_api_secret,
            settings.upstox_redirect_uri
        )
        
        self.notifier = TelegramNotifier(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
            settings.enable_notifications
        )
        
        # Initialize WebSocket Manager
        self.websocket_manager: Optional[WebSocketManager] = None
        self.websocket_enabled = WEBSOCKET_AVAILABLE
        
        # Trading state
        self.strategies: List[BaseStrategy] = []
        self.positions: Dict[str, Position] = {}
        self.orders: List[Order] = []
        self.is_running = False
        self.paper_trading = settings.paper_trading
        
        # Real-time data
        self.latest_ticks: Dict[str, Dict] = {}
        self.latest_candles: Dict[str, Dict] = {}
        self.latest_ha_candles: Dict[str, Dict] = {}
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        self.best_trade = 0.0
        self.worst_trade = 0.0
        self.session_start_time = datetime.now()
        
        # Enhanced monitoring - Fixed initialization
        self.last_price_update = datetime.now()  # Initialize to current time
        self.last_websocket_check = datetime.now()
        self.websocket_reconnect_attempts = 0
        self.last_signal_analysis_log = datetime.now()
        self.last_telegram_update = datetime.now()
        self.price_log_interval = 30  # Log price every 30 seconds
        self.signal_analysis_interval = 180  # Detailed analysis every 3 minutes
        self.telegram_update_interval = 3600  # Telegram update every hour
        
        # Default instruments to subscribe
        self.default_instruments = [
            'NSE_INDEX|Nifty 50',
            'NSE_INDEX|Nifty Bank', 
            'BSE_INDEX|SENSEX'
        ]
        
    async def on_ha_candle_received(self, ha_candle: Dict):
        """🚨 CLEAN VERSION: Process new Heikin Ashi candle for strategy analysis"""
        try:
            # 1. BASIC VALIDATION
            symbol = ha_candle.get('symbol', 'UNKNOWN')
            if not symbol or symbol == 'UNKNOWN':
                self.logger.warning("Received HA candle with unknown symbol")
                return
        
            # 2. LOG THE NEW CANDLE
            self.logger.info(f"NEW HA CANDLE - {symbol}: O:{ha_candle.get('ha_open', 0):.2f} H:{ha_candle.get('ha_high', 0):.2f} L:{ha_candle.get('ha_low', 0):.2f} C:{ha_candle.get('ha_close', 0):.2f}")
        
            # 3. GET CANDLE HISTORY (simplified logic)
            ha_candles = ha_candle.get('candle_history', [])
        
            # Fallback: get from websocket manager if not in candle
            if not ha_candles and self.websocket_manager:
                if hasattr(self.websocket_manager, 'persistent_ha_candles'):
                    ha_candles = self.websocket_manager.persistent_ha_candles.get(symbol, [])
                elif hasattr(self.websocket_manager, 'latest_ha_candles'):
                    ha_candles = self.websocket_manager.latest_ha_candles.get(symbol, [])
        
            candle_count = len(ha_candles)
        
            # 4. CHECK IF WE HAVE ENOUGH CANDLES
            if candle_count < 15:
                self.logger.info(f"Progress: {symbol} has {candle_count}/15 candles | Need {15-candle_count} more")
                return
        
            # 5. 🚀 WE HAVE ENOUGH CANDLES - EXECUTE STRATEGIES!
            self.logger.info(f"STRATEGY READY - {symbol} has {candle_count} candles - EXECUTING ANALYSIS...")
        
            # 6. CALL THE SEPARATE STRATEGY EXECUTION METHOD
            await self._execute_strategies_on_ha_candle(symbol, ha_candle, ha_candles)
        
        except Exception as e:
            self.logger.error(f"Error processing HA candle: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        
    async def _execute_strategies_on_ha_candle(self, symbol: str, ha_candle: Dict, ha_candles: List[Dict]):
        """🚨 SEPARATED: Execute all strategies when HA candle is received"""  
        try:
            self.logger.info(f"EXECUTING STRATEGIES for {symbol}")
        
            # Prepare comprehensive market data
            market_data = {
                'symbol': symbol,
                'ha_candle': ha_candle,
                'ha_candles_history': ha_candles,
                'instrument_key': 'NSE_INDEX|Nifty 50',
                'current_price': ha_candle.get('ha_close', 0),
                'timestamp': datetime.now(),
                # Add compatibility fields
                'price': ha_candle.get('ha_close', 0),
                'high': ha_candle.get('ha_high', 0),
                'low': ha_candle.get('ha_low', 0),
                'volume': ha_candle.get('volume', 0),
                'open': ha_candle.get('ha_open', 0),
                'close': ha_candle.get('ha_close', 0)
            }
        
            self.logger.info(f" Market Data: Price={market_data['current_price']:.2f}, Candles={len(ha_candles)}")
        
            # Process each strategy
            strategy_count = len(self.strategies)
            self.logger.info(f" Processing {strategy_count} strategies...")
        
            for i, strategy in enumerate(self.strategies):
                if not strategy.is_active:
                    self.logger.warning(f" Strategy {i+1}/{strategy_count} ({strategy.name}) is INACTIVE")
                    continue
                
                try:
                    self.logger.info(f" Analyzing strategy {i+1}/{strategy_count}: {strategy.name}")
                
                    # 🚨 ENTRY SIGNAL CHECK 🚨
                    entry_order = await strategy.should_enter(market_data)
                    if entry_order:
                        option_type = getattr(entry_order, 'option_type', 'CE')
                        self.logger.info(f" *** ENTRY SIGNAL *** {option_type} from {strategy.name}")
                        self.logger.info(f"    Price: Rs.{entry_order.price:.2f} | Quantity: {entry_order.quantity}")
                    
                        # Place order
                        if await self.place_order(entry_order):
                            self.orders.append(entry_order)
                            await strategy.on_order_filled(entry_order)
                            await self.send_trade_notification(entry_order, "ENTRY")
                            self.logger.info(f"Entry order executed successfully")
                        else:
                            self.logger.error(f"Failed to place entry order")
                    else:
                        self.logger.info(f"No entry signal from {strategy.name}")
                
                    # 🚨 EXIT SIGNAL CHECK 🚨
                    positions_for_symbol = [pos for pos in self.positions.values() if pos.symbol == symbol]
                
                    if positions_for_symbol:
                        self.logger.info(f"Checking {len(positions_for_symbol)} positions for exit...")
                    
                        for j, position in enumerate(positions_for_symbol):
                            exit_order = await strategy.should_exit(position, market_data)
                            if exit_order:
                                option_type = getattr(exit_order, 'option_type', 'CE')
                                self.logger.info(f"*** EXIT SIGNAL *** {option_type} from {strategy.name}")
                            
                                if await self.place_order(exit_order):
                                    self.orders.append(exit_order)
                                    await strategy.on_order_filled(exit_order)
                                    await self.send_trade_notification(exit_order, "EXIT")
                                
                                    # Remove position if fully closed
                                    position_key = f"{position.symbol}_{position.instrument_key}"
                                    if position_key in self.positions:
                                        if exit_order.quantity >= position.quantity:
                                            del self.positions[position_key]
                                            self.logger.info(f"Position fully closed: {position_key}")
                            else:
                                self.logger.info(f"No exit signal for position {j+1}")
                    else:
                        self.logger.debug(f"No positions to check for {symbol}")
                
                except Exception as strategy_error:
                    self.logger.error(f"Error in strategy {strategy.name}: {strategy_error}")
                    import traceback
                    self.logger.error(f"Strategy error details: {traceback.format_exc()}")
        
            self.logger.info(f"Strategy execution completed for {symbol}")
                
        except Exception as e:
            self.logger.error(f"Critical error executing strategies: {e}")
            import traceback
            self.logger.error(f"Critical error details: {traceback.format_exc()}")
    
        
            
    def add_strategy(self, strategy: BaseStrategy):
        """Add a trading strategy"""
        self.strategies.append(strategy)
        self.logger.info(f"Added strategy: {strategy.name}")
    
    def is_market_open(self) -> bool:
        """Check if market is open"""
        return MarketUtils.is_market_open()
    
    async def setup_websockets(self):
        """Setup websocket connections for real-time data"""
        if not self.websocket_enabled:
            self.logger.warning("WebSocket not available. Install upstox-python-sdk for real-time data.")
            return False
            
        if not self.upstox_client.access_token:
            self.logger.error("No access token available for websocket connection")
            return False
            
        try:
            # Initialize WebSocket Manager
            self.websocket_manager = WebSocketManager(
                api_key=self.settings.upstox_api_key,
                access_token=self.upstox_client.access_token
            )
            
            # Set up callbacks with enhanced error handling
            self.websocket_manager.set_callbacks(
            on_tick=None,  # Disabled to reduce noise
            on_candle=None,  # Disabled to reduce noise
            on_ha_candle=self.on_ha_candle_received,  # ← CRITICAL FIX
            on_order_update=self.on_order_update_received,
            on_error=self.on_websocket_error
            )
            
            # Subscribe to default instruments
            self.websocket_manager.subscribe_instruments(self.default_instruments)
            
            # Start websocket streams
            self.websocket_manager.start_all_streams()
            
            self.logger.info("WebSocket connections established successfully")
            await self.notifier.send_status_update("WebSocket Connected", "Real-time data streaming active")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup websockets: {e}")
            await self.notifier.send_error_alert(f" WebSocket setup failed: {str(e)}")
            return False
    
    def setup_websocket_callbacks(self):
        """Setup WebSocket event callbacks"""
        self.websocket_manager.set_callbacks(
            on_tick=None,  # Disable to reduce noise
            on_candle=None,  # Disable to reduce noise
            on_ha_candle=self.on_ha_candle_received,  # ← ENABLE THIS
            on_order_update=self.on_order_update_received,
            on_error=self.on_websocket_error
        )
        self.logger.info("WebSocket callbacks configured for HA candle processing")


    async def on_tick_received(self, tick_data: Dict):
        """Enhanced tick handler with timestamp and monitoring"""
        try:
            instrument_key = tick_data.get('instrument_key', '')
            symbol = self._extract_symbol_from_key(instrument_key)
            
            # Add timestamp for monitoring
            tick_data['timestamp'] = datetime.now()
            tick_data['price'] = tick_data.get('ltp', 0)
            
            # Store latest tick
            self.latest_ticks[symbol] = tick_data
            
            # Log tick (debug level to avoid spam)
            self.logger.debug(f"Tick {symbol}: Rs.{tick_data.get('ltp', 0):.2f}")
            
        except Exception as e:
            self.logger.error(f"Error processing tick data: {e}")
    
    async def on_candle_completed(self, candle_data: Dict):
        """Handle completed candle"""
        try:
            symbol = candle_data.get('symbol', '')
            
            # Store latest candle
            self.latest_candles[symbol] = candle_data
            
            self.trading_logger.info(
                f"3min Candle {symbol}: O:{candle_data['open']:.2f} H:{candle_data['high']:.2f} "
                f"L:{candle_data['low']:.2f} C:{candle_data['close']:.2f} V:{candle_data['volume']}"
            )
            
        except Exception as e:
            self.logger.error(f"Error processing candle data: {e}")
    
    async def on_ha_candle_completed(self, ha_candle_data: Dict):
        """Handle completed Heikin Ashi candle - KEY FOR STRATEGY"""
        try:
            symbol = ha_candle_data.get('symbol', '')
            
            # Store latest HA candle
            self.latest_ha_candles[symbol] = ha_candle_data
            
            self.trading_logger.info(
                f"HA Candle {symbol}: O:{ha_candle_data['ha_open']:.2f} H:{ha_candle_data['ha_high']:.2f} "
                f"L:{ha_candle_data['ha_low']:.2f} C:{ha_candle_data['ha_close']:.2f}"
            )
            
            # Trigger strategy evaluation on new HA candle
            await self.evaluate_strategies_on_new_candle(symbol, ha_candle_data)
            
        except Exception as e:
            self.logger.error(f"Error processing HA candle data: {e}")
    
    async def on_order_update_received(self, order_update: Dict):
        """Handle order status updates"""
        try:
            self.trading_logger.info(f"Order update: {order_update}")
        except Exception as e:
            self.logger.error(f"Error processing order update: {e}")
    
    async def on_websocket_error(self, error_message: str):
        """Enhanced WebSocket error handler with history preservation"""
        try:
            self.logger.error(f"WebSocket Error: {error_message}")
        
            # SAVE CANDLE HISTORY BEFORE ANY RECONNECTION
            saved_candles = {}
            saved_ha_candles = {}
        
            if self.websocket_manager:
                for symbol in ['NIFTY', 'BANKNIFTY', 'SENSEX']:
                    saved_candles[symbol] = self.websocket_manager.get_latest_candles(symbol, 100)
                    saved_ha_candles[symbol] = self.websocket_manager.get_latest_ha_candles(symbol, 100)
        
            # Send immediate Telegram alert
            await self.notifier.send_error_alert(f"🚨 WebSocket Error: {error_message}")
        
            # Attempt automatic reconnection
            self.logger.info("Attempting automatic WebSocket reconnection...")
            self.websocket_reconnect_attempts += 1
        
            # Small delay before reconnection attempt
            await asyncio.sleep(5)
        
            reconnect_success = await self.setup_websockets()
        
            if reconnect_success and saved_ha_candles:
                # Restore candle history
                for symbol, candles in saved_candles.items():
                    if candles and symbol in saved_ha_candles:
                        self.websocket_manager.restore_candle_history(
                            symbol, 
                            candles, 
                            saved_ha_candles[symbol]
                        )
            
                await self.notifier.send_status_update("Auto-Reconnected", 
                    f"✅ WebSocket reconnected with history preserved!")
                self.websocket_reconnect_attempts = 0
            else:
                await self.notifier.send_error_alert(
                    f"❌ Auto-reconnection failed. Manual restart may be required.")
            
        except Exception as e:
            self.logger.error(f"Error handling WebSocket error: {e}")
    
    async def check_websocket_health(self):
        """Monitor WebSocket health and auto-reconnect if needed"""
        try:
            current_time = datetime.now()
        
            # Check every 5 minutes
            if (current_time - self.last_websocket_check).total_seconds() < 300:
                return
            
            self.last_websocket_check = current_time
        
            if not self.websocket_manager:
                return
        
            # Check if we have recent data (within 2 minutes)
            data_age_limit = 120
            recent_data = False
        
            for symbol, tick_data in self.latest_ticks.items():
                if 'timestamp' in tick_data:
                    data_age = (current_time - tick_data['timestamp']).total_seconds()
                    if data_age < data_age_limit:
                        recent_data = True
                        break
        
            # If no recent data during market hours, attempt reconnection
            if not recent_data and self.is_market_open():
                self.logger.warning("No recent WebSocket data detected during market hours")
            
                # SAVE CANDLE HISTORY BEFORE RECONNECTION
                saved_candles = {}
                saved_ha_candles = {}
            
            if self.websocket_manager:
                for symbol in ['NIFTY', 'BANKNIFTY', 'SENSEX']:
                    saved_candles[symbol] = self.websocket_manager.get_latest_candles(symbol, 100)
                    saved_ha_candles[symbol] = self.websocket_manager.get_latest_ha_candles(symbol, 100)
                    
                    if saved_ha_candles[symbol]:
                        self.logger.info(f"Saving {len(saved_ha_candles[symbol])} HA candles for {symbol}")
            
            # Stop existing connections
            try:
                self.websocket_manager.stop_all_streams()
            except:
                pass
            
            # Small delay before reconnection
            await asyncio.sleep(2)
            
            # Attempt reconnection
            self.websocket_reconnect_attempts += 1
            reconnect_success = await self.setup_websockets()
            
            if reconnect_success and saved_ha_candles:
                # RESTORE CANDLE HISTORY AFTER RECONNECTION
                for symbol, candles in saved_candles.items():
                    if candles and symbol in saved_ha_candles:
                        self.websocket_manager.restore_candle_history(
                            symbol, 
                            candles, 
                            saved_ha_candles[symbol]
                        )
                
                await self.notifier.send_status_update("WebSocket Reconnected", 
                    f"✅ Reconnected with history preserved! Candles intact.")
                self.logger.info("WebSocket reconnected with candle history preserved")
            else:
                await self.notifier.send_error_alert(
                    f"❌ Health check reconnection failed (Attempt #{self.websocket_reconnect_attempts})")
            
        except Exception as e:
            self.logger.error(f"Error checking WebSocket health: {e}")

    
    async def log_market_status_with_analysis(self):
        """Enhanced market status logging with candle countdown"""
        try:
            current_time = datetime.now()
        
            # Log status every 30 seconds
            if (current_time - self.last_price_update).total_seconds() >= 30:
            
                # Get current NIFTY data
                nifty_symbol = "NIFTY"
                websocket_status = "Connected" if self.websocket_manager else "Disconnected"
            
                # Get candle count
                candle_count = 0
                if self.websocket_manager and hasattr(self.websocket_manager, 'latest_ha_candles'):
                    if nifty_symbol in self.websocket_manager.latest_ha_candles:
                        candle_count = len(self.websocket_manager.latest_ha_candles[nifty_symbol])
            
                # Get current price
                nifty_price = None
                if nifty_symbol in self.latest_ticks:
                    nifty_price = self.latest_ticks[nifty_symbol].get('ltp', 0)
            
                # Calculate time to next candle
                if self.websocket_manager:
                    current_candle = self.websocket_manager.candle_aggregator.get_current_candle(nifty_symbol)
                    if current_candle:
                        time_to_next = 60 - (current_time - current_candle['start_time']).total_seconds()
                        next_candle_str = f" | Next candle in: {int(time_to_next)}s"
                    else:
                        next_candle_str = ""
                else:
                    next_candle_str = ""
            
                # Log status with candle info
                if candle_count < 15:
                    status_msg = f"Market Status - NIFTY: Rs.{nifty_price:.2f} | Candles: {candle_count}/15{next_candle_str}"
                else:
                    status_msg = f"Market Status - NIFTY: Rs.{nifty_price:.2f} | Strategy: Active | Candles: {candle_count}{next_candle_str}"
            
                self.logger.info(status_msg)
                self.last_price_update = current_time
            
        except Exception as e:
            self.logger.error(f"Error logging market status: {e}")
    
    async def analyze_and_log_signal_conditions(self):
        """Analyze and log why signals are/aren't triggering"""
        try:
            for strategy in self.strategies:
                if not strategy.is_active:
                    continue
                
                # Import PineScriptStrategy locally to avoid circular imports
                from src.strategy.pine_script_strategy import PineScriptStrategy
                
                # Check if this is a Pine Script strategy
                if not isinstance(strategy, PineScriptStrategy):
                    continue
                
                candle_count = len(strategy.ha_candles_history)
                required_candles = strategy.adx_length + 1
                
                if candle_count < required_candles:
                    self.logger.info(f"Signal Check - Building data: {candle_count}/{required_candles} HA candles")
                    continue
                
                # Get latest data for analysis
                latest_candle = strategy.ha_candles_history[-1]
                trend_line = strategy.calculate_trend_line(strategy.ha_candles_history)
                current_price = latest_candle.get('ha_close', 0)
                
                if not trend_line:
                    continue
                
                # Analyze conditions
                strong_green, strong_red, body_pct = strategy.analyze_candle_strength(latest_candle)
                adx, plus_di, minus_di = strategy.calculate_adx(strategy.ha_candles_history)
                
                if not adx:
                    continue
                
                price_above = current_price > trend_line
                trend_ok = adx > strategy.adx_threshold
                price_diff = current_price - trend_line
                price_diff_pct = (price_diff / trend_line) * 100
                
                # Detailed analysis log
                self.logger.info(f"Pine Script Analysis:")
                self.logger.info(f"    Current Price: Rs.{current_price:.2f}")
                self.logger.info(f"    Trend Line: Rs.{trend_line:.2f} ({price_diff:+.2f} | {price_diff_pct:+.2f}%)")
                self.logger.info(f"    Candle: {' Strong Green' if strong_green else ' Weak'} ({body_pct:.1%})")
                self.logger.info(f"    ADX: {adx:.1f} ({'' if trend_ok else ''} > {strategy.adx_threshold})")
                self.logger.info(f"    Position: {' In Trade' if strategy.in_trade else ' Available'}")
                
                # Determine signal status
                buy_conditions = [
                    ("Price above trend", price_above),
                    ("Strong green candle", strong_green),
                    ("ADX > threshold", trend_ok),
                    ("Not in trade", not strategy.in_trade)
                ]
                
                met_conditions = [cond for cond, status in buy_conditions if status]
                missing_conditions = [cond for cond, status in buy_conditions if not status]
                
                if len(met_conditions) == len(buy_conditions):
                    self.logger.info(f"BUY SIGNAL CONDITIONS MET! Ready for next candle confirmation.")
                else:
                    self.logger.info(f"Waiting for: {', '.join(missing_conditions)}")
                    self.logger.info(f"Met: {', '.join(met_conditions)}")
                
        except Exception as e:
            self.logger.error(f"Error analyzing signal conditions: {e}")
    
    async def send_periodic_telegram_update(self):
        """Send periodic comprehensive status updates via Telegram"""
        try:
            current_time = datetime.now()
            
            # Send update every hour during market hours
            if (current_time - self.last_telegram_update).total_seconds() < self.telegram_update_interval:
                return
                
            # Calculate session stats
            session_duration = current_time - self.session_start_time
            hours = int(session_duration.total_seconds() / 3600)
            minutes = int((session_duration.total_seconds() % 3600) / 60)
            
            # Get current NIFTY price
            nifty_price = "N/A"
            nifty_change = ""
            if "NIFTY" in self.latest_ticks:
                price = self.latest_ticks['NIFTY'].get('ltp', 0)
                nifty_price = f"Rs.{price:.2f}"
                
                # Calculate change if we have reference price
                if hasattr(self, 'session_start_price'):
                    change = price - self.session_start_price
                    change_pct = (change / self.session_start_price) * 100
                    nifty_change = f" ({change:+.2f} | {change_pct:+.2f}%)"
            
            # WebSocket status
            ws_status = "✅ Connected"
            if not self.websocket_manager:
                ws_status = "❌ Disconnected"
            elif self.websocket_reconnect_attempts > 0:
                ws_status += f" (Reconnected {self.websocket_reconnect_attempts}x)"
            
            # Signal analysis - Fixed type checking
            signal_status = "🔍 Analyzing..."
            if self.strategies:
                from src.strategy.pine_script_strategy import PineScriptStrategy
                pine_strategy = None
                for strategy in self.strategies:
                    if isinstance(strategy, PineScriptStrategy):
                        pine_strategy = strategy
                        break
                
                if pine_strategy and len(pine_strategy.ha_candles_history) >= 15:
                    signal_status = "🎯 Ready for Signals"
                elif pine_strategy:
                    signal_status = f"🔄 Building Data ({len(pine_strategy.ha_candles_history)}/15)"
            
            message = f""" *Hourly Status Update*

🕐 *Session Time:* {hours}h {minutes}m
📈 *NIFTY:* {nifty_price}{nifty_change}
🔗 *WebSocket:* {ws_status}
🤖 *Strategy:* {signal_status}

📊 *Performance Today:*
🎯 *Trades:* {self.total_trades}
💵 *P&L:* Rs.{self.total_pnl:,.2f}
✅ *Win Rate:* {(self.winning_trades/max(1,self.total_trades))*100:.1f}%
🏆 *Best Trade:* Rs.{self.best_trade:,.2f}

🎯 *Pine Script Status:*
📊 *Target Accuracy:* 67%
🔍 *Monitoring:* Trend + Green Candle + ADX
⏳ *Waiting for:* Bullish Setup

💪 *Bot Status:* Active & Monitoring!"""
            
            await self.notifier.send_message(message)
            self.last_telegram_update = current_time
            
        except Exception as e:
            self.logger.error(f"Error sending periodic Telegram update: {e}")
    
    async def evaluate_strategies_on_new_candle(self, symbol: str, ha_candle: Dict):
        """Evaluate all strategies when a new HA candle is completed"""
        try:
            if not self.is_market_open():
                return
                
            for strategy in self.strategies:
                if not strategy.is_active:
                    continue
                    
                # Prepare market data with HA candle for Pine Script strategy
                market_data = self.prepare_market_data_for_strategy(symbol, ha_candle)
                
                # Check for entry signals
                entry_order = await strategy.should_enter(market_data)
                if entry_order:
                    if await self.place_order(entry_order):
                        self.orders.append(entry_order)
                        await strategy.on_order_filled(entry_order)
                
                # Check for exit signals on existing positions
                for position_key, position in list(self.positions.items()):
                    if position.symbol == symbol:
                        exit_order = await strategy.should_exit(position, market_data)
                        if exit_order:
                            if await self.place_order(exit_order):
                                self.orders.append(exit_order)
                                await strategy.on_order_filled(exit_order)
                                if exit_order.quantity >= position.quantity:
                                    del self.positions[position_key]
                                    
        except Exception as e:
            self.logger.error(f"Error evaluating strategies: {e}")
    
    def prepare_market_data_for_strategy(self, symbol: str, ha_candle: Dict) -> Dict:
        """Prepare comprehensive market data for strategy evaluation"""
        
        # Get historical data if available
        historical_candles = []
        historical_ha_candles = []
        
        if self.websocket_manager:
            historical_candles = self.websocket_manager.get_latest_candles(symbol, 50)
            historical_ha_candles = self.websocket_manager.get_latest_ha_candles(symbol, 50)
        
        # Get current tick data
        current_tick = self.latest_ticks.get(symbol, {})
        
        market_data = {
            'symbol': symbol,
            'timestamp': datetime.now(),
            'price': ha_candle.get('ha_close', 0),
            'ha_candle': ha_candle,
            'current_tick': current_tick,
            'historical_candles': historical_candles,
            'historical_ha_candles': historical_ha_candles,
            'instrument_key': current_tick.get('instrument_key', ''),
            
            # For backward compatibility
            'high': ha_candle.get('ha_high', 0),
            'low': ha_candle.get('ha_low', 0),
            'volume': ha_candle.get('volume', 0),
            'open': ha_candle.get('ha_open', 0),
            'close': ha_candle.get('ha_close', 0)
        }
        
        return market_data
    
    def _extract_symbol_from_key(self, instrument_key: str) -> str:
        """Extract symbol from instrument key"""
        key_to_symbol = {
            'NSE_INDEX|Nifty 50': 'NIFTY',
            'NSE_INDEX|Nifty Bank': 'BANKNIFTY',
            'BSE_INDEX|SENSEX': 'SENSEX',
            'NSE_FO|50201': 'NIFTY_FUT',
            'NSE_FO|26009': 'BANKNIFTY_FUT'
        }
        
        return key_to_symbol.get(instrument_key, instrument_key.split('|')[-1] if '|' in instrument_key else instrument_key)
    
    async def authenticate(self):
        """Authenticate with Upstox"""
        
        if self.upstox_client.access_token:
            self.logger.info("Found stored access token, testing...")
            
            if await self.upstox_client.test_token():
                self.logger.info("Stored token is valid, using it")
                await self.notifier.send_status_update("Authenticated", "Using stored access token")
                return True
            else:
                self.logger.info("Stored token is invalid, requesting new authentication")
        
        print(f"Please visit: {self.upstox_client.get_login_url()}")
        auth_code = input("Enter the authorization code: ")
        
        if await self.upstox_client.get_access_token(auth_code):
            self.logger.info("Successfully authenticated with Upstox")
            await self.notifier.send_status_update("Authenticated", "Successfully connected to Upstox API")
            return True
        else:
            self.logger.error("Failed to authenticate with Upstox")
            await self.notifier.send_error_alert("Failed to authenticate with Upstox")
            return False
    
    async def place_order(self, order: Order) -> bool:
        """Place an order with enhanced logging"""
        try:
            if self.paper_trading:
                # Enhanced paper trading simulation
                order.status = OrderStatus.FILLED
                order.filled_price = order.price
                order.filled_quantity = order.quantity
                order.order_id = f"PAPER_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Calculate investment details
                lot_size = 75
                total_investment = order.quantity * lot_size * order.price
                total_shares = order.quantity * lot_size
                
                self.trading_logger.info(
                    f"📋 PAPER TRADE - {order.transaction_type.value} {order.quantity} lots "
                    f"({total_shares:,} shares) of {order.symbol} @ Rs.{order.price:.2f}"
                )
                self.trading_logger.info(f"💰 Total Investment: Rs.{total_investment:,.2f}")
                
                # Send enhanced Telegram notification
                await self.send_enhanced_trade_notification(order, total_investment)
                
                # Update paper positions
                await self.update_paper_positions(order)
                
                return True
            else:
                # Real order placement logic would go here
                self.logger.warning("Live trading not implemented yet")
                return False
                
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            await self.notifier.send_error_alert(f"Error placing order: {str(e)}")
            return False
    
    async def send_enhanced_trade_notification(self, order: Order, total_investment: float):
        """Send enhanced trade notification via Telegram"""
        try:
            lot_size = 75
            total_shares = order.quantity * lot_size
            current_capital = 20000 + self.total_pnl
            
            if order.transaction_type == TransactionType.BUY:
                message = f"""🚀 *BUY SIGNAL - AstraRise Bot*

📊 *NIFTY Analysis:* Pine Script Bullish Signal Detected!
🎯 *Conditions Met:* Price > Trend + Strong Green + ADX > 20

💰 *PAPER TRADE EXECUTED:*
🔹 *Symbol:* {order.symbol}
🔹 *Action:* BUY {order.quantity} lots ({total_shares:,} shares)
🔹 *Price:* Rs.{order.price:.2f} per share
🔹 *Investment:* Rs.{total_investment:,.2f}

📈 *Capital Management:*
💵 *Total Capital:* Rs.{current_capital:,.2f}
💸 *Used:* Rs.{total_investment:,.2f} ({(total_investment/current_capital)*100:.1f}%)
💰 *Remaining:* Rs.{current_capital - total_investment:,.2f}

⏰ *Time:* {datetime.now().strftime('%I:%M:%S %p')}
🗓️ *Date:* {datetime.now().strftime('%B %d, %Y')}

🎯 Pine Script strategy in action! Let's see the results! 🚀"""
                
                await self.notifier.send_message(message)
                
        except Exception as e:
            self.logger.error(f"Error sending enhanced trade notification: {e}")
    
    async def update_paper_positions(self, order: Order):
        """Update paper trading positions with tracking"""
        try:
            position_key = f"{order.symbol}_{order.instrument_key or 'default'}"
            
            if order.transaction_type == TransactionType.BUY:
                entry_time = datetime.now()
                
                if position_key in self.positions:
                    existing = self.positions[position_key]
                    total_quantity = existing.quantity + order.quantity
                    total_cost = (existing.quantity * existing.average_price) + (order.quantity * order.price)
                    new_avg_price = total_cost / total_quantity
                    
                    existing.quantity = total_quantity
                    existing.average_price = new_avg_price
                else:
                    position = Position(
                        symbol=order.symbol,
                        quantity=order.quantity,
                        average_price=order.price,
                        current_price=order.price,
                        pnl=0,
                        unrealized_pnl=0,
                        instrument_key=order.instrument_key or 'default'
                    )
                    position.entry_time = entry_time
                    self.positions[position_key] = position
            
            elif order.transaction_type == TransactionType.SELL:
                if position_key in self.positions:
                    existing = self.positions[position_key]
                    entry_time = getattr(existing, 'entry_time', datetime.now())
                    exit_time = datetime.now()
                    
                    if order.quantity >= existing.quantity:
                        # Close position completely
                        lot_size = 75
                        pnl = (order.price - existing.average_price) * existing.quantity * lot_size
                        
                        # Update statistics
                        self.total_pnl += pnl
                        self.total_trades += 1
                        
                        if pnl > 0:
                            self.winning_trades += 1
                        
                        if pnl > self.best_trade:
                            self.best_trade = pnl
                        if pnl < self.worst_trade:
                            self.worst_trade = pnl
                        
                        # Send P&L notification
                        await self.send_pnl_notification(order.symbol, pnl, existing.average_price, 
                                                       order.price, existing.quantity, entry_time, exit_time)
                        
                        del self.positions[position_key]
                        self.trading_logger.info(f"Position closed: {order.symbol} P&L: Rs.{pnl:.2f}")
                    else:
                        # Partial close
                        existing.quantity -= order.quantity
                        
        except Exception as e:
            self.logger.error(f"Error updating paper positions: {e}")
    
    async def send_pnl_notification(self, symbol: str, pnl: float, entry_price: float, 
                                  exit_price: float, quantity: int, entry_time: datetime, exit_time: datetime):
        """Send comprehensive P&L notification"""
        try:
            lot_size = 75
            total_shares = quantity * lot_size
            trade_value = entry_price * total_shares
            pnl_pct = (pnl / trade_value) * 100 if trade_value > 0 else 0
            
            # Calculate trade duration
            duration = exit_time - entry_time
            duration_minutes = int(duration.total_seconds() / 60)
            duration_hours = duration_minutes // 60
            duration_mins = duration_minutes % 60
            
            # Determine status
            status_emoji = "🟢" if pnl > 0 else "🔴"
            status_text = "PROFIT" if pnl > 0 else "LOSS"
            
            # Calculate win rate
            win_rate = (self.winning_trades / max(1, self.total_trades)) * 100
            
            message = f"""📊 *TRADE COMPLETED - AstraRise Bot*

{status_emoji} *{status_text}:* Rs.{abs(pnl):,.2f} ({pnl_pct:+.2f}%)

📈 *Trade Details:*
🔹 *Symbol:* {symbol}
🔹 *Quantity:* {quantity} lots ({total_shares:,} shares)
🔹 *Entry Price:* Rs.{entry_price:.2f}
🔹 *Exit Price:* Rs.{exit_price:.2f}
🔹 *Price Change:* Rs.{exit_price - entry_price:+.2f}

⏰ *Timing:*
📅 *Entry:* {entry_time.strftime('%I:%M:%S %p')}
📅 *Exit:* {exit_time.strftime('%I:%M:%S %p')}
⏱️ *Duration:* {duration_hours}h {duration_mins}m

📊 *Session Performance:*
🎯 *Total Trades:* {self.total_trades}
✅ *Winning Trades:* {self.winning_trades} ({win_rate:.1f}%)
💵 *Total P&L:* Rs.{self.total_pnl:,.2f}
📈 *Pine Script Target:* 67% (Current: {win_rate:.1f}%)

🏆 *Records:*
🥇 *Best Trade:* Rs.{self.best_trade:,.2f}
📉 *Worst Trade:* Rs.{self.worst_trade:,.2f}

{"🎉 Excellent work!" if pnl > 0 else "💪 Stay strong, next one will be better!"}"""
            
            await self.notifier.send_message(message)
            
        except Exception as e:
            self.logger.error(f"Error sending P&L notification: {e}")
    
    async def update_positions(self):
        """Update current positions with real-time prices"""
        try:
            if not self.paper_trading:
                # Real positions update would go here
                pass
            else:
                # Update paper positions with current market prices
                for position_key, position in self.positions.items():
                    symbol = position.symbol
                    if symbol in self.latest_ticks:
                        current_price = float(self.latest_ticks[symbol].get('ltp', position.current_price))
                        position.current_price = current_price
                        position.unrealized_pnl = (current_price - position.average_price) * position.quantity
                
        except Exception as e:
            self.logger.error(f"Error updating positions: {e}")
    
    async def run(self):
        """Enhanced main bot execution loop"""
        self.logger.info("Starting enhanced trading bot...")
        
        # Store session start price for reference
        await asyncio.sleep(1)  # Small delay to ensure everything is initialized
        
        # Authenticate
        if not await self.authenticate():
            return
        
        # Setup websockets
        websocket_success = await self.setup_websockets()
        
        # Send enhanced startup notification
        startup_message = f"""🚀 *AstraRise Trading Bot Started*

📊 *Configuration:*
💰 *Capital:* Rs.20,000
🎯 *Max Risk:* Rs.15,000 (75%)
📈 *Strategy:* Pine Script v2 (Target: 67% accuracy)
⚡ *Mode:* Paper Trading (Safe testing)

🔗 *Connection Status:*
✅ *Upstox API:* Connected
{('✅' if websocket_success else '❌')} *WebSocket:* {'Connected' if websocket_success else 'Failed (using fallback)'}
📱 *Telegram:* Active

🕐 *Market Schedule:*
📅 *Date:* {datetime.now().strftime('%B %d, %Y')}
⏰ *Started:* {datetime.now().strftime('%I:%M:%S %p')}
📊 *Market Hours:* 9:15 AM - 3:30 PM IST

🎯 *Today's Goals:*
• Test Pine Script strategy with live data
• Monitor 67% accuracy target
• Validate Rs.20k capital management
• Track real-time performance

Bot is ready for market action! 💪"""
        
        await self.notifier.send_message(startup_message)
        
        # Add Pine Script strategy
        if not self.strategies:
            from src.strategy.pine_script_strategy import PineScriptStrategy
            pine_strategy = PineScriptStrategy("dhana_pine_script_strategy", {
                'adx_length': 14,
                'adx_threshold': 20,
                'strong_candle_threshold': 0.6,
                'max_positions': 1,
                'total_capital': 20000,
                'max_risk_pct': 0.75,
                'risk_per_trade': 15000
            })
            self.add_strategy(pine_strategy)
        
        # Store initial NIFTY price for session tracking
        if "NIFTY" in self.latest_ticks:
            self.session_start_price = self.latest_ticks['NIFTY'].get('ltp', 0)
        
        self.is_running = True
        
        try:
            while self.is_running:
                if self.is_market_open():
                    # Enhanced monitoring during market hours
                    await self.check_websocket_health()
                    await self.log_market_status_with_analysis()
                    await self.update_positions()
                    await self.send_periodic_telegram_update()
                    
                    # Fallback strategy execution if no websockets
                    if not websocket_success:
                        await self.run_strategies_with_rest_api()
                    
                    # Wait before next iteration
                    await asyncio.sleep(30)
                else:
                    self.logger.info("Market closed, waiting...")
                    await asyncio.sleep(300)
                    
        except KeyboardInterrupt:
            self.logger.info("Bot stopped by user")
            
            # Send shutdown summary
            session_duration = datetime.now() - self.session_start_time
            hours = int(session_duration.total_seconds() / 3600)
            minutes = int((session_duration.total_seconds() % 3600) / 60)
            
            shutdown_message = f"""🛑 *AstraRise Bot Stopped*

📊 *Session Summary:*
⏰ *Runtime:* {hours}h {minutes}m
🎯 *Trades:* {self.total_trades}
💵 *P&L:* Rs.{self.total_pnl:,.2f}
📈 *Win Rate:* {(self.winning_trades/max(1,self.total_trades))*100:.1f}%
🔗 *Reconnections:* {self.websocket_reconnect_attempts}

Thanks for testing! See you tomorrow! 👋"""
            
            await self.notifier.send_message(shutdown_message)
            await self.notifier.send_status_update("Stopped", "Bot stopped by user")
            
        except Exception as e:
            self.logger.error(f"Bot error: {e}")
            await self.notifier.send_error_alert(f"Bot crashed: {str(e)}")
        finally:
            # Cleanup
            if self.websocket_manager:
                self.websocket_manager.stop_all_streams()
            self.is_running = False
            self.logger.info("Enhanced trading bot stopped")
    
    async def run_strategies_with_rest_api(self):
        """Fallback method using REST API when websockets fail"""
        for strategy in self.strategies:
            if not strategy.is_active:
                continue
                
            try:
                # Placeholder for REST API implementation
                market_data = {
                    'symbol': 'FALLBACK',
                    'price': 0,
                    'timestamp': datetime.now()
                }
                
                # Check for entry signals
                entry_order = await strategy.should_enter(market_data)
                if entry_order:
                    if await self.place_order(entry_order):
                        self.orders.append(entry_order)
                
                # Check for exit signals
                for position in self.positions.values():
                    exit_order = await strategy.should_exit(position, market_data)
                    if exit_order:
                        if await self.place_order(exit_order):
                            self.orders.append(exit_order)
                            
            except Exception as e:
                await strategy.on_error(e)
                await self.notifier.send_error_alert(f"Strategy {strategy.name} error: {str(e)}")
                
                
# ==================== Enhanced Multi-Strategy Trading Bot ====================

# Add these enhancements to your existing trading_bot.py:

class MultiStrategyTradingBot(TradingBot):  # Extend your existing TradingBot
    """Enhanced trading bot supporting multiple strategies simultaneously"""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        
        # Multi-strategy containers
        self.strategy_configs = {}
        self.strategy_performance = {}
        
    def add_strategy_config(self, strategy_name: str, config: Dict):
        """Add strategy configuration"""
        self.strategy_configs[strategy_name] = config
        self.strategy_performance[strategy_name] = {
            'trades': 0,
            'wins': 0,
            'total_pnl': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0
        }
        self.logger.info(f"Added strategy config: {strategy_name} - {config['trading_mode']}")
    
    def initialize_strategies(self):
        """Initialize all configured strategies"""
        
        # Clear existing strategies
        self.strategies = []
        
        for strategy_name, config in self.strategy_configs.items():
            try:
                # Import enhanced strategy
                from src.strategy.enhanced_pine_script_strategy import EnhancedPineScriptStrategy
                
                # Create strategy instance
                strategy = EnhancedPineScriptStrategy(strategy_name, config)
                self.add_strategy(strategy)
                
                self.logger.info(f"Initialized strategy: {strategy_name} ({config['trading_mode']})")
                
            except Exception as e:
                self.logger.error(f"Failed to initialize strategy {strategy_name}: {e}")
    
    async def evaluate_strategies_on_new_candle(self, symbol: str, ha_candle: Dict):
        """Enhanced strategy evaluation for multiple strategies"""
        try:
            if not self.is_market_open():
                return
            
            # Prepare market data
            market_data = self.prepare_market_data_for_strategy(symbol, ha_candle)
            
            # Process each strategy
            for strategy in self.strategies:
                if not strategy.is_active:
                    continue
                
                try:
                    # Check for entry signals
                    entry_order = await strategy.should_enter(market_data)
                    if entry_order:
                        if await self.place_enhanced_order(entry_order):
                            self.orders.append(entry_order)
                            await strategy.on_order_filled(entry_order)
                            
                            # Send strategy-specific notification
                            await self.send_multi_strategy_notification(entry_order, "ENTRY")
                    
                    # Check for exit signals on existing positions
                    for position_key, position in list(self.positions.items()):
                        # Only check positions belonging to this strategy
                        if getattr(position, 'strategy_name', '') == strategy.name:
                            exit_order = await strategy.should_exit(position, market_data)
                            if exit_order:
                                if await self.place_enhanced_order(exit_order):
                                    self.orders.append(exit_order)
                                    await strategy.on_order_filled(exit_order)
                                    
                                    # Update performance tracking
                                    await self.update_strategy_performance(exit_order, position)
                                    
                                    # Send exit notification
                                    await self.send_multi_strategy_notification(exit_order, "EXIT")
                                    
                                    # Remove closed position
                                    if exit_order.quantity >= position.quantity:
                                        del self.positions[position_key]
                
                except Exception as e:
                    self.logger.error(f"Error processing strategy {strategy.name}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error evaluating strategies: {e}")
    
    async def place_enhanced_order(self, order: Order) -> bool:
        """Enhanced order placement with multi-strategy support"""
        try:
            if self.paper_trading:
                # Enhanced paper trading with strategy tracking
                order.status = OrderStatus.FILLED
                order.filled_price = order.price
                order.filled_quantity = order.quantity
                order.order_id = f"PAPER_{order.strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Calculate investment details
                lot_size = 75
                total_investment = order.quantity * lot_size * order.price
                total_shares = order.quantity * lot_size
                
                self.trading_logger.info(
                    f"📋 PAPER TRADE [{order.strategy_name}] - {order.transaction_type.value} {order.quantity} lots "
                    f"({total_shares:,} shares) of {order.symbol} @ Rs.{order.price:.2f}"
                )
                self.trading_logger.info(f"💰 Total Investment: Rs.{total_investment:,.2f}")
                
                # Update paper positions with strategy info
                await self.update_enhanced_paper_positions(order)
                
                return True
            else:
                # Real order placement logic would go here
                # ... existing real trading code ...
                pass
                
        except Exception as e:
            self.logger.error(f"Error placing enhanced order: {e}")
            return False
    
    async def update_enhanced_paper_positions(self, order: Order):
        """Update paper positions with multi-strategy tracking"""
        try:
            position_key = f"{order.symbol}_{order.strategy_name}_{getattr(order, 'option_type', 'CE')}"
            
            if order.transaction_type == TransactionType.BUY:
                entry_time = datetime.now()
                
                if position_key in self.positions:
                    existing = self.positions[position_key]
                    total_quantity = existing.quantity + order.quantity
                    total_cost = (existing.quantity * existing.average_price) + (order.quantity * order.price)
                    new_avg_price = total_cost / total_quantity
                    
                    existing.quantity = total_quantity
                    existing.average_price = new_avg_price
                else:
                    position = Position(
                        symbol=order.symbol,
                        quantity=order.quantity,
                        average_price=order.price,
                        current_price=order.price,
                        pnl=0,
                        unrealized_pnl=0,
                        instrument_key=order.instrument_key or 'default'
                    )
                    # Add strategy-specific attributes
                    position.entry_time = entry_time
                    position.strategy_name = order.strategy_name
                    position.option_type = getattr(order, 'option_type', 'CE')
                    position.strategy_mode = getattr(order, 'strategy_mode', 'CE')
                    
                    self.positions[position_key] = position
            
            elif order.transaction_type == TransactionType.SELL:
                if position_key in self.positions:
                    existing = self.positions[position_key]
                    entry_time = getattr(existing, 'entry_time', datetime.now())
                    exit_time = datetime.now()
                    
                    if order.quantity >= existing.quantity:
                        # Close position completely
                        lot_size = 75
                        pnl = (order.price - existing.average_price) * existing.quantity * lot_size
                        
                        # Update global statistics
                        self.total_pnl += pnl
                        self.total_trades += 1
                        
                        if pnl > 0:
                            self.winning_trades += 1
                        
                        if pnl > self.best_trade:
                            self.best_trade = pnl
                        if pnl < self.worst_trade:
                            self.worst_trade = pnl
                        
                        # Update strategy-specific performance
                        strategy_name = order.strategy_name
                        if strategy_name in self.strategy_performance:
                            perf = self.strategy_performance[strategy_name]
                            perf['trades'] += 1
                            perf['total_pnl'] += pnl
                            if pnl > 0:
                                perf['wins'] += 1
                            if pnl > perf['best_trade']:
                                perf['best_trade'] = pnl
                            if pnl < perf['worst_trade']:
                                perf['worst_trade'] = pnl
                        
                        # Send P&L notification
                        await self.send_enhanced_pnl_notification(order.symbol, pnl, existing.average_price, 
                                                       order.price, existing.quantity, entry_time, exit_time, order.strategy_name)
                        
                        del self.positions[position_key]
                        self.trading_logger.info(f"Position closed [{order.strategy_name}]: {order.symbol} P&L: Rs.{pnl:.2f}")
                    else:
                        # Partial close
                        existing.quantity -= order.quantity
                        
        except Exception as e:
            self.logger.error(f"Error updating enhanced paper positions: {e}")
    
    async def send_multi_strategy_notification(self, order: Order, action: str):
        """Send strategy-specific notifications"""
        try:
            strategy_name = getattr(order, 'strategy_name', 'Unknown')
            option_type = getattr(order, 'option_type', 'CE')
            strategy_mode = getattr(order, 'strategy_mode', 'CE')
            
            # Strategy-specific emojis and colors
            strategy_info = {
                'CE': {'emoji': '^', 'name': 'Bullish CE', 'color': '🟢'},
                'PE': {'emoji': '>', 'name': 'Bearish PE', 'color': '🔴'},
                'BIDIRECTIONAL': {'emoji': '', 'name': 'Bidirectional', 'color': '🔵'}
            }
            
            info = strategy_info.get(strategy_mode, strategy_info['CE'])
            
            if action == "ENTRY":
                lot_size = 75
                total_shares = order.quantity * lot_size
                total_investment = order.quantity * lot_size * order.price
                current_capital = 20000 + self.total_pnl
                
                message = f"""{info['emoji']} {info['name']} SIGNAL - AstraRise Bot

📊 *Strategy:* {strategy_name}
🎯 *Mode:* {strategy_mode} | *Option:* {option_type}
💰 *Analysis:* Pine Script {info['name']} Signal Detected!

💰 *PAPER TRADE EXECUTED:*
🔹 *Symbol:* {order.symbol}
🔹 *Action:* BUY {order.quantity} lots ({total_shares:,} shares)
🔹 *Price:* Rs.{order.price:.2f} per share
🔹 *Investment:* Rs.{total_investment:,.2f}

📈 *Capital Management:*
💵 *Total Capital:* Rs.{current_capital:,.2f}
💸 *Used:* Rs.{total_investment:,.2f} ({(total_investment/current_capital)*100:.1f}%)
💰 *Remaining:* Rs.{current_capital - total_investment:,.2f}

⏰ *Time:* {datetime.now().strftime('%I:%M:%S %p')}

🎯 {strategy_name} strategy executing! 🚀"""
                
                await self.notifier.send_message(message)
                
        except Exception as e:
            self.logger.error(f"Error sending multi-strategy notification: {e}")
    
    async def send_enhanced_pnl_notification(self, symbol: str, pnl: float, entry_price: float, 
                                           exit_price: float, quantity: int, entry_time: datetime, 
                                           exit_time: datetime, strategy_name: str):
        """Send enhanced P&L notification with strategy performance"""
        try:
            lot_size = 75
            total_shares = quantity * lot_size
            trade_value = entry_price * total_shares
            pnl_pct = (pnl / trade_value) * 100 if trade_value > 0 else 0
            
            # Calculate trade duration
            duration = exit_time - entry_time
            duration_minutes = int(duration.total_seconds() / 60)
            duration_hours = duration_minutes // 60
            duration_mins = duration_minutes % 60
            
            # Determine status
            status_emoji = "🟢" if pnl > 0 else "🔴"
            status_text = "PROFIT" if pnl > 0 else "LOSS"
            
            # Get strategy performance
            strategy_perf = self.strategy_performance.get(strategy_name, {})
            strategy_trades = strategy_perf.get('trades', 0)
            strategy_wins = strategy_perf.get('wins', 0)
            strategy_win_rate = (strategy_wins / max(1, strategy_trades)) * 100
            strategy_pnl = strategy_perf.get('total_pnl', 0.0)
            
            # Calculate overall win rate
            overall_win_rate = (self.winning_trades / max(1, self.total_trades)) * 100
            
            message = f"""📊 *TRADE COMPLETED - {strategy_name}*

{status_emoji} *{status_text}:* Rs.{abs(pnl):,.2f} ({pnl_pct:+.2f}%)

📈 *Trade Details:*
🔹 *Strategy:* {strategy_name}
🔹 *Symbol:* {symbol}
🔹 *Quantity:* {quantity} lots ({total_shares:,} shares)
🔹 *Entry Price:* Rs.{entry_price:.2f}
🔹 *Exit Price:* Rs.{exit_price:.2f}
🔹 *Price Change:* Rs.{exit_price - entry_price:+.2f}

⏰ *Timing:*
📅 *Entry:* {entry_time.strftime('%I:%M:%S %p')}
📅 *Exit:* {exit_time.strftime('%I:%M:%S %p')}
⏱️ *Duration:* {duration_hours}h {duration_mins}m

📊 *Strategy Performance ({strategy_name}):*
🎯 *Trades:* {strategy_trades}
✅ *Wins:* {strategy_wins} ({strategy_win_rate:.1f}%)
💵 *Strategy P&L:* Rs.{strategy_pnl:,.2f}

📊 *Overall Session Performance:*
🎯 *Total Trades:* {self.total_trades}
✅ *Winning Trades:* {self.winning_trades} ({overall_win_rate:.1f}%)
💵 *Total P&L:* Rs.{self.total_pnl:,.2f}
📈 *Pine Script Target:* 67% (Current: {overall_win_rate:.1f}%)

🏆 *Records:*
🥇 *Best Trade:* Rs.{self.best_trade:,.2f}
📉 *Worst Trade:* Rs.{self.worst_trade:,.2f}

{"🎉 Excellent work!" if pnl > 0 else "💪 Stay strong, next one will be better!"}"""
            
            await self.notifier.send_message(message)
            
        except Exception as e:
            self.logger.error(f"Error sending enhanced P&L notification: {e}")
    
    async def send_multi_strategy_status_update(self):
        """Send comprehensive multi-strategy status update"""
        try:
            current_time = datetime.now()
            
            # Calculate session stats
            session_duration = current_time - self.session_start_time
            hours = int(session_duration.total_seconds() / 3600)
            minutes = int((session_duration.total_seconds() % 3600) / 60)
            
            # Get current NIFTY price
            nifty_price = "N/A"
            nifty_change = ""
            if "NIFTY" in self.latest_ticks:
                price = self.latest_ticks['NIFTY'].get('ltp', 0)
                nifty_price = f"Rs.{price:.2f}"
                
                if hasattr(self, 'session_start_price'):
                    change = price - self.session_start_price
                    change_pct = (change / self.session_start_price) * 100
                    nifty_change = f" ({change:+.2f} | {change_pct:+.2f}%)"
            
            # WebSocket status
            ws_status = "✅ Connected"
            if not self.websocket_manager:
                ws_status = "❌ Disconnected"
            elif self.websocket_reconnect_attempts > 0:
                ws_status += f" (Reconnected {self.websocket_reconnect_attempts}x)"
            
            # Strategy performance summary
            strategy_summary = ""
            for strategy_name, perf in self.strategy_performance.items():
                trades = perf['trades']
                wins = perf['wins']
                win_rate = (wins / max(1, trades)) * 100
                pnl = perf['total_pnl']
                
                config = self.strategy_configs.get(strategy_name, {})
                mode = config.get('trading_mode', 'Unknown')
                
                strategy_summary += f"""
🎯 *{strategy_name}* ({mode}):
   📊 Trades: {trades} | Win Rate: {win_rate:.1f}%
   💵 P&L: Rs.{pnl:,.2f}"""
            
            message = f"""📊 *Multi-Strategy Status Update*

🕐 *Session Time:* {hours}h {minutes}m
📈 *NIFTY:* {nifty_price}{nifty_change}
🔗 *WebSocket:* {ws_status}

📊 *Overall Performance:*
🎯 *Total Trades:* {self.total_trades}
💵 *Total P&L:* Rs.{self.total_pnl:,.2f}
✅ *Overall Win Rate:* {(self.winning_trades/max(1,self.total_trades))*100:.1f}%
🏆 *Best Trade:* Rs.{self.best_trade:,.2f}
{strategy_summary}

🎯 *Pine Script Multi-Strategy Status:*
📊 *Target Accuracy:* 67%
🔍 *Active Strategies:* {len(self.strategies)}
⚡ *Mode:* Paper Trading (Safe testing)

💪 *All strategies monitoring and ready!*"""
            
            await self.notifier.send_message(message)
            
        except Exception as e:
            self.logger.error(f"Error sending multi-strategy status update: {e}")

# ==================== Strategy Configuration Helper ====================

class StrategyConfigManager:
    """Helper class to manage strategy configurations"""
    
    @staticmethod
    def get_ce_only_config(capital_allocation: float = 0.33):
        """Configuration for CE-only strategy"""
        return {
            'strategy_id': 'CE_Pine_Script',
            'trading_mode': 'CE_ONLY',
            'adx_length': 14,
            'adx_threshold': 20,
            'strong_candle_threshold': 0.6,
            'max_positions': 1,
            'total_capital': int(20000 * capital_allocation),
            'max_risk_pct': 0.75,
            'risk_per_trade': int(15000 * capital_allocation)
        }
    
    @staticmethod
    def get_pe_only_config(capital_allocation: float = 0.33):
        """Configuration for PE-only strategy"""
        return {
            'strategy_id': 'PE_Pine_Script',
            'trading_mode': 'PE_ONLY',
            'adx_length': 14,
            'adx_threshold': 20,
            'strong_candle_threshold': 0.6,
            'max_positions': 1,
            'total_capital': int(20000 * capital_allocation),
            'max_risk_pct': 0.75,
            'risk_per_trade': int(15000 * capital_allocation)
        }
    
    @staticmethod
    def get_bidirectional_config(capital_allocation: float = 0.34):
        """Configuration for bidirectional strategy"""
        return {
            'strategy_id': 'Bidirectional_Pine_Script',
            'trading_mode': 'BIDIRECTIONAL',
            'adx_length': 14,
            'adx_threshold': 20,
            'strong_candle_threshold': 0.6,
            'max_positions': 2,  # Can hold both CE and PE
            'total_capital': int(20000 * capital_allocation),
            'max_risk_pct': 0.75,
            'risk_per_trade': int(15000 * capital_allocation)
        }
    
    @staticmethod
    def get_all_strategies_config():
        """Get configuration for all three strategies"""
        return {
            'CE_Pine_Script': StrategyConfigManager.get_ce_only_config(),
            'PE_Pine_Script': StrategyConfigManager.get_pe_only_config(),
            'Bidirectional_Pine_Script': StrategyConfigManager.get_bidirectional_config()
        }

# ==================== Enhanced Main Runner ====================

async def run_multi_strategy_bot():
    """Enhanced main function for multi-strategy bot"""
    
    # Load settings
    settings = Settings()
    
    # Create multi-strategy bot
    bot = MultiStrategyTradingBot(settings)
    
    # Configure strategies based on environment variable or default
    import os
    strategy_mode = os.getenv('STRATEGY_MODE', 'ALL')  # CE_ONLY, PE_ONLY, BIDIRECTIONAL, ALL
    
    config_manager = StrategyConfigManager()
    
    if strategy_mode == 'CE_ONLY':
        bot.add_strategy_config('CE_Pine_Script', config_manager.get_ce_only_config(1.0))
        
    elif strategy_mode == 'PE_ONLY':
        bot.add_strategy_config('PE_Pine_Script', config_manager.get_pe_only_config(1.0))
        
    elif strategy_mode == 'BIDIRECTIONAL':
        bot.add_strategy_config('Bidirectional_Pine_Script', config_manager.get_bidirectional_config(1.0))
        
    else:  # ALL strategies
        strategies_config = config_manager.get_all_strategies_config()
        for name, config in strategies_config.items():
            bot.add_strategy_config(name, config)
    
    # Initialize all configured strategies
    bot.initialize_strategies()
    
    # Override the periodic update method
    bot.send_periodic_telegram_update = bot.send_multi_strategy_status_update
    
    # Run the bot
    await bot.run()

# ==================== Usage Instructions ====================

# To run different strategy modes:

# 1. CE Only:
# STRATEGY_MODE=CE_ONLY python main_multi_strategy.py

# 2. PE Only:
# STRATEGY_MODE=PE_ONLY python main_multi_strategy.py

# 3. Bidirectional:
# STRATEGY_MODE=BIDIRECTIONAL python main_multi_strategy.py

# 4. All strategies:
# STRATEGY_MODE=ALL python main_multi_strategy.py
# or simply:
# python main_multi_strategy.py
                