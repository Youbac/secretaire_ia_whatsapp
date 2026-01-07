import requests
import gspread
import json
import logging
from typing import Optional, List, Dict, Any
from google import genai
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Import Settings
from config import settings

# Configure Logger
logger = logging.getLogger(__name__)

class FinanceAnalyst:
    """
    Agent responsible for analyzing financial discussions on WhatsApp
    and logging transactions into Google Sheets.
    Uses the new Google GenAI SDK.
    """

    def __init__(self):
        self._init_ai()
        self._init_sheets()
        
        # Target WhatsApp Conversation
        self.chat_id = "-zeA_LzlUnS3nCeRyIdS5Q" 

    def _init_ai(self):
        """Initializes the new Gemini Client."""
        try:
            self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
            self.model_name = settings.GEMINI_MODEL
        except Exception as e:
            logger.error(f"❌ [Finance] AI Init failed: {e}")
            self.client = None

    def _init_sheets(self):
        """Connects to Google Sheets using the centralized logic."""
        self.sheet = None
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds_data = settings.get_firebase_credentials()

            if not creds_data:
                logger.warning("⚠️ [Finance] No Firebase credentials found.")
                return

            if isinstance(creds_data, str):
                creds = ServiceAccountCredentials.from_json_keyfile_name(creds_data, scope)
            else:
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_data, scope)

            client = gspread.authorize(creds)
            
            if not settings.FINANCE_SHEET_ID:
                logger.warning("⚠️ [Finance] No Sheet ID configured.")
                return

            self.sheet = client.open_by_key(settings.FINANCE_SHEET_ID).sheet1
            logger.info("✅ [Finance] Connected to Google Sheet.")
            
        except Exception as e:
            logger.error(f"❌ [Finance] Sheet Connection failed: {e}")

    def get_recent_messages(self, limit=30) -> str:
        """Fetches raw messages from Unipile."""
        url = f"https://{settings.UNIPILE_DSN}/api/v1/chats/{self.chat_id}/messages"
        headers = {"X-API-Key": settings.UNIPILE_API_KEY}
        
        try:
            response = requests.get(url, headers=headers, params={"limit": limit}, timeout=10)
            if response.status_code != 200:
                logger.warning(f"⚠️ [Finance] WhatsApp API Error: {response.status_code}")
                return ""
            
            data = response.json()
            messages = data.get("items", [])
            history = []
            
            for msg in messages:
                if msg.get("type") == "text":
                    # Determine sender
                    is_me = msg.get("sender_id") == settings.UNIPILE_ACCOUNT_ID
                    sender = "Moi" if is_me else "Partenaire"
                    
                    timestamp = msg.get("timestamp", "")
                    text = msg.get("text", "")
                    history.append(f"[{timestamp}] {sender}: {text}")
            
            # Return chronological order
            return "\n".join(reversed(history))

        except Exception as e:
            logger.error(f"❌ [Finance] Fetch Messages failed: {e}")
            return ""

    def process_and_save(self) -> str:
        """Main Pipeline: Read -> Analyze -> Save."""
        
        # 1. Get Data
        logger.info("🔍 [Finance] Reading WhatsApp messages...")
        conversation = self.get_recent_messages()
        if not conversation:
            return "⚠️ Pas de messages trouvés ou erreur API."

        # 2. Analyze with Gemini (New SDK)
        logger.info("🧠 [Finance] Analyzing with Gemini...")
        prompt = f"""
        Role: Expert Comptable.
        Task: Extraire les transactions financières de cette conversation.
        
        Conversation:
        {conversation}
        
        Output Format: JSON Array ONLY.
        Keys: "date" (YYYY-MM-DD), "type" (DEPENSE/GAIN), "montant" (float), "description" (string), "qui" (string).
        
        If no transaction found, return [].
        Do not add markdown formatting like ```json.
        """

        try:
            if not self.client:
                return "❌ Erreur: Client AI non initialisé."

            # Synchrone call for simplicity in this script context
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            raw_text = response.text
            # Clean potential markdown
            clean_json = raw_text.replace("```json", "").replace("```", "").strip()
            
            transactions = json.loads(clean_json)

            if not transactions:
                return "✅ Aucune nouvelle transaction détectée."

            # 3. Save to Sheets
            if self.sheet:
                count = 0
                for t in transactions:
                    row = [
                        t.get("date", datetime.now().strftime("%Y-%m-%d")),
                        t.get("type", "UNKNOWN"),
                        t.get("montant", 0),
                        t.get("description", ""),
                        t.get("qui", "?")
                    ]
                    self.sheet.append_row(row)
                    count += 1
                return f"✅ Succès ! {count} transactions ajoutées."
            else:
                return "⚠️ Analyse réussie, mais Google Sheet inaccessible."

        except json.JSONDecodeError:
            logger.error(f"❌ [Finance] Invalid JSON from AI: {raw_text}")
            return "❌ Erreur: L'IA n'a pas renvoyé un JSON valide."
        except Exception as e:
            logger.error(f"❌ [Finance] Process failed: {e}")
            return f"❌ Erreur critique: {e}"

if __name__ == "__main__":
    # Test Run
    logging.basicConfig(level=logging.INFO)
    bot = FinanceAnalyst()
    print(bot.process_and_save())
