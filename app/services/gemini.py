import logging
from typing import Optional
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Import settings
from config import settings

# Configure Logger
logger = logging.getLogger(__name__)

class GeminiService:
    """
    Production-grade wrapper for Google GenAI SDK (v1.0+).
    Handles authentication, retries, and safety settings for Gemini 1.5/2.0.
    """

    def __init__(self):
        self._validate_config()
        
        # Initialize the synchronous and asynchronous client
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        self.model_name = settings.GEMINI_MODEL

        # Default Generation Config (Performance optimized)
        self.default_config = types.GenerateContentConfig(
            temperature=0.3,
            top_p=0.8,
            top_k=40,
            max_output_tokens=2048,
            # Permissive safety settings for professional use cases to avoid false positives
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_ONLY_HIGH"),
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_ONLY_HIGH"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_ONLY_HIGH"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_ONLY_HIGH"),
            ]
        )
        
        logger.info(f"✨ Gemini Service initialized with model: {self.model_name}")

    def _validate_config(self):
        """Ensures critical configuration is present before startup."""
        if not settings.GOOGLE_API_KEY:
            logger.critical("❌ FATAL: GOOGLE_API_KEY is missing in settings.")
            raise ValueError("GOOGLE_API_KEY is required.")

    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception), # In production, narrow this down to specific API errors
        reraise=True
    )
    async def generate_response(self, system_instruction: str, user_message: str) -> str:
        """
        Generates a response using the Async API with automatic retries.
        
        Args:
            system_instruction (str): The 'persona' or rules for the AI.
            user_message (str): The actual input content to process.
            
        Returns:
            str: The cleaned AI response.
        """
        try:
            # Create a shallow copy of config to inject the dynamic system instruction
            run_config = self.default_config
            run_config.system_instruction = system_instruction

            # Async API Call
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=user_message,
                config=run_config
            )

            if not response.text:
                logger.warning("⚠️ Gemini returned an empty response (Potential Safety Filter trigger).")
                return "I cannot answer this request due to safety filters."

            return response.text.strip()

        except Exception as e:
            # We log the error here, but 'tenacity' will retry it 3 times before giving up
            logger.warning(f"🔄 Gemini API Warning (Retrying...): {e}")
            raise e  # Re-raise to trigger retry logic

    async def safe_generate(self, system_instruction: str, user_message: str) -> str:
        """
        Wrapper around generate_response that catches all errors for safe UI display.
        Use this method in your main application loop to prevent crashes.
        """
        try:
            return await self.generate_response(system_instruction, user_message)
        except Exception as e:
            logger.error(f"❌ Gemini Critical Failure after retries: {e}", exc_info=True)
            return "Service temporarily unavailable. Please try again later."

# Singleton Instance
gemini_service = GeminiService()
