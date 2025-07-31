# ==================== main.py (BIDIRECTIONAL MODE) ====================
#!/usr/bin/env python3
"""
Main entry point for the trading bot with BIDIRECTIONAL strategy
"""
import os
import sys
import asyncio
from pathlib import Path
import logging
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.trading_bot import TradingBot
from config.settings import get_settings
from config.logging_config import setup_logging

async def main():
    """Enhanced main function with BIDIRECTIONAL strategy"""
    try:
        # Setup logging
        setup_logging()
        logger = logging.getLogger(__name__)
        
        # Load configuration
        settings = get_settings()
        
        logger.info("Starting AstraRise Trading Bot - BIDIRECTIONAL Mode")
        
        # Initialize trading bot
        bot = TradingBot(settings)
        
        # ADD BIDIRECTIONAL PINE SCRIPT STRATEGY
        from src.strategy.enhanced_pine_script_strategy import EnhancedPineScriptStrategy
        
        bidirectional_strategy = EnhancedPineScriptStrategy("bidirectional_pine_script", {
            'strategy_id': 'Bidirectional_Pine_Script',
            'trading_mode': 'BIDIRECTIONAL',  # This enables both CE and PE
            'adx_length': 14,
            'adx_threshold': 20,
            'strong_candle_threshold': 0.6,
            'max_positions': 2,  # Can hold both CE and PE positions
            'total_capital': 20000,
            'max_risk_pct': 0.75,
            'risk_per_trade': 10000  # Split capital between CE and PE
        })
        
        bot.add_strategy(bidirectional_strategy)
        
        logger.info(f"Strategy loaded: {bidirectional_strategy.name}")
        logger.info(f"Trading Mode: BIDIRECTIONAL (CE + PE)")
        logger.info(f"Capital: Rs.20,000 | Max Positions: 2")
        logger.info(f"Can trade both CALLS and PUTS simultaneously")
        
        # Run the bot
        await bot.run()
        
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error starting bot: {e}")
        raise

if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    
if __name__ == "__main__":
    asyncio.run(main())