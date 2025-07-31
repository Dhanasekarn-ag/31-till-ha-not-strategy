# ==================== config/logging_config.py ====================
import logging
import logging.handlers
from pathlib import Path
from config.settings import get_settings
import logging
import sys


def setup_logging():
    """Setup logging configuration"""
    settings = get_settings()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler - detailed logs
    log_file = settings.logs_dir / "trading_bot.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler
    error_file = settings.logs_dir / "errors.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_file, maxBytes=5*1024*1024, backupCount=3
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)
    
    # Trading file handler - for trades and strategy logs
    trades_file = settings.logs_dir / "trades.log"
    trades_handler = logging.handlers.RotatingFileHandler(
        trades_file, maxBytes=5*1024*1024, backupCount=10
    )
    trades_handler.setLevel(logging.INFO)
    trades_handler.setFormatter(detailed_formatter)
    
    # Create trading logger
    trading_logger = logging.getLogger('trading')
    trading_logger.addHandler(trades_handler)
    trading_logger.setLevel(logging.INFO)
    
# Configure logging with UTF-8 encoding for emojis
class UTF8StreamHandler(logging.StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream)
        if hasattr(self.stream, 'reconfigure'):
            self.stream.reconfigure(encoding='utf-8')

# Replace console handler
def setup_utf8_logging():
    """Setup UTF-8 logging to handle emojis properly"""
    
    # Remove existing handlers
    logger = logging.getLogger()
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add UTF-8 compatible handlers
    file_handler = logging.FileHandler('logs/trading_bot.log', encoding='utf-8')
    console_handler = UTF8StreamHandler(sys.stdout)
    
    # Set format
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)
