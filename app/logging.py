import logging
import sys

# ANSI escape codes for beautiful coloring in terminal console
class ColoredFormatter(logging.Formatter):
    colors = {
        logging.DEBUG: "\033[36m",    # Cyan
        logging.INFO: "\033[32m",     # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",    # Red
        logging.CRITICAL: "\033[41m"  # Red Background
    }
    reset = "\033[0m"

    def format(self, record):
        color = self.colors.get(record.levelno, self.reset)
        log_fmt = f"{color}%(asctime)s [%(levelname)s] %(name)s - %(message)s{self.reset}"
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)

# Initialize and configure logger
logger = logging.getLogger("legalmove")
logger.setLevel(logging.INFO)

# Avoid duplicate handlers if imported/configured multiple times
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColoredFormatter())
    logger.addHandler(handler)
