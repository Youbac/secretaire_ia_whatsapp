import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import firestore as google_firestore
from datetime import datetime
import logging

# On importe notre config et notre schéma validé
from config import settings
from app.schemas.webhook import UnipileMessageEvent

# --- Configuration du Logger ---
logger = logging.getLogger("firestore_service")
logger.setLevel(logging.INFO)

# --- 1. Initialisation Singleton (Pattern Lazy Loading) ---
# On ne se connecte que si nécessaire, et une seule fois.

if not firebase_admin._apps:
    logger.info("🔌 Initialisation de la connexion Firebase...")
    
    cred_info = settings.get_firebase_credentials()
    
    if cred_info:
        # Si get_firebase_credentials renvoie un chemin (str) ou un dict (Base64)
        cred = credentials.Certificate(cred_info)
        firebase_admin.initialize_app(cred)
        logger.info("✅ Connexion Firebase établie avec succès.")
    else:
        # Fallback critique : Tente l'auth par défaut (Google Cloud Run / Local GCloud)
        logger.warning("⚠️ Aucun credential explicite. Tentative d'Auth par défaut Google...")
        firebase_admin.initialize_app()

# Client global réutilisable
db = firestore.client()

# --- 2. Fonctions Métier ---

def save_message_event(event: UnipileMessageEvent) -> bool:
    """
    Sauvegarde un message entrant de manière atomique (Batch Write).
    
    Stratégie de Données (NoSQL) :
    - Collection 'chats' : Métadonnées légères (pour l'affichage liste).
    - Sous-collection 'messages' : L'historique complet.
    
    Returns:
        bool: True si succès, False sinon.
    """
    try:
        # On démarre une transaction batch pour garantir la cohérence
        batch = db.batch()
        
        # Références des documents
        chat_ref = db.collection("chats").document(event.chat_id)
        msg_ref = chat_ref.collection("messages").document(event.message_id)

        # 1. Préparation du document Message
        # .model_dump() convertit notre objet Pydantic en dictionnaire propre pour Firestore
        msg_doc = event.model_dump(exclude={"event"}, by_alias=True)
        # On ajoute un timestamp serveur fiable (indépendant de l'heure du PC)
        msg_doc["stored_at"] = google_firestore.SERVER_TIMESTAMP
        
        # 2. Préparation des Méta-données du Chat (Snippet)
        # On tronque le texte pour la prévisualisation (max 100 chars)
        preview_text = (event.text or "📎 Média/Fichier")[:100]
        
        chat_update = {
            "last_message_preview": preview_text,
            "last_activity": event.timestamp, # Timestamp de WhatsApp
            "updated_at": google_firestore.SERVER_TIMESTAMP, # Timestamp de mise à jour
            # On stocke les participants pour faciliter la recherche future
            "participants_names": firestore.ArrayUnion([event.sender.attendee_name or "Inconnu"]),
            
            # Champs pour nos futurs agents (State Machine)
            "status": "active", 
            "ai_processed": False 
        }

        # 3. Ajout des opérations au Batch
        batch.set(msg_ref, msg_doc) # Crée ou remplace le message
        
        # merge=True est CRUCIAL ici.
        # Si le chat existe déjà (avec des tags, des notes IA), on ne veut PAS tout écraser.
        # On met juste à jour le "last_message".
        batch.set(chat_ref, chat_update, merge=True) 

        # 4. Commit (Envoi vers Google en une seule requête HTTP)
        batch.commit()
        
        logger.info(f"💾 Saved Msg: {event.message_id} | Chat: {event.chat_id}")
        return True

    except Exception as e:
        logger.error(f"❌ Critical Firestore Error: {str(e)}", exc_info=True)
        # En prod, ici on enverrait une alerte Sentry
        # On relance l'exception pour que le contrôleur sache que ça a échoué
        raise e
