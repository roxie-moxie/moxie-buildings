import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///./moxie.db")
GOOGLE_SHEETS_ID: str = os.environ.get("GOOGLE_SHEETS_ID", "")
GOOGLE_SHEETS_KEY_PATH: str = os.environ.get("GOOGLE_SHEETS_KEY_PATH", "")
GOOGLE_SHEETS_TAB_NAME: str = os.environ.get("GOOGLE_SHEETS_TAB_NAME", "Buildings")
