import asyncio
import logging
from datetime import datetime
from app.services.firestore import get_weekly_context
from app.agents.finance import FinanceAnalyst
from app.services.firestore import get_new_messages_only  
from app.agents.finance import FinanceAnalyst

# Services
from app.services.firestore import (
    save_message_event, 
    get_unprocessed_chats, 
    get_messages_from_today, 
    mark_chat_as_processed,
    db  # On importe db pour faire des requêtes spécifiques si besoin
)
from app.services.gemini import GeminiService
from app.services.sheets import GoogleSheetsService

# Agents
from app.agents.sales import SalesAnalyst
from app.agents.strategy import StrategyAnalyst

# Config
from config import settings

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("daily_reporter")

# --- CONFIGURATION ---
# Ton numéro et celui de Vincent (pour identifier le chat "Strategy")
# Assure-toi que ces numéros correspondent EXACTEMENT à l'ID de chat dans Firestore (souvent le num sans +)
VINCENT_CHAT_ID = "BAKgkSJ2VqKSlDDhOy4Cww"  
MY_CHAT_ID = "33768389721" # Le tien, au cas où vous parlez dans un groupe à deux

# ... Config
FINANCE_GROUP_ID = "-zeA_LzlUnS3nCeRyIdS5Q" # Remplace par le VRAI ID du groupe Dépenses


async def main():
    logger.info("🌙 Démarrage du Rapport Quotidien...")
    
    # 1. Initialisation
    try:
        gemini = GeminiService()
        sheets = GoogleSheetsService()
        sales_agent = SalesAnalyst(gemini)
        strategy_agent = StrategyAnalyst(gemini)
        finance_agent = FinanceAnalyst(gemini)  
        logger.info("✅ Services & Agents prêts.")
    except Exception as e:
        logger.critical(f"❌ Échec init services: {e}")
        return

    # --- PARTIE 1 : ANALYSE DES CLIENTS (SALES) ---
    logger.info("🕵️‍♂️ Début analyse Sales (Clients/Prospects)...")
    
    chat_ids = get_unprocessed_chats()
    logger.info(f"📊 {len(chat_ids)} conversations actives trouvées aujourd'hui.")

    for chat_id in chat_ids:
        # On ignore le chat avec Vincent ici (il est traité à part)
        if chat_id == VINCENT_CHAT_ID or chat_id == MY_CHAT_ID:
            continue
            
        # Récupération des messages du jour
        history = get_weekly_context(chat_id)
        
        if not history:
            logger.info(f"Skipping {chat_id} (Pas de messages aujourd'hui malgré le flag)")
            mark_chat_as_processed(chat_id)
            continue

        # Analyse IA
        logger.info(f"🧠 Analyse de {chat_id}...")
        analysis = await sales_agent.analyze_conversation(chat_id, history)
        
        # Sauvegarde dans Google Sheets (Onglet "Leads du Jour")
        # Format: [Date, ChatID, Résumé IA]
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Note: Assure-toi d'avoir un onglet nommé "DailyLogs" dans ton Sheet
        success = await sheets.append_row(
            spreadsheet_id=settings.GOOGLE_SHEET_ID,
            range_name="DailyLogs!A:C", 
            values=[today_str, chat_id, analysis]
        )
        
        if success:
            mark_chat_as_processed(chat_id)
        else:
            logger.error(f"❌ Échec écriture Sheet pour {chat_id}")

    # --- PARTIE 2 : ANALYSE STRATÉGIQUE (VINCENT) ---
    logger.info("👔 Début analyse Stratégie (Vincent)...")
    
    # On récupère le chat spécifique avec Vincent
    # Note: L'ID du chat dépend de qui a initié la conversation. 
    vincent_history = get_messages_from_today(VINCENT_CHAT_ID)
    
    if vincent_history:
        logger.info("🧠 Analyse de la discussion Fondateurs...")
        strategy_report = await strategy_agent.analyze_founders_chat(vincent_history)
        
        # Sauvegarde dans Google Sheets (Onglet "Stratégie")
        today_str = datetime.now().strftime("%Y-%m-%d")
        await sheets.append_row(
            spreadsheet_id=settings.GOOGLE_SHEET_ID,
            range_name="Strategy!A:C",
            values=[today_str, "Vincent & Moi", strategy_report]
        )
        # On marque aussi ce chat comme traité
        mark_chat_as_processed(VINCENT_CHAT_ID)
    else:
        logger.info("📭 Aucun échange avec Vincent aujourd'hui.")
    
    # --- PARTIE 3 : ANALYSE FINANCE (Groupe Dépenses) ---
    logger.info("💰 Début analyse Finance...")
    
    # ICI : On ne prend QUE les nouveaux messages pour éviter les doublons
    finance_history = get_new_messages_only(FINANCE_GROUP_ID)
    
    if finance_history:
        logger.info(f"🔎 Nouveaux messages Finance à analyser : \n{finance_history[:100]}...")
        
        transactions = await finance_agent.extract_transactions(finance_history)
        
        if transactions:
            logger.info(f"💸 {len(transactions)} transactions extraites.")
            for tx in transactions:
                # Écriture dans le Sheet
                await sheets.append_row(
                    spreadsheet_id=settings.GOOGLE_SHEET_ID,
                    range_name="Compta!A:F",
                    values=[
                        tx.get("date"),
                        tx.get("paye_par"),
                        tx.get("categorie"),
                        tx.get("description"),
                        tx.get("montant"),
                        tx.get("devise")
                    ]
                )
        
        # CRUCIAL : On met à jour le timestamp 'last_processed_at'
        mark_chat_as_processed(FINANCE_GROUP_ID)
        
    else:
        logger.info("✅ Aucune nouvelle dépense depuis la dernière fois.")

if __name__ == "__main__":
    asyncio.run(main())
