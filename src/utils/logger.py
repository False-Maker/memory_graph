"""
Logger utility
"""
import logging
import sys
from pathlib import Path


def setup_logger(name: str = "memory_graph", level: str = "INFO"):
    """Setup logger"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger


# Default logger - 设置为 DEBUG 级别可以看到更多日志
logger = setup_logger(level="DEBUG")
