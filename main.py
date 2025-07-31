# ==================== main.py ====================
#!/usr/bin/env python3
"""
Main entry point for the trading bot
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

def main():
    """Main function"""
    try:
        # Setup logging
        setup_logging()
        
        # Load configuration
        settings = get_settings()
        
        # Initialize and run bot
        bot = TradingBot(settings)
        
        # Run the bot
        asyncio.run(bot.run())
        
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
    main()