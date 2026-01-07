import asyncio
import logging
from datetime import datetime

# Services
from app.services.firestore import (
    get_weekly_context, 
    get_unprocessed_chats, 
    mark_chat_as_processed
)
from app.services.gemini import GeminiService
from app.services.sheets import GoogleSheetsService

# Agents
from app.agents.sales import SalesAnalyst
from app.agents.strategy import StrategyAnalyst
from app.agents.finance import FinanceAnalyst

# Config
from config import settings

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("DailyReporter")

# --- CONSTANTS ---
VINCENT_CHAT_ID = "BAKgkSJ2VqKSlDDhOy4Cww"  
MY_CHAT_ID = "33768389721" 
FINANCE_GROUP_ID = "-zeA_LzlUnS3nCeRyIdS5Q"
IGNORED_CHATS = {VINCENT_CHAT_ID, MY_CHAT_ID, FINANCE_GROUP_ID}

async def run_sales_analysis(gemini: GeminiService, sheets: GoogleSheetsService):
    """Sub-process: Analyzes customer conversations."""
    logger.info("🕵️‍♂️ [SALES] Starting analysis...")
    
    try:
        chat_ids = get_unprocessed_chats()
        if not chat_ids:
            logger.info("📭 [SALES] No active chats found.")
            return

        logger.info(f"📊 [SALES] Found {len(chat_ids)} chats to process.")
        
        # Instantiate Agent once
        sales_agent = SalesAnalyst(gemini)
        today_str = datetime.now().strftime("%Y-%m-%d")

        count = 0
        for chat_id in chat_ids:
            if chat_id in IGNORED_CHATS:
                continue

            history = get_weekly_context(chat_id)
            if not history:
                mark_chat_as_processed(chat_id)
                continue

            # Analyze
            logger.debug(f"🧠 [SALES] Analyzing {chat_id}...")
            analysis = await sales_agent.analyze_conversation(chat_id, history)
            
            # Save to Sheets
            success = await sheets.append_row(
                spreadsheet_id=settings.SHEET_ID_SALES,
                range_name="Sheet1!A:C",
                values=[today_str, chat_id, analysis]
            )

            if success:
                mark_chat_as_processed(chat_id)
                count += 1
            else:
                logger.error(f"❌ [SALES] Failed to save report for {chat_id}")

        logger.info(f"✅ [SALES] Processed {count} conversations successfully.")

    except Exception as e:
        logger.error(f"❌ [SALES] Critical Failure: {e}", exc_info=True)

async def run_strategy_analysis(gemini: GeminiService, sheets: GoogleSheetsService):
    """Sub-process: Analyzes Founder discussions."""
    logger.info("👔 [STRATEGY] Starting analysis...")
    
    try:
        vincent_history = get_weekly_context(VINCENT_CHAT_ID)
        
        if not vincent_history:
            logger.info("📭 [STRATEGY] No recent messages with Vincent.")
            return

        strategy_agent = StrategyAnalyst(gemini)
        report = await strategy_agent.analyze_founders_chat(vincent_history)
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        success = await sheets.append_row(
            spreadsheet_id=settings.SHEET_ID_STRATEGY,
            range_name="Sheet1!A:C",
            values=[today_str, "Vincent & Moi", report]
        )

        if success:
            mark_chat_as_processed(VINCENT_CHAT_ID)
            logger.info("✅ [STRATEGY] Report saved successfully.")
        else:
            logger.error("❌ [STRATEGY] Failed to save report to Sheets.")

    except Exception as e:
        logger.error(f"❌ [STRATEGY] Critical Failure: {e}", exc_info=True)

async def run_finance_analysis():
    """Sub-process: Analyzes Finance Group."""
    logger.info("💰 [FINANCE] Starting analysis...")
    
    try:
        # Note: FinanceAnalyst handles its own dependencies internally (as per your class design)
        finance_agent = FinanceAnalyst()
        
        # We run it in a thread if it's blocking, but here assuming process_and_save is synchronous or hybrid
        # If process_and_save is blocking, wrap it in asyncio.to_thread
        result = await asyncio.to_thread(finance_agent.process_and_save)
        
        logger.info(f"✅ [FINANCE] Result: {result}")

    except Exception as e:
        logger.error(f"❌ [FINANCE] Critical Failure: {e}", exc_info=True)

async def main():
    logger.info("🌙 === STARTING DAILY REPORT === 🌙")
    
    # 1. Initialize Core Services
    try:
        gemini = GeminiService()
        sheets = GoogleSheetsService()
        logger.info("🛠️ Core Services Initialized.")
    except Exception as e:
        logger.critical(f"❌ Failed to initialize core services. Aborting. Error: {e}")
        return

    # 2. Run All Tasks Concurrently (Optional) or Sequentially
    # Running sequentially is safer for debugging
    
    await run_sales_analysis(gemini, sheets)
    await run_strategy_analysis(gemini, sheets)
    await run_finance_analysis()

    logger.info("🌙 === DAILY REPORT COMPLETED === 🌙")

if __name__ == "__main__":
    asyncio.run(main())
