import logging
import sys

def init_logging(log_level: str):
    """
    Initializes logging based on the specified level.
    Sets up a console handler.
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    # Set root logger level to capture everything
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG) # Capture all messages

    # Clear existing handlers to prevent duplicate output if called multiple times
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)

    # Console handler: User-specified level and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level) # Use user-specified level for console
    console_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] %(message)s'))
    root_logger.addHandler(console_handler)

    # Ensure the logger for this module also respects the level
    logging.getLogger(__name__).setLevel(numeric_level)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized with console level: {log_level.upper()}")
