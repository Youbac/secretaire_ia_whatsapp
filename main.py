import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from contextlib import asynccontextmanager
import logging

# Imports internes modulaires
from config import settings
from app.schemas.webhook import UnipileMessageEvent
from app.services.firestore import save_message_event

# --- Configuration des Logs ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main_server")

# --- 1. Cycle de Vie (Startup / Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestion propre du démarrage et de l'arrêt.
    Permet d'initialiser les connexions avant d'accepter des requêtes.
    """
    # Au démarrage
    logger.info("🚀 [System] Démarrage du Secrétaire IA WhatsApp (v2.0)...")
    
    mode = "CLOUD (Base64)" if settings.FIREBASE_CRED_BASE64 else "LOCAL (Fichier)"
    logger.info(f"🔧 [Config] Mode Environnement: {mode}")
    
    # Ici, on pourrait pré-charger des modèles IA lourds si besoin
    
    yield # Le serveur tourne ici...
    
    # À l'arrêt
    logger.info("🛑 [System] Arrêt gracieux du serveur.")

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
        
                # --- NOUVEAU BLOC DE FILTRAGE ---
        # Si on a configuré un ID spécifique et que le message ne vient pas de ce compte...
        if settings.UNIPILE_ACCOUNT_ID and event.account_id != settings.UNIPILE_ACCOUNT_ID:
            # On ignore silencieusement (ou avec un petit log debug)
            logger.info(f"🚫 [Ignoré] Message pour un autre compte ({event.account_id})")
            return
        # -------------------------------

        # 2. Filtrage (On ne veut que les nouveaux messages entrants)
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
    # Ne se lance que si on exécute 'python main.py' directement
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True # Reload auto si on change le code (Dev Experience)
    )
