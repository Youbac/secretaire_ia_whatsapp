import logging
from functools import lru_cache
from app.services.firestore import FirestoreService
from app.services.gemini import GeminiService
from app.services.sheets import GoogleSheetsService

logger = logging.getLogger(__name__)

# --- Singleton Instances (Lazy-Loaded) ---

@lru_cache()
def get_firestore_service() -> FirestoreService:
    """Returns a singleton instance of FirestoreService."""
    logger.info("🔧 Initializing FirestoreService...")
    return FirestoreService()

@lru_cache()
def get_gemini_service() -> GeminiService:
    """Returns a singleton instance of GeminiService."""
    logger.info("🔧 Initializing GeminiService...")
    return GeminiService()

@lru_cache()
def get_sheets_service() -> GoogleSheetsService:
    """Returns a singleton instance of GoogleSheetsService."""
    logger.info("🔧 Initializing GoogleSheetsService...")
    return GoogleSheetsService()

# Optional: Add Unipile service here when we create it
# @lru_cache()
# def get_unipile_service() -> UnipileService:
#     return UnipileService()
