import logging
import json
from app.services.gemini import GeminiService

logger = logging.getLogger(__name__)

class SalesAnalyst:
    """
    Analyzes customer conversations to extract intent, status, and lead data.
    """

    def __init__(self, gemini_service: GeminiService):
        self.gemini = gemini_service

    async def analyze_conversation(self, chat_id: str, messages_text: str) -> str:
        """
        Sends the conversation history to Gemini and returns a structured summary.
        """
        if not messages_text or len(messages_text) < 10:
            return "⚠️ Conversation too short or empty."

        system_instruction = """
        You are the CRM Analyst for a sports agency.
        Analyze the WhatsApp conversation provided.
        
        Output MUST be a JSON object with these keys:
        - "intent": Short summary of what they wanted.
        - "status": "RESOLVED" or "ACTION_REQUIRED".
        - "sentiment": "POSITIVE", "NEUTRAL", or "NEGATIVE".
        - "summary": A 1-sentence summary for the daily report.
        
        Do not use Markdown. Just raw JSON.
        """

        try:
            # We call the robust generate_response method from GeminiService
            response_text = await self.gemini.generate_response(
                system_instruction=system_instruction,
                user_message=f"Conversation ID: {chat_id}\n\n{messages_text}"
            )

            # Try to parse JSON to format it nicely for the Google Sheet
            try:
                # Clean up any potential markdown code blocks
                clean_text = response_text.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_text)
                
                # Format specific for Google Sheet cell (Human readable)
                formatted_output = (
                    f"[{data.get('status', 'UNK')}] {data.get('intent', '')}\n"
                    f"Sentiment: {data.get('sentiment', 'N/A')}\n"
                    f"📝 {data.get('summary', '')}"
                )
                return formatted_output

            except json.JSONDecodeError:
                # If AI returns plain text, just return it as is
                return response_text

        except Exception as e:
            logger.error(f"❌ Sales Analysis failed for {chat_id}: {e}")
            return "❌ Error during analysis."
