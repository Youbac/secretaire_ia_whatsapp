import logging
from typing import Optional
from app.services.gemini import GeminiService
from app.services.sheets import GoogleSheetsService

logger = logging.getLogger(__name__)

class SalesAgent:
    """
    Handles interactions with external contacts (prospects, clients, strangers).
    Goal: Qualify leads, provide information, escalate when necessary.
    """
    
    SYSTEM_PROMPT = """
    You are the Virtual Assistant for ICFootball Club & Agency.
    You are speaking to a potential customer, prospect, or external contact.
    
    Your Mission:
    1. **Welcome warmly** - Make them feel valued immediately.
    2. **Qualify the need** - Are they looking to:
       - Play soccer/futsal? (Direct them to GoodRec app or website)
       - Organize an event/league? (Gather details: size, location, timeline)
       - Partner with us? (Get company name, proposal summary)
       - Other inquiry? (Clarify and note it)
    3. **Gather contact info** - If you don't have their name/email, politely ask for it.
    4. **Never overpromise** - Do not commit to prices, dates, or specific services without human validation.
    5. **Escalate smartly** - If the request is complex, say: "Let me connect you with our team. They'll follow up within 24 hours."
    
    Tone: Friendly, Professional, Sporty, Energetic.
    Language: Detect the user's language (English/French) and reply in the same language.
    
    Format: Keep messages concise (2-4 sentences max). This is WhatsApp, not email.
    """
    
    def __init__(self, gemini_service: GeminiService, sheets_service: GoogleSheetsService):
        self.gemini = gemini_service
        self.sheets = sheets_service

    async def process_message(self, sender_id: str, message_text: str, conversation_history: str) -> str:
        """
        Processes an incoming message from a potential customer.
        
        Args:
            sender_id: Phone number of the sender.
            message_text: The actual message content.
            conversation_history: Recent chat history for context.
        
        Returns:
            The AI-generated response.
        """
        full_context = (
            f"Conversation History:\n{conversation_history}\n\n"
            f"New message from {sender_id}:\n{message_text}"
        )
        
        response = await self.gemini.generate_response(
            system_instruction=self.SYSTEM_PROMPT,
            user_message=full_context
        )
        
        # Optional: Log this interaction to Google Sheets for CRM tracking
        await self.sheets.log_customer_interaction(
            customer_phone=sender_id,
            message=message_text,
            agent_type="SALES"
        )
        
        return response
