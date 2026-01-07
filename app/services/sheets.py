import logging
import asyncio
from typing import List, Any, Optional
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# We import the instance 'settings' which contains the logic and data
from config import settings

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    """
    Production-grade service for Google Sheets.
    Features:
    - Automatic Retries (Tenacity) for API failures.
    - Threaded execution for non-blocking Async.
    - Smart Auth (File vs Base64).
    """
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self):
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticates using the smart logic from Settings."""
        try:
            creds_data = settings.get_firebase_credentials()

            if not creds_data:
                raise ValueError("❌ No Firebase/Google credentials found in Settings.")

            # Load credentials based on type
            if isinstance(creds_data, dict):
                # Cloud Mode
                creds = Credentials.from_service_account_info(creds_data, scopes=self.SCOPES)
                logger.info("☁️ Google Sheets: Loaded from Base64 (Cloud Mode)")
            else:
                # Local Mode
                creds = Credentials.from_service_account_file(creds_data, scopes=self.SCOPES)
                logger.info(f"📂 Google Sheets: Loaded from file {creds_data}")

            self.service = build('sheets', 'v4', credentials=creds)
            logger.info("✅ Google Sheets service initialized.")

        except Exception as e:
            logger.critical(f"❌ Failed to initialize Google Sheets service: {e}")
            self.service = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HttpError, TimeoutError)),
        reraise=False  # Returns the result of the last attempt (False if failed)
    )
    async def append_row(self, spreadsheet_id: str, range_name: str, values: List[Any]) -> bool:
        """
        Appends a row with automatic retry on failure.
        """
        if not self.service:
            logger.error("⚠️ Sheets Service not ready.")
            return False

        body = {'values': [values]}

        def _blocking_request():
            return self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()

        try:
            # Run blocking call in a separate thread to keep bot responsive
            result = await asyncio.to_thread(_blocking_request)
            
            updates = result.get('updates', {})
            logger.debug(f"✅ Row added to {range_name}: {updates.get('updatedCells')} cells updated.")
            return True

        except HttpError as e:
            # Let Tenacity handle retries for 429/500, but log if it's a permanent 403
            if e.resp.status in [403, 404]:
                logger.error(f"❌ Permanent Google API Error (No Retry): {e}")
                raise e # Raise to stop retrying
            else:
                logger.warning(f"🔄 Sheets API temporary issue: {e}")
                raise e # Raise to trigger retry

        except Exception as e:
            logger.error(f"❌ Unexpected Error: {e}")
            raise e

    async def log_finance_transaction(self, date: str, type_: str, amount: float, description: str, who: str) -> bool:
        """Specific helper for Finance."""
        if not settings.FINANCE_SHEET_ID:
            logger.warning("⚠️ No FINANCE_SHEET_ID in settings.")
            return False

        return await self.append_row(
            spreadsheet_id=settings.FINANCE_SHEET_ID,
            range_name="Sheet1!A:E",
            values=[date, type_, amount, description, who]
        )

# Global Instance
sheets_service = GoogleSheetsService()
