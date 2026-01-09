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
    logger.info("🔌 [Init] Démarrage connexion Firebase...")
    try:
        cred_info = settings.get_firebase_credentials()
        if cred_info:
            cred = credentials.Certificate(cred_info)
            firebase_admin.initialize_app(cred)
            logger.info("✅ [Init] Connexion Firebase établie avec succès.")
        else:
            logger.warning("⚠️ [Init] Attention : Utilisation Auth Google Cloud par défaut (Pas de credentials trouvés).")
            firebase_admin.initialize_app()
    except Exception as e:
        logger.critical(f"❌ [Init] ERREUR CRITIQUE connexion Firebase : {e}", exc_info=True)
        # On ne raise pas ici pour ne pas crasher toute l'app au démarrage, 
        # mais la DB ne marchera pas.

db = firestore.client()

# --- 2. CORE FUNCTIONS ---

def save_message_event(event: UnipileMessageEvent) -> bool:
    """
    Sauvegarde un message entrant dans Firestore.
    Version 'Ultra-Robuste' avec logs détaillés pour le débogage.
    """
    # 1. Log d'entrée pour tracer la requête
    logger.info(f"📥 [Firestore] Début sauvegarde message ID: {event.message_id} | Chat: {event.chat_id}")
    
    try:
        batch = db.batch()
        
        # Références Documents
        chat_ref = db.collection("chats").document(event.chat_id)
        msg_ref = chat_ref.collection("messages").document(event.message_id)

        # 2. Nettoyage & Préparation des données du message
        try:
            # On convertit l'objet Pydantic en dictionnaire propre pour Firestore
            msg_doc = event.model_dump(exclude={"event"}, by_alias=True)
        except Exception as e:
            logger.error(f"❌ [Data] Erreur conversion Pydantic (model_dump) : {e}")
            return False

        msg_doc["stored_at"] = google_firestore.SERVER_TIMESTAMP
        
        # 3. Analyse du contexte (Groupe ou pas ?)
        attendees_list = event.attendees_ids or []
        # Un chat est un groupe si > 2 participants OU si l'ID contient @g.us
        is_group = len(attendees_list) > 2 or (event.chat_id and "@g.us" in event.chat_id)
        
        # 4. Extraction sécurisée de l'expéditeur
        sender_info = event.sender
        sender_name = sender_info.attendee_name or "Inconnu"
        sender_id = sender_info.attendee_id # Peut être None

        # Log de diagnostic sur l'expéditeur (pour comprendre pourquoi ça plantait avant)
        if not sender_id:
            logger.warning(f"⚠️ [Data Warning] Message {event.message_id} SANS ID d'expéditeur. Nom: {sender_name}")

        # 5. Préparation de la mise à jour du Chat parent
        preview_text = (event.text or "📎 [Média/Fichier]")[:100]

        chat_update = {
            "last_message_preview": f"{sender_name}: {preview_text}",
            "last_activity": event.timestamp,
            "updated_at": google_firestore.SERVER_TIMESTAMP,
            "is_group": is_group,
            "ai_processed": False,      # Marqueur pour l'IA : "À traiter"
            "needs_summary": True       # Marqueur pour le résumé quotidien
        }

        # 6. Mise à jour des participants (Sécurisée)
        # ArrayUnion plante si on lui donne None, donc on vérifie avant d'ajouter.
        if sender_id:
            chat_update["participants_ids"] = firestore.ArrayUnion([sender_id])
        
        if sender_name and sender_name != "Inconnu":
            chat_update["participants_names"] = firestore.ArrayUnion([sender_name])

        if event.chat_name:
            chat_update["chat_name"] = event.chat_name

        # 7. Ajout au Batch
        batch.set(msg_ref, msg_doc)
        # merge=True est CRUCIAL pour ne pas écraser les données existantes du chat (tags, notes, etc.)
        batch.set(chat_ref, chat_update, merge=True) 

        # 8. Commit (Envoi vers Google)
        batch.commit()
        
        logger.info(f"✅ [Firestore] SUCCÈS ! Message de {sender_name} sauvegardé dans {event.chat_id}.")
        return True

    except Exception as e:
        # Log détaillé de l'erreur avec la stack trace complète
        logger.error(f"❌ [Firestore CRASH] Echec sauvegarde message {event.message_id}: {str(e)}", exc_info=True)
        return False

# --- 3. RETRIEVAL FUNCTIONS (For Nightly Agents) ---

def get_weekly_context(chat_id: str) -> str:
    """
    Récupère l'historique des 7 derniers jours pour ce chat.
    Permet à l'IA d'avoir le contexte complet de la semaine.
    """
    try:
        now = datetime.utcnow()
        seven_days_ago = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0)
        
        docs = (
            db.collection("chats")
            .document(chat_id)
            .collection("messages")
            .where("stored_at", ">=", seven_days_ago)
            .order_by("stored_at")
            .stream()
        )
        
        conversation_text = []
        for doc in docs:
            data = doc.to_dict()
            sender = data.get("sender", {}).get("attendee_name", "Inconnu")
            text = data.get("text", "[Contenu non-texte]")
            
            ts = data.get("stored_at")
            if ts:
                time_str = ts.strftime("%a %d %H:%M") if hasattr(ts, 'strftime') else str(ts)
            else:
                time_str = "?"
                
            conversation_text.append(f"[{time_str}] {sender}: {text}")
            
        return "\n".join(conversation_text)

    except Exception as e:
        logger.error(f"❌ [Firestore Read] Erreur lecture historique {chat_id}: {e}")
        return ""

def get_unprocessed_chats() -> List[str]:
    """
    Retourne la liste des chat_ids qui doivent être analysés ('needs_summary' = True).
    """
    try:
        docs = db.collection("chats").where("needs_summary", "==", True).stream()
        return [doc.id for doc in docs]
    except Exception as e:
        logger.error(f"❌ [Firestore Read] Erreur récupération chats à traiter: {e}")
        return []

def mark_chat_as_processed(chat_id: str):
    """Marque le chat comme traité après l'analyse IA."""
    try:
        db.collection("chats").document(chat_id).update({
            "needs_summary": False,
            "ai_processed": True,
            "last_processed_at": google_firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        logger.error(f"❌ [Firestore Update] Erreur update statut chat {chat_id}: {e}")

def get_new_messages_only(chat_id: str) -> str:
    """
    Récupère uniquement les messages NON lus par le script précédent.
    """
    try:
        chat_doc = db.collection("chats").document(chat_id).get()
        if not chat_doc.exists:
            return "" 
            
        data = chat_doc.to_dict()
        last_processed_at = data.get("last_processed_at")
        
        query = (
            db.collection("chats")
            .document(chat_id)
            .collection("messages")
            .order_by("stored_at")
        )
        
        if last_processed_at:
            query = query.where("stored_at", ">", last_processed_at)
            
        docs = query.stream()
        
        conversation_text = []
        count = 0
        for doc in docs:
            msg = doc.to_dict()
            sender = msg.get("sender", {}).get("attendee_name", "Inconnu")
            text = msg.get("text", "")
            date_str = msg.get("stored_at").strftime("%Y-%m-%d") if msg.get("stored_at") else "???"
            
            conversation_text.append(f"[{date_str}] {sender}: {text}")
            count += 1
            
        if count == 0:
            return ""
            
        return "\n".join(conversation_text)

    except Exception as e:
        logger.error(f"❌ [Firestore Read] Erreur lecture incrémentale {chat_id}: {e}")
        return ""