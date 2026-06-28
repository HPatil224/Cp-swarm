import logging
import sys
from pathlib import Path
from config.settings import settings

def configure_logging(log_level_str: str = "INFO", log_file_path: Path | None = None):
    """
    Sets up application-wide logging with console and file handlers.
    """
    # Map string log level to logging constants
    level = getattr(logging, log_level_str.upper(), logging.INFO)
    
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    
    if log_file_path:
        try:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(log_file_path, encoding='utf-8'))
        except Exception:
            # Fallback if log directory/file cannot be created
            pass
        
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
        force=True
    )

# Automatically configure logging on module import
import os
configure_logging(
    log_level_str=os.environ.get("LOG_LEVEL", "INFO"),
    log_file_path=settings.paths.logs_dir / "cp_swarm.log"
)
