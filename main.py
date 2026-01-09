import uvicorn
import logging
import os
from fastapi import FastAPI, Request, BackgroundTasks
from contextlib import asynccontextmanager

# --- 1. CONFIGURATION LOGS (À PLACER TOUT EN HAUT) ---
# Ceci force Render à afficher les logs immédiatement
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    force=True 
)
logger = logging.getLogger("main_server")

# --- 2. Imports de l'application ---
# (On importe le reste APRÈS avoir configuré les logs)
from config import settings
from app.schemas.webhook import UnipileMessageEvent
from app.services.firestore import save_message_event

# --- 3. Cycle de Vie ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 [System] Démarrage du Secrétaire IA WhatsApp (v2.0)...")
    logger.info(f"🔧 [Config] Mode Environnement: {'CLOUD' if settings.FIREBASE_CRED_BASE64 else 'LOCAL'}")
    yield
    logger.info("🛑 [System] Arrêt du serveur.")

# --- 4. Initialisation FastAPI ---
app = FastAPI(lifespan=lifespan)

# --- 2. Initialisation FastAPI ---
app = FastAPI(
    title="Secretaire IA WhatsApp API",
    description="Backend de gestion WhatsApp via Unipile & Gemini",
    version="2.0.0",
    lifespan=lifespan
)

# --- 3. Logique Métier (Background Workers) ---
async def process_webhook_event(payload: dict):
    """
    Worker asynchrone : Traite le message EN ARRIÈRE-PLAN.
    Avantage : Unipile reçoit son '200 OK' en 10ms, même si on met 5s à traiter.
    """
    try:
        logger.info(f"[DEBUG] Payload brut: {payload}")
        event = UnipileMessageEvent(**payload)
        logger.info(f"[DEBUG] event.account_id={event.account_id}, filter={settings.UNIPILE_ACCOUNT_ID}")
        # 1. Validation Pydantic (Si le payload est invalide, ça s'arrête net)
        event = UnipileMessageEvent(**payload)
        
        # 2. Filtrage (On ne veut que les nouveaux messages entrants)
        logger.info(f"[DEBUG] account_id reçu: {event.account_id}")

        # On ignore les 'read', 'typing', etc. pour l'instant
        if event.event not in ["message_received", "message_created"]:
            logger.debug(f"Event ignoré: {event.event}")
            return

        # 3. Sauvegarde Persistante
        save_message_event(event)
        
        # 4. [FUTUR] Déclenchement IA
        # C'est ici qu'on ajoutera la ligne : await ai_agent.analyze(event)

    except Exception as e:
        logger.error(f"❌ [Processing Error] Erreur lors du traitement background: {e}")

# --- 4. Routes API (Endpoints) ---

@app.get("/")
def health_check():
    """Route de santé pour Render/UptimeRobot"""
    return {
        "status": "online",
        "service": "Secretaire IA",
        "version": "2.0.0"
    }

@app.post("/unipile-webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint unique de réception des Webhooks Unipile.
    """
    try:
        # Lecture rapide du body
        payload = await request.json()
        
        # On ne bloque PAS la requête. On ajoute une tâche à la file d'attente.
        background_tasks.add_task(process_webhook_event, payload)
        
        # Réponse immédiate
        return {"status": "received", "details": "processing_in_background"}
        
    except Exception as e:
        logger.error(f"❌ [Webhook Error] Erreur critique de réception: {e}")
        # On renvoie 200 quand même pour éviter qu'Unipile désactive le webhook
        # (Fail-safe strategy)
        return {"status": "error_handled"}

# --- 5. Point d'entrée Local ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # Ne se lance que si on exécute 'python main.py' directement
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=port, 
        reload= False 
    )
