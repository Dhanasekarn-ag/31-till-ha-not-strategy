# ==================== src/websocket/websocket_manager.py (YESTERDAY NIGHT WORKING VERSION) ====================
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Optional
import pandas as pd
import numpy as np
from collections import defaultdict, deque
import json
import threading

try:
    import upstox_client
    from upstox_client.rest import ApiException
    UPSTOX_SDK_AVAILABLE = True
except ImportError:
    UPSTOX_SDK_AVAILABLE = False

class CandleAggregator:
    """Aggregates tick data into candles of different timeframes"""
    
    def __init__(self, timeframe_minutes: int = 3):
        self.timeframe_minutes = timeframe_minutes
        self.timeframe_seconds = timeframe_minutes * 60
        self.current_candles: Dict[str, Dict] = {}
        self.completed_candles: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.logger = logging.getLogger(__name__)
        
    def process_tick(self, symbol: str, tick_data: Dict) -> Optional[Dict]:
        """Process a tick and return completed candle if any"""
        try:
            price = float(tick_data.get('ltp', 0))
            volume = int(tick_data.get('volume', 0))
            timestamp = datetime.now()
            
            if price <= 0:
                return None
            
            # Calculate candle start time
            candle_start = self._get_candle_start_time(timestamp)
            candle_key = f"{symbol}_{candle_start.strftime('%Y%m%d_%H%M%S')}"
            
            # Initialize or update current candle
            if symbol not in self.current_candles:
                self.current_candles[symbol] = {
                    'symbol': symbol,
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'volume': volume,
                    'start_time': candle_start,
                    'end_time': candle_start + timedelta(seconds=self.timeframe_seconds),
                    'tick_count': 1
                }
            else:
                current_candle = self.current_candles[symbol]
                
                # Check if we need to close current candle and start new one
                if timestamp >= current_candle['end_time']:
                    # Complete the current candle
                    completed_candle = current_candle.copy()
                    self.completed_candles[symbol].append(completed_candle)
                    
                    # Start new candle
                    self.current_candles[symbol] = {
                        'symbol': symbol,
                        'open': price,
                        'high': price,
                        'low': price,
                        'close': price,
                        'volume': volume,
                        'start_time': candle_start,
                        'end_time': candle_start + timedelta(seconds=self.timeframe_seconds),
                        'tick_count': 1
                    }
                    
                    self.logger.debug(f"Completed {self.timeframe_minutes}min candle for {symbol}: O:{completed_candle['open']:.2f} H:{completed_candle['high']:.2f} L:{completed_candle['low']:.2f} C:{completed_candle['close']:.2f}")
                    return completed_candle
                else:
                    # Update current candle
                    current_candle['high'] = max(current_candle['high'], price)
                    current_candle['low'] = min(current_candle['low'], price)
                    current_candle['close'] = price
                    current_candle['volume'] = volume
                    current_candle['tick_count'] += 1
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error processing tick for {symbol}: {e}")
            return None
    
    def _get_candle_start_time(self, timestamp: datetime) -> datetime:
        """Calculate the start time of the candle for given timestamp"""
        # Round down to nearest timeframe boundary
        minutes = (timestamp.minute // self.timeframe_minutes) * self.timeframe_minutes
        return timestamp.replace(minute=minutes, second=0, microsecond=0)
    
    def get_latest_candles(self, symbol: str, count: int = 10) -> List[Dict]:
        """Get latest completed candles for a symbol"""
        if symbol in self.completed_candles:
            return list(self.completed_candles[symbol])[-count:]
        return []
    
    def get_current_candle(self, symbol: str) -> Optional[Dict]:
        """Get current incomplete candle for a symbol"""
        return self.current_candles.get(symbol)

class HeikinAshiConverter:
    """Converts regular candles to Heikin Ashi candles"""
    
    def __init__(self):
        self.ha_candles: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.logger = logging.getLogger(__name__)
    
    def convert_candle(self, symbol: str, candle: Dict) -> Dict:
        """Convert a regular candle to Heikin Ashi"""
        try:
            open_price = float(candle['open'])
            high_price = float(candle['high'])
            low_price = float(candle['low'])
            close_price = float(candle['close'])
            
            # Get previous HA candle
            prev_ha = None
            if symbol in self.ha_candles and len(self.ha_candles[symbol]) > 0:
                prev_ha = self.ha_candles[symbol][-1]
            
            # Calculate Heikin Ashi values
            if prev_ha is None:
                # First candle
                ha_close = (open_price + high_price + low_price + close_price) / 4
                ha_open = (open_price + close_price) / 2
            else:
                ha_close = (open_price + high_price + low_price + close_price) / 4
                ha_open = (prev_ha['ha_open'] + prev_ha['ha_close']) / 2
            
            ha_high = max(high_price, ha_open, ha_close)
            ha_low = min(low_price, ha_open, ha_close)
            
            ha_candle = {
                'symbol': symbol,
                'timestamp': candle.get('start_time', datetime.now()),
                'ha_open': ha_open,
                'ha_high': ha_high,
                'ha_low': ha_low,
                'ha_close': ha_close,
                'volume': candle.get('volume', 0),
                'original_open': open_price,
                'original_high': high_price,
                'original_low': low_price,
                'original_close': close_price
            }
            
            # Store the HA candle
            self.ha_candles[symbol].append(ha_candle)
            
            self.logger.debug(f"HA Candle for {symbol}: O:{ha_open:.2f} H:{ha_high:.2f} L:{ha_low:.2f} C:{ha_close:.2f}")
            return ha_candle
            
        except Exception as e:
            self.logger.error(f"Error converting to Heikin Ashi for {symbol}: {e}")
            return candle
    
    def get_latest_ha_candles(self, symbol: str, count: int = 10) -> List[Dict]:
        """Get latest Heikin Ashi candles for a symbol"""
        if symbol in self.ha_candles:
            return list(self.ha_candles[symbol])[-count:]
        return []

class WebSocketManager:
    """Enhanced WebSocket Manager with improved error handling and monitoring"""
    
    def __init__(self, api_key: str, access_token: str):
        self.api_key = api_key
        self.access_token = access_token
        self.logger = logging.getLogger(__name__)
        
        # Check if Upstox SDK is available
        if not UPSTOX_SDK_AVAILABLE:
            raise ImportError("upstox-python-sdk is required for websocket functionality. Install with: pip install upstox-python-sdk")
        
        # Initialize components
        self.candle_aggregator = CandleAggregator(timeframe_minutes=3)
        self.ha_converter = HeikinAshiConverter()
        
        # WebSocket connections
        self.market_streamer = None
        self.portfolio_streamer = None
        
        # Callbacks
        self.on_tick_callback: Optional[Callable] = None
        self.on_candle_callback: Optional[Callable] = None
        self.on_ha_candle_callback: Optional[Callable] = None
        self.on_order_update_callback: Optional[Callable] = None
        self.on_error_callback: Optional[Callable] = None
        
        # Subscribed instruments
        self.subscribed_instruments: List[str] = []
        
        # Connection status
        self.is_connected = False
        self.connection_thread = None

         # Connection state
        self.is_connected = False
        self.last_data_received = datetime.now()
        self.connection_attempts = 0
        self.max_reconnection_attempts = 5
        
        # Data storage
        self.latest_candles: Dict[str, List[Dict]] = {}
        self.latest_ha_candles: Dict[str, List[Dict]] = {}

        
    def set_callbacks(self, on_tick=None, on_candle=None, on_ha_candle=None, 
                     on_order_update=None, on_error=None):
        """Set callback functions for different events"""
        self.on_tick_callback = on_tick
        self.on_candle_callback = on_candle
        self.on_ha_candle_callback = on_ha_candle
        self.on_order_update_callback = on_order_update
        self.on_error_callback = on_error
        
        self.logger.info("WebSocket callbacks configured")
    
    def subscribe_instruments(self, instruments: List[str]):
        """Subscribe to instrument data"""
        self.subscribed_instruments = instruments
        self.logger.info(f"Subscribed to instruments: {instruments}")

    def start_market_stream(self):
        """Start market data websocket stream"""
        try:
            if not self.subscribed_instruments:
                self.logger.warning("No instruments subscribed for market data")
                return
            
            # Configure Upstox client
            configuration = upstox_client.Configuration()
            configuration.access_token = self.access_token
            
            # Initialize market data streamer
            self.market_streamer = upstox_client.MarketDataStreamerV3(
                upstox_client.ApiClient(configuration),
                self.subscribed_instruments,
                "full"  # Full market data
            )
            
            # Set up event handlers
            self.market_streamer.on("open", self._on_market_open)
            self.market_streamer.on("message", self._on_market_message)
            self.market_streamer.on("error", self._on_market_error)
            self.market_streamer.on("close", self._on_market_close)
            
            # Enable auto-reconnect
            self.market_streamer.auto_reconnect(True, 10, 3)
            
            # Connect
            self.market_streamer.connect()
            self.logger.info("Market data websocket connection initiated")
            
        except Exception as e:
            self.logger.error(f"Failed to start market stream: {e}")
    
    def start_portfolio_stream(self):
        """Start portfolio/order updates websocket stream"""
        try:
            # Configure Upstox client
            configuration = upstox_client.Configuration()
            configuration.access_token = self.access_token
            
            # Initialize portfolio data streamer
            self.portfolio_streamer = upstox_client.PortfolioDataStreamer(
                upstox_client.ApiClient(configuration)
            )
            
            # Set up event handlers
            self.portfolio_streamer.on("open", self._on_portfolio_open)
            self.portfolio_streamer.on("message", self._on_portfolio_message)
            self.portfolio_streamer.on("error", self._on_portfolio_error)
            self.portfolio_streamer.on("close", self._on_portfolio_close)
            
            # Enable auto-reconnect
            self.portfolio_streamer.auto_reconnect(True, 10, 3)
            
            # Connect
            self.portfolio_streamer.connect()
            self.logger.info("Portfolio data websocket connection initiated")
            
        except Exception as e:
            self.logger.error(f"Failed to start portfolio stream: {e}")
    
    def start_all_streams(self):
        """Start all WebSocket streams with enhanced error handling"""
        try:
            self.logger.info("Starting WebSocket streams...")
            self.start_market_stream()
            self.start_portfolio_stream()
            self.is_connected = True
            self.logger.info("WebSocket streams started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start WebSocket streams: {e}")
            if self.on_error_callback:
                asyncio.create_task(self.on_error_callback(f"Failed to start streams: {str(e)}"))
    
    def stop_all_streams(self):
        """Stop all WebSocket streams"""
        try:
            self.logger.info("Stopping WebSocket streams...")
            
            if self.market_streamer:
                try:
                    self.market_streamer.disconnect()
                except:
                    pass
                self.market_streamer = None
                
            if self.portfolio_streamer:
                try:
                    self.portfolio_streamer.disconnect()
                except:
                    pass
                self.portfolio_streamer = None
                
            self.is_connected = False
            self.logger.info("WebSocket streams stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping WebSocket streams: {e}")
    
    # Market Data Event Handlers
    def _on_market_open(self):
        """Called when market websocket connection opens"""
        self.logger.info("Websocket connected")
        self.logger.info("Market data websocket connected")
    
    def _on_market_message(self, message):
        """Process incoming market data"""
        try:
            # Parse market data message
            if isinstance(message, dict):
                feeds = message.get('feeds', {})
                
                for instrument_key, data in feeds.items():
                    ltpc = data.get('ltpc', {})
                    if ltpc:
                        # Extract tick data
                        tick_data = {
                            'instrument_key': instrument_key,
                            'ltp': ltpc.get('ltp'),
                            'volume': ltpc.get('vol', 0),
                            'timestamp': datetime.now()
                        }
                        
                        # Call tick callback
                        if self.on_tick_callback:
                            asyncio.create_task(self.on_tick_callback(tick_data))
                        
                        # Process candle aggregation
                        symbol = self._get_symbol_from_key(instrument_key)
                        completed_candle = self.candle_aggregator.process_tick(symbol, tick_data)
                        
                        if completed_candle:
                            # Call candle callback
                            if self.on_candle_callback:
                                asyncio.create_task(self.on_candle_callback(completed_candle))
                            
                            # Convert to Heikin Ashi
                            ha_candle = self.ha_converter.convert_candle(symbol, completed_candle)
                            
                            # Call HA candle callback
                            if self.on_ha_candle_callback:
                                asyncio.create_task(self.on_ha_candle_callback(ha_candle))
            
        except Exception as e:
            self.logger.error(f"Error processing market message: {e}")
    
    def _on_market_error(self, error):
        """Called when market websocket encounters an error"""
        self.logger.error(f"Market websocket error: {error}")
    
    def _on_market_close(self):
        """Called when market websocket connection closes"""
        self.logger.warning("Market data websocket connection closed")
    
    # Portfolio Data Event Handlers
    def _on_portfolio_open(self):
        """Called when portfolio websocket connection opens"""
        self.logger.info("Websocket connected")
        self.logger.info("Portfolio data websocket connected")
    
    def _on_portfolio_message(self, message):
        """Process incoming portfolio/order updates"""
        try:
            if self.on_order_update_callback:
                asyncio.create_task(self.on_order_update_callback(message))
        except Exception as e:
            self.logger.error(f"Error processing portfolio message: {e}")
    
    def _on_portfolio_error(self, error):
        """Called when portfolio websocket encounters an error"""
        self.logger.error(f"Portfolio websocket error: {error}")
    
    def _on_portfolio_close(self):
        """Called when portfolio websocket connection closes"""
        self.logger.warning("Portfolio data websocket connection closed")
    
    def _get_symbol_from_key(self, instrument_key: str) -> str:
        """Extract symbol from instrument key"""
        # Example: NSE_FO|50201 -> extract meaningful symbol
        parts = instrument_key.split('|')
        if len(parts) > 1:
            return parts[1]
        return instrument_key
    
    def get_latest_candles(self, symbol: str, count: int = 50) -> List[Dict]:
        """Get latest candles for a symbol"""
        return self.candle_aggregator.get_latest_candles(symbol, count)
    
    def get_latest_ha_candles(self, symbol: str, count: int = 50) -> List[Dict]:
        """Get latest Heikin Ashi candles for a symbol"""
        return self.ha_converter.get_latest_ha_candles(symbol, count)
    
    def get_connection_status(self) -> Dict:
        """Get current connection status"""
        return {
            'is_connected': self.is_connected,
            'last_data_received': self.last_data_received,
            'connection_attempts': self.connection_attempts,
            'subscribed_instruments': getattr(self, 'subscribed_instruments', [])
        }
    
    def get_current_candle(self, symbol: str) -> Optional[Dict]:
        """Get current incomplete candle for a symbol"""
        return self.candle_aggregator.get_current_candle(symbol)