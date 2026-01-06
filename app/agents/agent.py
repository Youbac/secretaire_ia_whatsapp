import logging
import json
from app.services.gemini import GeminiService

logger = logging.getLogger(__name__)

class FinanceAnalyst:
    """
    Extrait des transactions financières structurées depuis une conversation en vrac.
    """
    
    SYSTEM_PROMPT = """
    Tu es l'Expert Comptable IA de l'agence.
    Ta mission : Analyser les messages du groupe 'Dépenses' et extraire chaque transaction.

    Règles d'extraction :
    1. Repère tout ce qui ressemble à une dépense ou un revenu (Montant + Motif).
    2. Catégorise intelligemment (ex: "Équipement", "Marketing", "Terrain", "Transport", "Autre").
    3. Identifie qui a payé (l'expéditeur du message).
    
    Sortie STRICTE au format JSON (Liste d'objets) :
    [
      {
        "date": "JJ/MM/AAAA",
        "montant": 120.50,
        "devise": "USD" ou "EUR",
        "categorie": "Marketing",
        "description": "Pub Facebook",
        "paye_par": "Vincent"
      }
    ]
    Si aucun montant n'est trouvé, renvoie une liste vide [].
    Ne mets PAS de markdown (```json), juste le JSON brut.
    """
    
    def __init__(self, gemini_service: GeminiService):
        self.gemini = gemini_service

    async def extract_transactions(self, conversation_text: str) -> list:
        """
        Retourne une liste de dicts prêts à être insérés dans Google Sheets.
        """
        response_text = await self.gemini.generate_response(self.SYSTEM_PROMPT, conversation_text)
        
        # Nettoyage basique au cas où l'IA mettrait du markdown
        cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
        
        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            logger.error(f"❌ Erreur parsing JSON Finance: {response_text}")
            return []
