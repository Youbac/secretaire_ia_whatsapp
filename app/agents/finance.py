import logging
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any

# Services Centralisés (Architecture Propre)
from app.services.gemini import GeminiService
from app.services.sheets import GoogleSheetsService
from app.services.firestore import get_new_messages_only, mark_chat_as_processed

# Configuration
from config import settings

logger = logging.getLogger(__name__)

class FinanceAnalyst:
    """
    Agent spécialisé dans l'analyse financière.
    Il lit les messages Firestore, extrait les transactions via Gemini,
    et les insère dans Google Sheets via le Service centralisé.
    """

    # ID du groupe Whatsapp "Finance" (À mettre idéalement dans config.py, mais gardé ici pour l'instant)
    CHAT_ID = "-zeA_LzlUnS3nCeRyIdS5Q"

    def __init__(self, gemini_service: GeminiService, sheets_service: GoogleSheetsService):
        """
        Injection de dépendances : On lui donne les outils dont il a besoin.
        """
        self.gemini = gemini_service
        self.sheets = sheets_service

    async def run_analysis(self) -> str:
        """
        Pipeline principal : Lecture DB -> Analyse IA -> Ecriture Sheets.
        """
        logger.info(f"💰 [Finance] Démarrage de l'analyse pour le chat {self.CHAT_ID}...")

        # 1. Récupération des messages NON TRAITÉS depuis Firestore
        # (Plus besoin d'appeler l'API Unipile, on a déjà les données !)
        conversation_text = get_new_messages_only(self.CHAT_ID)
        
        if not conversation_text:
            logger.info("📭 [Finance] Pas de nouveaux messages à analyser.")
            return "Pas de nouveaux messages."

        # 2. Analyse IA (Extraction JSON)
        transactions = await self._extract_transactions(conversation_text)
        
        if not transactions:
            # Si on a lu des messages mais trouvé aucune transaction, on marque quand même comme lu
            mark_chat_as_processed(self.CHAT_ID)
            return "Messages lus, aucune transaction détectée."

        # 3. Sauvegarde dans Google Sheets
        success_count = await self._save_to_sheets(transactions)

        # 4. Marquage des messages comme "Traités" dans Firestore
        if success_count > 0:
            mark_chat_as_processed(self.CHAT_ID)
            return f"✅ Succès : {success_count} transactions sauvegardées."
        else:
            return "⚠️ Erreur lors de la sauvegarde Sheets."

    async def _extract_transactions(self, text: str) -> List[Dict[str, Any]]:
        """Demande à Gemini d'extraire les données structurées."""
        
        system_prompt = """
        Tu es un Expert Comptable rigoureux.
        Ta mission : Extraire les transactions financières de cette conversation WhatsApp.
        
        Règles :
        1. Ignore les discussions hors-sujet.
        2. Extrais : Date, Type (DEPENSE/RECETTE), Montant, Description, Qui a payé.
        3. Si la date n'est pas explicite, utilise la date du jour.
        
        Format de sortie STRICT : Un tableau JSON uniquement.
        Exemple :
        [
            {"date": "2023-10-27", "type": "DEPENSE", "montant": 45.50, "description": "Restaurant client", "qui": "Vincent"}
        ]
        """

        try:
            # Appel au service Gemini centralisé (Gère les retries tout seul)
            response = await self.gemini.generate_response(
                system_instruction=system_prompt,
                user_message=f"Conversation à analyser :\n{text}"
            )

            # Nettoyage du Markdown (Gemini aime bien mettre ```json ... ```)
            cleaned_json = response.replace("```json", "").replace("```", "").strip()
            
            # Parsing
            return json.loads(cleaned_json)

        except json.JSONDecodeError:
            logger.error(f"❌ [Finance] L'IA a renvoyé un JSON invalide : {response}")
            return []
        except Exception as e:
            logger.error(f"❌ [Finance] Erreur analyse IA : {e}")
            return []

    async def _save_to_sheets(self, transactions: List[Dict[str, Any]]) -> int:
        """Pousse les données vers le Sheet Finance."""
        if not settings.FINANCE_SHEET_ID:
            logger.error("❌ [Finance] ID du Sheet non configuré dans settings.")
            return 0

        count = 0
        for t in transactions:
            row_values = [
                t.get("date", datetime.now().strftime("%Y-%m-%d")),
                t.get("type", "AUTRE"),
                t.get("montant", 0),
                t.get("description", "?"),
                t.get("qui", "Inconnu")
            ]
            
            # Utilisation du Service Sheets (Gère les quotas API et retries)
            success = await self.sheets.append_row(
                spreadsheet_id=settings.FINANCE_SHEET_ID,
                range_name="Sheet1!A:E", # Assurez-vous que c'est le bon onglet
                values=row_values
            )
            
            if success:
                count += 1
        
        return count

# --- Zone de Test (Execution directe) ---
if __name__ == "__main__":
    # Pour tester ce fichier seul, on doit initialiser les services manuellement
    import asyncio
    
    async def main_test():
        logging.basicConfig(level=logging.INFO)
        
        # On instancie les services
        gemini = GeminiService()
        sheets = GoogleSheetsService()
        
        # On lance l'agent
        agent = FinanceAnalyst(gemini, sheets)
        result = await agent.run_analysis()
        print(f"Rapport : {result}")

    asyncio.run(main_test())