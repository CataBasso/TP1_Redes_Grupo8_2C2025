"""
Centralized logging service for the file transfer application.
Handles verbose and quiet modes based on command line flags.
"""

import sys
from datetime import datetime


class Logger:
    """
    Centralized logger that respects verbose and quiet flags.
    
    Modes:
    - Normal: Shows regular operational messages
    - Verbose (-v): Shows detailed debug information
    - Quiet (-q): Shows only errors and critical messages
    """
    
    def __init__(self, verbose=False, quiet=False):
        self.verbose = verbose
        self.quiet = quiet
    
    def _log(self, level, message):
        """Internal logging method with timestamp."""
        if self.quiet and level not in ['ERROR', 'CRITICAL']:
            return
        
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted_msg = f"[{timestamp}] {level}: {message}"
        
        if level in ['ERROR', 'CRITICAL']:
            print(formatted_msg, file=sys.stderr)
        else:
            print(formatted_msg)
    
    def info(self, message):
        """Log informational messages (normal output)."""
        if not self.quiet:
            self._log("INFO", message)
    
    def debug(self, message):
        """Log debug messages (only in verbose mode)."""
        if self.verbose:
            self._log("DEBUG", message)
    
    def error(self, message):
        """Log error messages (always shown unless specifically suppressed)."""
        self._log("ERROR", message)
    
    def critical(self, message):
        """Log critical messages (always shown)."""
        self._log("CRITICAL", message)
    
    def verbose_info(self, message):
        """Log detailed information (only in verbose mode)."""
        if self.verbose:
            self._log("VERBOSE", message)


# Global logger instance - will be initialized by main scripts
logger = None


def init_logger(verbose=False, quiet=False):
    """Initialize the global logger with the specified verbosity settings."""
    global logger
    logger = Logger(verbose=verbose, quiet=quiet)
    return logger


def get_logger():
    """Get the global logger instance."""
    global logger
    if logger is None:
        # Default to normal mode if not initialized
        logger = Logger()
    return logger