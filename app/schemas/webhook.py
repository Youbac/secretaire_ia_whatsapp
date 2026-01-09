from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from datetime import datetime

# --- 1. SOUS-MODÈLES (Les briques) ---

class SenderInfo(BaseModel):
    """Identité de l'expéditeur normalisée."""
    attendee_id: Optional[str] = Field(default=None, description="ID unique")
    attendee_name: Optional[str] = Field(default="Inconnu", description="Nom affiché")
    
    class Config:
        extra = "ignore"

class Attachment(BaseModel):
    """Structure d'un fichier joint."""
    id: Optional[str] = None
    type: str = "unknown"
    url: Optional[str] = None
    mimetype: Optional[str] = None
    filename: Optional[str] = None
    size: Optional[int] = 0

class AttendeeItem(BaseModel):
    """
    CORRECTIF : Structure pour un participant dans la liste 'attendees'.
    Unipile envoie un objet complet, pas juste un ID string.
    """
    attendee_id: Optional[str] = None
    attendee_name: Optional[str] = None
    
    class Config:
        extra = "ignore"

# --- 2. MODÈLE PRINCIPAL (L'Événement) ---

class UnipileMessageEvent(BaseModel):
    """
    Modèle strict et exhaustif pour l'événement 'message_received' d'Unipile.
    """
    # Métadonnées techniques
    event: str = Field(description="Type d'événement")
    account_id: str = Field(description="ID du compte Unipile")
    
    # Identifiants Uniques
    message_id: str = Field(alias="id")  
    chat_id: str
    
    # Horodatage
    timestamp: str 
    
    # Contenu du message
    text: Optional[str] = Field(default="", validation_alias="text") 
    
    # Qui parle ?
    sender: SenderInfo = Field(default_factory=SenderInfo)
    is_sender: bool = Field(default=False)
    
    # Infos sur le Groupe
    chat_name: Optional[str] = Field(default=None)
    
    # CORRECTIF : On mappe le JSON 'attendees' vers une liste d'objets, pas de strings
    attendees_data: List[AttendeeItem] = Field(default=[], alias="attendees") 

    # Pièces jointes
    attachments: List[Attachment] = Field(default_factory=list)

    # --- Propriétés Calculées (Pour compatibilité) ---
    
    @property
    def attendees_ids(self) -> List[str]:
        """
        Extrait automatiquement la liste des IDs pour que le reste du code continue de marcher.
        """
        return [a.attendee_id for a in self.attendees_data if a.attendee_id]

    # --- Validateurs & Logique ---

    @field_validator('timestamp', mode='before')
    @classmethod
    def normalize_timestamp(cls, v):
        if not v:
            return datetime.utcnow().isoformat()
        return v

    @field_validator('text', mode='before')
    @classmethod
    def ensure_text_string(cls, v):
        return v if v else ""

    class Config:
        extra = "ignore"            
        populate_by_name = True     
        from_attributes = True