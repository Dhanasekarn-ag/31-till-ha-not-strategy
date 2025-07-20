# ==================== config/logging_config.py ====================
import logging
import logging.handlers
from pathlib import Path
from config.settings import get_settings

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