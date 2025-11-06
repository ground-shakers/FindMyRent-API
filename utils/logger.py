"""Universal logfire for the application."""

import logfire
from logging import getLogger

# Create a universal logfire instance that can be imported anywhere
logger = getLogger("FindMyRent")


# Also create a convenience function for getting logfire with context
def get_logfire(name: str = "FindMyRent"):
    """Get a logfire instance with optional context name."""
    return getLogger(name)


def instrument_libraries():
    """Instrument common libraries for better observability."""
    logfire.instrument_httpx()
    logfire.instrument_pymongo()
    logfire.instrument_redis()