# ==================== main_multi_strategy.py ====================
import asyncio
import logging
import os
from datetime import datetime
from config.settings import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/multi_strategy_bot.log'),
        logging.StreamHandler()
    ]
)

async def main():
    """Main function for multi-strategy trading bot"""
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("🚀 Starting Multi-Strategy AstraRise Trading Bot...")
        
        # Load settings
        settings = Settings()
        
        # Import multi-strategy bot
        from src.trading_bot import MultiStrategyTradingBot, StrategyConfigManager
        
        # Create bot instance
        bot = MultiStrategyTradingBot(settings)
        
        # Get strategy mode from environment or use default
        strategy_mode = os.getenv('STRATEGY_MODE', 'ALL')
        logger.info(f"🎯 Strategy Mode: {strategy_mode}")
        
        # Configure strategies
        config_manager = StrategyConfigManager()
        
        if strategy_mode == 'CE_ONLY':
            logger.info("📈 Configuring CE-only strategy")
            bot.add_strategy_config('CE_Pine_Script', config_manager.get_ce_only_config(1.0))
            
        elif strategy_mode == 'PE_ONLY':
            logger.info("📉 Configuring PE-only strategy")
            bot.add_strategy_config('PE_Pine_Script', config_manager.get_pe_only_config(1.0))
            
        elif strategy_mode == 'BIDIRECTIONAL':
            logger.info("🎯 Configuring bidirectional strategy")
            bot.add_strategy_config('Bidirectional_Pine_Script', config_manager.get_bidirectional_config(1.0))
            
        else:  # ALL strategies
            logger.info("🔥 Configuring all strategies (CE + PE + Bidirectional)")
            strategies_config = config_manager.get_all_strategies_config()
            for name, config in strategies_config.items():
                bot.add_strategy_config(name, config)
        
        # Initialize strategies
        bot.initialize_strategies()
        
        # Show configuration summary
        logger.info("📊 Multi-Strategy Configuration Summary:")
        for strategy_name, config in bot.strategy_configs.items():
            logger.info(f"   ✅ {strategy_name}: {config['trading_mode']} | Capital: Rs.{config['total_capital']:,}")
        
        # Send startup notification
        startup_message = f"""🚀 *Multi-Strategy AstraRise Bot Started*

📊 *Configuration:*
🎯 *Mode:* {strategy_mode}
💰 *Total Capital:* Rs.20,000
📈 *Strategies:* {len(bot.strategy_configs)}
⚡ *Trading Mode:* Paper Trading (Safe testing)

🔗 *Active Strategies:*"""
        
        for strategy_name, config in bot.strategy_configs.items():
            startup_message += f"\n   • {strategy_name} ({config['trading_mode']}) - Rs.{config['total_capital']:,}"
        
        startup_message += f"""

🕐 *Market Schedule:*
📅 *Date:* {datetime.now().strftime('%B %d, %Y')}
⏰ *Started:* {datetime.now().strftime('%I:%M:%S %p')}
📊 *Market Hours:* 9:15 AM - 3:30 PM IST

🎯 *Today's Goals:*
• Test multi-strategy Pine Script logic
• Compare CE vs PE vs Bidirectional performance
• Validate capital allocation across strategies
• Track individual strategy accuracy

Multi-strategy bot ready for action! 💪"""
        
        await bot.notifier.send_message(startup_message)
        
        # Override periodic update method for multi-strategy
        original_update = bot.send_periodic_telegram_update
        bot.send_periodic_telegram_update = bot.send_multi_strategy_status_update
        
        # Run the bot
        await bot.run()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())

# ==================== Usage Examples ====================

"""
# Run CE-only strategy:
STRATEGY_MODE=CE_ONLY python main_multi_strategy.py

# Run PE-only strategy:
STRATEGY_MODE=PE_ONLY python main_multi_strategy.py

# Run bidirectional strategy:
STRATEGY_MODE=BIDIRECTIONAL python main_multi_strategy.py

# Run all strategies simultaneously:
STRATEGY_MODE=ALL python main_multi_strategy.py
# or simply:
python main_multi_strategy.py
"""

# ==================== Quick Test Script ====================

async def test_strategy_configs():
    """Quick test of strategy configurations"""
    
    from src.trading_bot import StrategyConfigManager
    
    config_manager = StrategyConfigManager()
    
    print("🧪 Testing Strategy Configurations:")
    print("\n📈 CE-only Config:")
    ce_config = config_manager.get_ce_only_config()
    for key, value in ce_config.items():
        print(f"   {key}: {value}")
    
    print("\n📉 PE-only Config:")
    pe_config = config_manager.get_pe_only_config()
    for key, value in pe_config.items():
        print(f"   {key}: {value}")
    
    print("\n🎯 Bidirectional Config:")
    bidir_config = config_manager.get_bidirectional_config()
    for key, value in bidir_config.items():
        print(f"   {key}: {value}")
    
    print("\n✅ All configurations look good!")

# Uncomment to test configurations:
# asyncio.run(test_strategy_configs())