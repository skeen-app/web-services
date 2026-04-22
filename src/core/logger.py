import logging
import sys

def get_logger(name: str) -> logging.Logger:
    """
    Configures and returns a centralized logger.
    Useful for Cloud Run or local environments.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Create a console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)

        # Create a formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Prevent log propagation to the root logger which might lead to duplicated streams
        logger.propagate = False

    return logger
