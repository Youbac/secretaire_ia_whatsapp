import logging
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from config import Config

# Configuration du logger
logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        if not Config.GEMINI_API_KEY:
            logger.error("❌ GEMINI_API_KEY manquante dans la configuration.")
            raise ValueError("GEMINI_API_KEY is required.")
            
        genai.configure(api_key=Config.GEMINI_API_KEY)
        
        # Configuration du modèle Flash pour la rapidité et le contexte
        self.model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            generation_config=genai.GenerationConfig(
                temperature=0.3,      # Créatif mais pas délirant
                top_p=0.8,
                top_k=40,
                max_output_tokens=1024,
            ),
            # On réduit les blocages de sécurité pour éviter les faux positifs sur des discussions pro
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
        )

    async def generate_response(self, system_instruction: str, user_message: str) -> str:
        """
        Génère une réponse en utilisant le contexte fourni.
        
        Args:
            system_instruction: Le rôle et les règles (System Prompt).
            user_message: Le dernier message de l'utilisateur (ou l'historique concaténé).
        """
        try:
            # On construit le prompt complet
            full_prompt = f"{system_instruction}\n\nUser: {user_message}"
            
            # Appel asynchrone (non bloquant)
            response = await self.model.generate_content_async(full_prompt)
            
            if not response.text:
                logger.warning("⚠️ Réponse vide reçue de Gemini.")
                return "..."

            return response.text.strip()

        except Exception as e:
            logger.error(f"❌ Erreur critique Gemini : {str(e)}", exc_info=True)
            # Fallback élégant pour ne pas planter le webhook
            return "Je rencontre un problème technique momentané. Je reviens vers vous rapidement."

