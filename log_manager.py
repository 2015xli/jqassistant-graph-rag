import logging
import sys
import multiprocessing as mp

def is_main_process():
    return mp.current_process().name == "MainProcess"

# --- 1. Custom Filter Classes ---

class DebugOnlyFilter(logging.Filter):
    """Passes ONLY messages with an exact level of DEBUG."""
    def filter(self, record):
        return record.levelno == logging.DEBUG


class InfoAndUpFilter(logging.Filter):
    """Passes ONLY messages with INFO and higher."""
    def filter(self, record):
        return record.levelno >= logging.INFO


# --- 2. Public initialization function ---

_initialized = False  # Prevent re-initializing when multiple modules import


def init_logging(log_file: str = "debug.log", console_level: str = "INFO"):
    """
    Initializes the logging configuration for the application.
    """
    # Root logger setup
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all messages

    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console Handler (prints INFO and above to stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File Handler (prints DEBUG and above to a file)
    try:
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        logging.error(f"Failed to initialize file logger at {log_file}: {e}")

    global _initialized
    if _initialized:
        return  # Avoid double handlers and duplicated output

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Application logger (__main__ OR callers)
    app_logger = logging.getLogger(__name__)
    app_logger.setLevel(logging.DEBUG)

    # --- Handlers ---

    # Console handler: INFO and above
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(InfoAndUpFilter())
    stdout_handler.setFormatter(
        logging.Formatter('%(asctime)s - [%(levelname)s] %(message)s')
    )
    # Attach handlers
    root_logger.addHandler(stdout_handler)

    # File handler: DEBUG only
    if is_main_process():
        file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.addFilter(DebugOnlyFilter())
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] %(message)s')
        )

        # Attach handlers
        root_logger.addHandler(file_handler)

    _initialized = True