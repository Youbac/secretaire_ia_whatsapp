from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from datetime import datetime

# --- 1. SOUS-MODÈLES (Les briques) ---

class SenderInfo(BaseModel):
    """Identité de l'expéditeur normalisée."""
    attendee_id: Optional[str] = Field(default=None, description="ID unique (souvent le num tel)")
    attendee_name: Optional[str] = Field(default="Inconnu", description="Nom affiché")

class Attachment(BaseModel):
    """Structure d'un fichier joint (Image, Vocal, PDF)."""
    id: Optional[str] = None
    type: str = "unknown"  # image, audio, document...
    url: Optional[str] = None
    mimetype: Optional[str] = None
    filename: Optional[str] = None
    size: Optional[int] = 0

# --- 2. MODÈLE PRINCIPAL (L'Événement) ---

class UnipileMessageEvent(BaseModel):
    """
    Modèle strict et exhaustif pour l'événement 'message_received' d'Unipile.
    """
    # Métadonnées techniques
    event: str = Field(description="Type d'événement (ex: message_received)")
    account_id: str = Field(description="ID du compte Unipile connecté")
    
    # Identifiants Uniques
    message_id: str = Field(alias="id")  # Unipile envoie "id", on le mappe vers "message_id" pour la clarté
    chat_id: str
    
    # Horodatage
    timestamp: str 
    
    # Contenu du message
    # Unipile met le texte dans "text" OU "body" selon les versions, on gère les deux via alias
    text: Optional[str] = Field(default="", validation_alias="text") 
    
    # Qui parle ?
    sender: SenderInfo = Field(default_factory=SenderInfo)
    is_sender: bool = Field(default=False, description="True si c'est le propriétaire du compte qui parle")
    
    # Infos sur le Groupe (Nouveau & Important)
    chat_name: Optional[str] = Field(default=None, description="Nom du groupe si disponible")
    # Liste des IDs des participants (utile pour savoir qui est dans la discussion)
    attendees_ids: List[str] = Field(default=[], alias="attendees") 

    # Pièces jointes (Typées proprement maintenant)
    attachments: List[Attachment] = Field(default_factory=list)

    # --- Validateurs & Logique ---

    @field_validator('timestamp', mode='before')
    @classmethod
    def normalize_timestamp(cls, v):
        """Assure qu'on a toujours une date valide, même si vide."""
        if not v:
            return datetime.utcnow().isoformat()
        return v

    @field_validator('text', mode='before')
    @classmethod
    def ensure_text_string(cls, v):
        """Évite les crashs si le texte est None (ex: juste une image)."""
        return v if v else ""

    class Config:
        """Configuration Pydantic Avancée"""
        extra = "ignore"            # Ignore les champs inconnus (futurs updates Unipile)
        populate_by_name = True     # Permet d'utiliser nos noms (message_id) OU les alias (id)
        from_attributes = True      # Compatible avec les ORM si besoin
