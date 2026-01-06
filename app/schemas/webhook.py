from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from datetime import datetime

# --- 1. Sous-Modèles (Les briques) ---

class SenderInfo(BaseModel):
    """Infos sur la personne qui envoie le message"""
    attendee_id: Optional[str] = None      # ID unique (ex: numéro de tel)
    attendee_name: Optional[str] = "Inconnu" # Nom affiché dans WhatsApp

# --- 2. Modèle Principal (Le Message) ---

class UnipileMessageEvent(BaseModel):
    """
    Représente un événement 'Message' reçu d'Unipile.
    Validé strictement pour éviter les erreurs de type 'KeyError' plus tard.
    """
    event: str  # Le type d'action (message_received, message_sent...)
    account_id: str  # <--- AJOUTE CETTE LIGNE (C'est crucial)

    # Identifiants cruciaux
    message_id: str
    chat_id: str
    
    # Contenu
    timestamp: str 
    # Unipile appelle le champ "message", mais nous on préfère l'appeler "text" dans notre code
    text: Optional[str] = Field(alias="message", default="")
    
    # Qui ?
    sender: SenderInfo = Field(default_factory=SenderInfo)
    is_sender: bool = False # True si c'est TOI qui as écrit
    
    # Média (Images, Vocaux...) - On garde la liste brute pour l'instant
    attachments: List[Any] = []

    # --- Validateurs Intelligents ---
    
    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v):
        """Si le timestamp est vide ou nul, on met l'heure actuelle pour ne pas planter"""
        if not v:
            return datetime.now().isoformat()
        return v

    class Config:
        # Si Unipile ajoute des nouveaux champs dans le futur, on les ignore (pas de crash)
        extra = "ignore" 
        # Permet d'utiliser message.text (notre nom) OU message.message (nom Unipile)
        populate_by_name = True
