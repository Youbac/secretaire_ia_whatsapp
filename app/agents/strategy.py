import logging
from app.services.gemini import GeminiService

logger = logging.getLogger(__name__)

class StrategyAgent:
    """
    Handles interactions with founders (you and Vincent).
    Acts as an executive thinking partner and task manager.
    """
    
    SYSTEM_PROMPT = """
    You are the Executive AI Assistant for the agency's founders.
    You are speaking to one of the co-founders (equal partners running the business).
    
    Your Role:
    1. **Execute commands efficiently** - If they give you a task, confirm it's noted/done.
    2. **Summarize insights** - If they share information, structure it clearly.
    3. **Provide strategic input** - If they ask for an opinion, give a thoughtful perspective (but be concise).
    4. **Never waste their time** - Skip pleasantries. Get to the point.
    
    Tone: Professional, Direct, Collaborative (equal-to-equal, not boss-to-subordinate).
    Format: Ultra-concise. This is instant messaging, not a report.
    
    Examples of good responses:
    - "Noted. I've logged this as a priority task."
    - "Here's the summary: [3 bullet points]."
    - "Tracked. I'll remind you on Thursday."
    
    Bad responses (avoid these):
    - "Of course! I'd be delighted to assist you with..." (too formal/long)
    - "Let me know if there's anything else I can do!" (unnecessary)
    """
    
    def __init__(self, gemini_service: GeminiService):
        self.gemini = gemini_service

    async def process_message(self, founder_name: str, message_text: str, conversation_history: str) -> str:
        """
        Processes a message from a founder.
        
        Args:
            founder_name: "FOUNDER" or "COFOUNDER".
            message_text: The actual message content.
            conversation_history: Recent chat history for context.
        
        Returns:
            The AI-generated response.
        """
        full_context = (
            f"You are speaking to {founder_name}.\n\n"
            f"Conversation History:\n{conversation_history}\n\n"
            f"New message:\n{message_text}"
        )
        
        response = await self.gemini.generate_response(
            system_instruction=self.SYSTEM_PROMPT,
            user_message=full_context
        )
        
        return response
