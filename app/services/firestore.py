import logging
import requests
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

import firebase_admin
from firebase_admin import credentials, firestore, storage
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
        
        # Configuration avec Storage Bucket
        options = {}
        if settings.FIREBASE_STORAGE_BUCKET:
            options['storageBucket'] = settings.FIREBASE_STORAGE_BUCKET

        if cred_info:
            cred = credentials.Certificate(cred_info)
            firebase_admin.initialize_app(cred, options)
            logger.info(f"✅ [Init] Firebase Auth & Storage ({settings.FIREBASE_STORAGE_BUCKET}) connectés.")
        else:
            logger.warning("⚠️ [Init] Auth Google Cloud par défaut.")
            firebase_admin.initialize_app(options=options)
            
    except Exception as e:
        logger.critical(f"❌ [Init] ERREUR CRITIQUE Firebase : {e}", exc_info=True)

db = firestore.client()

# --- 2. HELPER: GESTION DES FICHIERS ---

def process_attachments(event: UnipileMessageEvent):
    """
    Télécharge les pièces jointes d'Unipile et les stocke sur Firebase Storage.
    Met à jour l'objet event avec les nouvelles URLs durables.
    """
    if not event.attachments:
        return

    bucket = storage.bucket() # Utilise le bucket par défaut configuré

    for att in event.attachments:
        try:
            # 1. Récupération du contenu (Si Unipile donne une URL accessible)
            # Note: Si Unipile donne un ID interne, il faudrait faire un appel API spécifique ici.
            # On suppose ici que att.url ou une logique de fetch via API Unipile est utilisée.
            
            # Construction de l'URL de téléchargement Unipile si elle n'est pas directe
            # (Adaptation selon doc Unipile : souvent GET /api/v1/messages/{id}/attachments/{att_id})
            download_url = att.url
            headers = {}
            
            if not download_url and att.id:
                 # Fallback: Construction URL API Unipile (Hypothèse standard)
                 download_url = f"{settings.UNIPILE_DSN}/api/v1/messages/{event.message_id}/attachments/{att.id}"
                 headers = {"X-API-Key": settings.UNIPILE_API_KEY}

            if not download_url:
                logger.warning(f"⚠️ [Storage] Pas d'URL pour l'attachment {att.id}")
                continue

            # 2. Téléchargement
            logger.info(f"📥 [Storage] Téléchargement: {att.filename or 'fichier'}...")
            res = requests.get(download_url, headers=headers, stream=True)
            
            if res.status_code == 200:
                # 3. Upload vers Firebase Storage
                # Chemin: chats/{chat_id}/{message_id}/{filename}
                ext = att.filename.split('.')[-1] if att.filename and '.' in att.filename else "bin"
                blob_path = f"chats/{event.chat_id}/{event.message_id}/{att.id}.{ext}"
                
                blob = bucket.blob(blob_path)
                blob.upload_from_string(res.content, content_type=res.headers.get('Content-Type'))
                blob.make_public() # Optionnel : rend le lien accessible publiquement
                
                # 4. Mise à jour de l'URL dans l'objet message
                # On remplace l'URL Unipile (temporaire) par celle de Firebase (durable)
                att.url = blob.public_url
                logger.info(f"✅ [Storage] Fichier stocké : {att.url}")
            else:
                logger.error(f"❌ [Storage] Echec download Unipile ({res.status_code})")

        except Exception as e:
            logger.error(f"❌ [Storage] Erreur traitement fichier : {e}")

# --- 3. CORE FUNCTIONS ---

def save_message_event(event: UnipileMessageEvent) -> bool:
    """
    Sauvegarde avec gestion des fichiers multimédias.
    """
    logger.info(f"📥 [Firestore] Traitement message ID: {event.message_id}")
    
    try:
        # A. TRAITEMENT DES FICHIERS (Avant la sauvegarde)
        if event.attachments:
            process_attachments(event)

        batch = db.batch()
        
        chat_ref = db.collection("chats").document(event.chat_id)
        msg_ref = chat_ref.collection("messages").document(event.message_id)

        # B. DUMP DES DONNÉES (Incluant maintenant les URLs Firebase)
        msg_doc = event.model_dump(exclude={"event"}, by_alias=True)
        msg_doc["stored_at"] = google_firestore.SERVER_TIMESTAMP
        
        # C. LOGIQUE GROUPE & SENDER
        attendees_list = event.attendees_ids or []
        is_group = len(attendees_list) > 2 or (event.chat_id and "@g.us" in event.chat_id)
        
        sender_info = event.sender
        sender_name = sender_info.attendee_name or "Inconnu"
        sender_id = sender_info.attendee_id

        # D. APERÇU (Gère le cas "Image" si pas de texte)
        preview_text = event.text
        if not preview_text and event.attachments:
            preview_text = f"📎 Fichier: {event.attachments[0].filename or 'Media'}"
        preview_text = (preview_text or "")[:100]

        chat_update = {
            "last_message_preview": f"{sender_name}: {preview_text}",
            "last_activity": event.timestamp,
            "updated_at": google_firestore.SERVER_TIMESTAMP,
            "is_group": is_group,
            "ai_processed": False,
            "needs_summary": True
        }

        if sender_id:
            chat_update["participants_ids"] = firestore.ArrayUnion([sender_id])
        if sender_name != "Inconnu":
            chat_update["participants_names"] = firestore.ArrayUnion([sender_name])
        if event.chat_name:
            chat_update["chat_name"] = event.chat_name

        batch.set(msg_ref, msg_doc)
        batch.set(chat_ref, chat_update, merge=True)

        batch.commit()
        
        logger.info(f"✅ [Firestore] Message sauvegardé avec succès.")
        return True

    except Exception as e:
        logger.error(f"❌ [Firestore CRASH] : {str(e)}", exc_info=True)
        return False

# --- 4. RETRIEVAL FUNCTIONS (Inchangées) ---
# (Gardez ici les fonctions get_weekly_context, get_unprocessed_chats, etc. du fichier précédent)
# Pour gagner de la place je ne les remets pas, mais elles doivent rester dans le fichier !
def get_weekly_context(chat_id: str) -> str:
    # ... (Copiez-collez le code existant)
    try:
        now = datetime.utcnow()
        seven_days_ago = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0)
        docs = db.collection("chats").document(chat_id).collection("messages").where("stored_at", ">=", seven_days_ago).order_by("stored_at").stream()
        conversation_text = []
        for doc in docs:
            data = doc.to_dict()
            sender = data.get("sender", {}).get("attendee_name", "Inconnu")
            text = data.get("text", "")
            # Si pas de texte mais un fichier, on l'indique
            if not text and data.get("attachments"):
                 text = f"[📎 PIÈCE JOINTE: {data['attachments'][0].get('url', 'lien')}]"
            
            ts = data.get("stored_at")
            time_str = ts.strftime("%a %d %H:%M") if ts and hasattr(ts, 'strftime') else "?"
            conversation_text.append(f"[{time_str}] {sender}: {text}")
        return "\n".join(conversation_text)
    except Exception as e:
        logger.error(f"❌ Erreur lecture historique: {e}")
        return ""

def get_unprocessed_chats() -> List[str]:
    try:
        docs = db.collection("chats").where("needs_summary", "==", True).stream()
        return [doc.id for doc in docs]
    except: return []

def mark_chat_as_processed(chat_id: str):
    try:
        db.collection("chats").document(chat_id).update({"needs_summary": False, "ai_processed": True, "last_processed_at": google_firestore.SERVER_TIMESTAMP})
    except: pass

def get_new_messages_only(chat_id: str) -> str:
    # ... (Garder la logique existante)
    try:
        chat_doc = db.collection("chats").document(chat_id).get()
        if not chat_doc.exists: return ""
        last_processed = chat_doc.to_dict().get("last_processed_at")
        query = db.collection("chats").document(chat_id).collection("messages").order_by("stored_at")
        if last_processed: query = query.where("stored_at", ">", last_processed)
        docs = query.stream()
        conversation_text = []
        for doc in docs:
            msg = doc.to_dict()
            sender = msg.get("sender", {}).get("attendee_name", "Inconnu")
            text = msg.get("text", "") or "[Fichier Joint]"
            date_str = msg.get("stored_at").strftime("%Y-%m-%d") if msg.get("stored_at") else "???"
            conversation_text.append(f"[{date_str}] {sender}: {text}")
        return "\n".join(conversation_text)
    except: return ""