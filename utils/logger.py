"""Logger for the application.
"""
import logfire

import os

from dotenv import load_dotenv

import logfire
from logging import basicConfig, getLogger

load_dotenv()

logfire.configure(token=os.getenv("LOGFIRE_WRITE_TOKEN"))
basicConfig(handlers=[logfire.LogfireLoggingHandler()])

logger = getLogger(__name__)