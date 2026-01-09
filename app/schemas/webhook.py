from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Any
from datetime import datetime

# --- 1. SOUS-MODÈLES ---

class SenderInfo(BaseModel):
    """Identité de l'expéditeur."""
    attendee_id: Optional[str] = Field(default=None)
    attendee_name: Optional[str] = Field(default="Inconnu")
    
    class Config:
        extra = "ignore"

class Attachment(BaseModel):
    id: Optional[str] = None
    type: str = "unknown"
    url: Optional[str] = None
    filename: Optional[str] = None

class AttendeeItem(BaseModel):
    """Structure pour les participants (liste d'objets complexes)."""
    attendee_id: Optional[str] = None
    attendee_name: Optional[str] = None
    
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
    
    # LE CHAMP PROBLÉMATIQUE (On le laisse simple ici)
    text: str = Field(default="") 
    
    # Le reste...
    sender: SenderInfo = Field(default_factory=SenderInfo)
    is_sender: bool = Field(default=False)
    chat_name: Optional[str] = Field(default=None)
    attendees_data: List[AttendeeItem] = Field(default=[], alias="attendees") 
    attachments: List[Attachment] = Field(default_factory=list)

    # --- LA SOLUTION MAGIQUE ---
    @model_validator(mode='before')
    @classmethod
    def unify_text_field(cls, data: Any) -> Any:
        """
        Va chercher le contenu du message PEU IMPORTE son nom.
        Unipile change souvent entre 'message', 'text', 'body'.
        On attrape tout et on le range dans 'text'.
        """
        if isinstance(data, dict):
            # On cherche le contenu dans l'ordre de priorité
            content = data.get('text') or data.get('message') or data.get('body')
            
            # Si on a trouvé quelque chose, on l'impose dans le champ 'text'
            if content:
                data['text'] = str(content) # On s'assure que c'est du string
        return data

    # --- Propriétés Helper ---
    @property
    def attendees_ids(self) -> List[str]:
        return [a.attendee_id for a in self.attendees_data if a.attendee_id]

    @field_validator('timestamp', mode='before')
    @classmethod
    def normalize_timestamp(cls, v):
        return v if v else datetime.utcnow().isoformat()

    class Config:
        extra = "ignore"            
        populate_by_name = True     
        from_attributes = True