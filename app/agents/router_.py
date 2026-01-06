import logging
from typing import Optional
from app.services.gemini import GeminiService
from app.services.firestore import FirestoreService
from app.schemas.webhook import UnipileMessage

logger = logging.getLogger(__name__)

class AgentRouter:
    def __init__(self, gemini_service: GeminiService, firestore_service: FirestoreService):
        self.gemini = gemini_service
        self.db = firestore_service
        
        # --- ROLE CONFIGURATION ---
        
        # Founders & Admins
        self.ADMINS = {
            "33768389721": "FOUNDER",     # You
            "15166422399": "COFOUNDER"    # Vincent
        }
        
        # Team Members
        self.EMPLOYEES = {
            "16463922789": "Jin",
            "13478245247": "Muna Brian",
            "13476955236": "Josiah",
            "13472184391": "Seb",
            "19292267037": "Jamyang",
            "19178346848": "Jovie",
            "19292823114": "Haznallah",
            "16468944629": "Brayant"
        }
        
        # Partners
        self.PARTNERS = {
            "17737708956": "GOODREC_OFFICIAL",
            "14125671447": "GOODREC_HOSTS"
        }
        
        # Ignored Numbers (Family/Private) - The bot will NEVER reply to these
        self.IGNORED_NUMBERS = {
            "33617785411", "33677798793", "21652699220", 
            "21620345271", "33651682434"
        }

    async def route_and_reply(self, message: UnipileMessage) -> Optional[str]:
        """
        Orchestrates the response: Identifies sender -> Selects System Prompt -> Generates AI Reply.
        Returns None if no reply should be sent (e.g., Family).
        """
        sender_id = message.sender_id
        chat_id = message.chat_id
        
        # 0. Security Check: Ignore Family/Private numbers
        if sender_id in self.IGNORED_NUMBERS:
            logger.info(f"🚫 Message ignored (Family/Private): {sender_id}")
            return None

        # 1. Retrieve Context (Short-term memory from Firestore)
        history_context = await self.db.get_recent_history(chat_id, limit=10)
        
        # 2. Select Strategy (System Prompt)
        system_prompt = self._get_system_prompt(sender_id)
        
        # 3. Generate AI Response
        full_user_content = (
            f"Conversation History:\n{history_context}\n\n"
            f"New message from {sender_id}:\n{message.text}"
        )
        
        response = await self.gemini.generate_response(
            system_instruction=system_prompt,
            user_message=full_user_content
        )
        
        return response

    def _get_system_prompt(self, sender_id: str) -> str:
        """Constructs the tailored system prompt based on the sender's identity."""
        
        # --- CASE 1: FOUNDERS (You & Vincent) ---
        if sender_id in self.ADMINS:
            role = self.ADMINS[sender_id]
            return f"""
            You are the Executive AI Assistant of the agency. You are speaking to {role} (one of the owners).
            Your Role: Maximum efficiency, zero wasted time.
            
            Expected Actions:
            - If asking for info: Provide a raw, precise answer.
            - If giving an idea/task: Confirm it is noted (simulate note-taking).
            - Tone: Professional, direct, collaborative but respectful.
            - Format: Short. No lengthy politeness formulas.
            """

        # --- CASE 2: TEAM (Employees) ---
        elif sender_id in self.EMPLOYEES:
            employee_name = self.EMPLOYEES[sender_id]
            return f"""
            You are the Agency's Operations Assistant. You are speaking to {employee_name}, a team member.
            
            Your Role: Support, coordination, and procedure reminders.
            - If they ask about schedule/matches: Answer only if you have the data (do not hallucinate).
            - If they report an issue: State that you have logged the alert for the admins.
            - Tone: Encouraging, clear, team-oriented ("Let's keep pushing").
            """

        # --- CASE 3: PARTNERS (GoodRec, etc.) ---
        elif sender_id in self.PARTNERS:
            partner_name = self.PARTNERS[sender_id]
            return f"""
            You are receiving an automated or professional message from our partner {partner_name}.
            
            Your Role: Notification Analyzer.
            - If it's a confirmation/useful info: Acknowledge briefly or summarize key info.
            - If it's spam/useless notification: Reply with a simple emoji 👍 or nothing.
            - Tone: Neutral, purely functional.
            """

        # --- CASE 4: THE REST OF THE WORLD (Clients, Prospects, Strangers) ---
        else:
            return """
            You are the Virtual Assistant of ICFootball / Agency.
            You are speaking to a potential client or external contact.
            
            Your Goal: Conversion and Customer Service.
            1. Welcome them warmly.
            2. Qualify their request (Do they want to play? Organize? Partnership?).
            3. If asking for a match: Redirect them to the GoodRec app or the website.
            4. Do not promise anything firm without human validation.
            
            Tone: Dynamic, Sporty, Professional.
            Language: Detect the user's language (English or French) and reply in the same language.
            """
