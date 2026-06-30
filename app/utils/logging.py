import contextvars
import sys
from loguru import logger

# Context-local storage for log accumulation per request/transformation
request_logs = contextvars.ContextVar("request_logs", default=None)

class ContextLogsSink:
    def __init__(self):
        self.formatter = "{time:HH:mm:ss} | {level: <7} | {message}"

    def write(self, message):
        # Retrieve list for active context
        logs_list = request_logs.get()
        if logs_list is not None:
            # Strip newline and add to context
            logs_list.append(message.rstrip())

# Configure Loguru
# Remove default logger to avoid duplicate stdout logs
logger.remove()

# Add standard stdout logger
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

# Add the context sink
logger.add(
    ContextLogsSink().write,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="DEBUG"
)

def get_current_logs():
    return request_logs.get()
