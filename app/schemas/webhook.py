from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Any
from datetime import datetime

# --- 1. SOUS-MODÈLES ---

class AttendeeSpecifics(BaseModel):
    """
    Détails techniques (contient le numéro de téléphone).
    """
    phone_number: Optional[str] = None
    
    class Config:
        extra = "ignore"

class SenderInfo(BaseModel):
    """Identité de l'expéditeur."""
    attendee_id: Optional[str] = Field(default=None)
    attendee_name: Optional[str] = Field(default="Inconnu")
    attendee_specifics: Optional[AttendeeSpecifics] = None # <-- AJOUT ICI
    
    @property
    def phone(self) -> str:
        """Helper pour récupérer le téléphone directement."""
        if self.attendee_specifics and self.attendee_specifics.phone_number:
            return self.attendee_specifics.phone_number
        return ""

    class Config:
        extra = "ignore"

class Attachment(BaseModel):
    id: Optional[str] = None
    type: str = "unknown"
    url: Optional[str] = None
    filename: Optional[str] = None

class AttendeeItem(BaseModel):
    """Structure pour les participants."""
    attendee_id: Optional[str] = None
    attendee_name: Optional[str] = None
    attendee_specifics: Optional[AttendeeSpecifics] = None # <-- AJOUT ICI
    
    @property
    def phone(self) -> str:
        """Helper pour récupérer le téléphone directement."""
        if self.attendee_specifics and self.attendee_specifics.phone_number:
            return self.attendee_specifics.phone_number
        return ""

    class Config:
        extra = "ignore"

# --- 2. MODÈLE PRINCIPAL ---

class UnipileMessageEvent(BaseModel):
    # Champs techniques
    event: str
    account_id: str
    message_id: str = Field(alias="id")  
    chat_id: str
    timestamp: str 
    
    # Contenu du message (Géré par le validateur unify_text_field)
    text: str = Field(default="") 
    
    # Le reste...
    sender: SenderInfo = Field(default_factory=SenderInfo)
    is_sender: bool = Field(default=False)
    chat_name: Optional[str] = Field(default=None)
    attendees_data: List[AttendeeItem] = Field(default=[], alias="attendees") 
    attachments: List[Attachment] = Field(default_factory=list)

    # --- LA SOLUTION MAGIQUE (Contenu du message) ---
    @model_validator(mode='before')
    @classmethod
    def unify_text_field(cls, data: Any) -> Any:
        """
        Attrape le contenu qu'il s'appelle 'text', 'message' ou 'body'.
        """
        if isinstance(data, dict):
            content = data.get('text') or data.get('message') or data.get('body')
            if content:
                data['text'] = str(content)
        return data

    # --- Propriétés Helper ---
    @property
    def attendees_ids(self) -> List[str]:
        return [a.attendee_id for a in self.attendees_data if a.attendee_id]

    @property
    def sender_phone(self) -> str:
        """Raccourci pour avoir le téléphone de l'expéditeur"""
        return self.sender.phone

    @field_validator('timestamp', mode='before')
    @classmethod
    def normalize_timestamp(cls, v):
        return v if v else datetime.utcnow().isoformat()

    class Config:
        extra = "ignore"            
        populate_by_name = True     
        from_attributes = True