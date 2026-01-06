import logging
from typing import List, Dict, Any
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import Config

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    """Service for writing data to Google Sheets for tracking and reporting."""
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self):
        try:
            creds = Credentials.from_service_account_info(
                Config.FIREBASE_CREDENTIALS,  # Reuse Firebase service account (has Sheets permissions)
                scopes=self.SCOPES
            )
            self.service = build('sheets', 'v4', credentials=creds)
            logger.info("✅ Google Sheets service initialized.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Google Sheets service: {e}")
            raise e

    async def append_row(self, spreadsheet_id: str, range_name: str, values: List[Any]) -> bool:
        """
        Appends a single row to a Google Sheet.
        
        Args:
            spreadsheet_id: The ID of the Google Sheet (from the URL).
            range_name: The range to append to (e.g., "Sheet1!A:D").
            values: List of values to append as a row.
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            body = {
                'values': [values]
            }
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',  # Interprets numbers and dates
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            logger.info(f"✅ Appended row to sheet {spreadsheet_id}: {result.get('updates')}")
            return True
            
        except HttpError as e:
            logger.error(f"❌ Google Sheets API error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error appending to sheet: {e}")
            return False

    async def log_customer_interaction(self, customer_phone: str, message: str, agent_type: str) -> bool:
        """
        Convenience method to log a customer interaction.
        Adjust the spreadsheet_id and range to match your actual tracking sheet.
        """
        # TODO: Replace with your actual Google Sheet ID from Config
        spreadsheet_id = Config.CUSTOMER_LOG_SHEET_ID if hasattr(Config, 'CUSTOMER_LOG_SHEET_ID') else None
        
        if not spreadsheet_id:
            logger.warning("⚠️ No Customer Log Sheet ID configured. Skipping sheet logging.")
            return False
        
        from datetime import datetime
        timestamp = datetime.utcnow().isoformat()
        
        return await self.append_row(
            spreadsheet_id=spreadsheet_id,
            range_name="Sheet1!A:D",
            values=[timestamp, customer_phone, message[:100], agent_type]  # Truncate message to 100 chars
        )
