import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import firestore as google_firestore

from config import settings
from app.schemas.webhook import UnipileMessageEvent

# --- LOGGER CONFIGURATION ---
logger = logging.getLogger("firestore_service")
logger.setLevel(logging.INFO)

# --- 1. INITIALIZATION (Singleton) ---
if not firebase_admin._apps:
    logger.info("🔌 Initializing Firebase connection...")
    cred_info = settings.get_firebase_credentials()
    if cred_info:
        cred = credentials.Certificate(cred_info)
        firebase_admin.initialize_app(cred)
        logger.info("✅ Firebase connection established.")
    else:
        logger.warning("⚠️ Using Default Google Cloud Auth.")
        firebase_admin.initialize_app()

db = firestore.client()

# --- 2. CORE FUNCTIONS ---

def save_message_event(event: UnipileMessageEvent) -> bool:
    """
    Saves an incoming message with enriched metadata for groups.
    Updates the parent 'chat' document to flag it for nightly analysis.
    """
    try:
        batch = db.batch()
        
        chat_ref = db.collection("chats").document(event.chat_id)
        msg_ref = chat_ref.collection("messages").document(event.message_id)

        # 1. Prepare Message Document
        # model_dump converts Pydantic to Dict, using aliases (id -> message_id)
        msg_doc = event.model_dump(exclude={"event"}, by_alias=True)
        msg_doc["stored_at"] = google_firestore.SERVER_TIMESTAMP
        
        # 2. Smart Group Logic
        attendees_list = event.attendees_ids or []
        # A chat is a group if it has > 2 people OR specifically ends in @g.us (WhatsApp standard)
        is_group = len(attendees_list) > 2 or (event.chat_id and "@g.us" in event.chat_id)
        
        chat_name = event.chat_name
        
        # 3. Prepare Chat Metadata Update (Parent Doc)
        sender_name = event.sender.attendee_name or "Unknown"
        preview_text = (event.text or "📎 Media/File")[:100]

        chat_update = {
            "last_message_preview": f"{sender_name}: {preview_text}",
            "last_activity": event.timestamp,
            "updated_at": google_firestore.SERVER_TIMESTAMP,
            "is_group": is_group,
            
            # Add sender to participant lists (ArrayUnion adds only if unique)
            "participants_names": firestore.ArrayUnion([sender_name]),
            "participants_ids": firestore.ArrayUnion([event.sender.attendee_id]),
            
            # Metadata for the Nightly Reporter
            "ai_processed": False,      # Flag: Has not been summarized yet
            "needs_summary": True       # Flag: Explicitly needs attention
        }

        if chat_name:
            chat_update["chat_name"] = chat_name

        # 4. Execute Batch
        batch.set(msg_ref, msg_doc)
        batch.set(chat_ref, chat_update, merge=True) # merge=True is VITAL to keep existing tags/notes

        batch.commit()
        
        logger.info(f"💾 Saved Msg from {sender_name} | Chat: {event.chat_id} | Group: {is_group}")
        return True

    except Exception as e:
        logger.error(f"❌ Critical Firestore Error: {str(e)}", exc_info=True)
        raise e

# --- 3. RETRIEVAL FUNCTIONS (For Nightly Agents) ---

def get_weekly_context(chat_id: str) -> str:
    """
    Récupère l'historique des 7 derniers jours pour ce chat.
    Permet à l'IA d'avoir le contexte complet de la semaine, pas juste du jour.
    """
    try:
        # Calcul de la date il y a 7 jours
        now = datetime.utcnow()
        seven_days_ago = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0)
        
        # On va chercher dans la sous-collection 'messages' de CE chat
        # Note: BAKgkSJ2VqKSlDDhOy4Cww semble être un ID de message ou un ID auto-généré, 
        # assure-toi qu'on vise bien le document PARENT (le chat).
        
        docs = (
            db.collection("chats")
            .document(chat_id)
            .collection("messages")
            .where("stored_at", ">=", seven_days_ago) # On filtre sur stored_at comme demandé
            .order_by("stored_at")
            .stream()
        )
        
        conversation_text = []
        for doc in docs:
            data = doc.to_dict()
            sender = data.get("sender", {}).get("attendee_name", "Inconnu")
            text = data.get("text", "[Contenu non-texte]")
            
            # Formatage propre de la date pour l'IA (ex: "Lun 10h30")
            ts = data.get("stored_at")
            if ts:
                # Si c'est un objet datetime Firestore, on le formate, sinon on laisse
                time_str = ts.strftime("%a %d %H:%M") if hasattr(ts, 'strftime') else str(ts)
            else:
                time_str = "?"
                
            conversation_text.append(f"[{time_str}] {sender}: {text}")
            
        return "\n".join(conversation_text)

    except Exception as e:
        logger.error(f"❌ Erreur lecture historique {chat_id}: {e}")
        return ""

def get_unprocessed_chats() -> List[str]:
    """
    Returns a list of chat_ids that have 'needs_summary' = True.
    Used by the Sales Agent to know which customers to analyze.
    """
    try:
        docs = db.collection("chats").where("needs_summary", "==", True).stream()
        return [doc.id for doc in docs]
    except Exception as e:
        logger.error(f"❌ Error fetching unprocessed chats: {e}")
        return []

def mark_chat_as_processed(chat_id: str):
    """Resets the flags after analysis is done."""
    try:
        db.collection("chats").document(chat_id).update({
            "needs_summary": False,
            "ai_processed": True,
            "last_processed_at": google_firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        logger.error(f"❌ Error updating chat status {chat_id}: {e}")

def get_new_messages_only(chat_id: str) -> str:
    """
    Récupère uniquement les messages NON lus par le script précédent.
    Idéal pour la Compta (évite les doublons).
    """
    try:
        # 1. On regarde quand le chat a été traité pour la dernière fois
        chat_doc = db.collection("chats").document(chat_id).get()
        if not chat_doc.exists:
            return "" # Chat inconnu
            
        data = chat_doc.to_dict()
        last_processed_at = data.get("last_processed_at") # Timestamp Firestore
        
        # 2. Construction de la requête
        query = (
            db.collection("chats")
            .document(chat_id)
            .collection("messages")
            .order_by("stored_at")
        )
        
        # Si on a déjà traité ce chat, on filtre ce qui est APRES cette date
        if last_processed_at:
            query = query.where("stored_at", ">", last_processed_at)
            
        docs = query.stream()
        
        # 3. Formatage
        conversation_text = []
        count = 0
        for doc in docs:
            msg = doc.to_dict()
            sender = msg.get("sender", {}).get("attendee_name", "Inconnu")
            text = msg.get("text", "")
            # On ajoute la date dans le texte pour aider l'IA (ex: pour la colonne Date du Sheet)
            date_str = msg.get("stored_at").strftime("%Y-%m-%d") if msg.get("stored_at") else "???"
            
            conversation_text.append(f"[{date_str}] {sender}: {text}")
            count += 1
            
        if count == 0:
            return ""
            
        return "\n".join(conversation_text)

    except Exception as e:
        logger.error(f"❌ Erreur lecture incrémentale {chat_id}: {e}")
        return ""

