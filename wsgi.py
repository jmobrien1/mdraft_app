import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app import create_app
app = create_app()
