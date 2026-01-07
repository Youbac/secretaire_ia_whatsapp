import logging
from app.services.gemini import GeminiService

logger = logging.getLogger(__name__)

class StrategyAnalyst:
    """
    Exclusive analysis of Founder discussions (You & Vincent).
    Extracts strategy, tasks, and business ideas.
    """
    
    def __init__(self, gemini_service: GeminiService):
        self.gemini = gemini_service

    async def analyze_founders_chat(self, conversation_text: str) -> str:
        """
        Analyzes the raw text exchange between founders.
        """
        # 1. Validation to save API calls
        if not conversation_text or len(conversation_text.strip()) < 20:
            return "∅ Pas d'échanges significatifs aujourd'hui."

        # 2. Advanced System Prompt
        system_instruction = """
        You are the Executive Secretary for the company founders.
        Your goal is to turn a chaotic WhatsApp conversation into a clear Business Report.

        Objectives:
        1. STRATEGY SUMMARY: Bullet points of key business topics discussed.
        2. ACTION ITEMS: Clear list of tasks assigned or mentioned (Who does What).
        3. IDEAS PARKING LOT: Good ideas mentioned but not yet acted upon.

        Constraints:
        - IGNORE personal chat ("lol", "food", "sports" unless business related).
        - Be concise and professional.
        - Use emojis for readability.

        Output Format:
        [STRATEGY]
        • Point 1
        • Point 2

        [ACTIONS]
        - [ ] Task A (Assigned to: Name)
        - [ ] Task B

        [IDEAS]
        • Idea 1
        """

        try:
            logger.info("👔 Analyzing Founders' Chat...")
            response = await self.gemini.generate_response(
                system_instruction=system_instruction, 
                user_message=conversation_text
            )
            return response

        except Exception as e:
            logger.error(f"❌ Strategy Analysis failed: {e}")
            return "❌ Erreur d'analyse stratégique."
