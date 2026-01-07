import os
import base64
import json
from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv
from typing import List, Optional

# Charge les variables depuis .env (si présent en local)
load_dotenv()

class Settings(BaseSettings):
    """
    Configuration centralisée de l'application.
    Utilise Pydantic pour valider que les types sont bons.
    """
    
    # --- 1. FIREBASE (Le Cœur des Données) ---
    # Path local vers le JSON (ex: C:/Users/...)
    FIREBASE_CRED_PATH: str = "firebase_credentials.json"
    # Contenu Base64 (pour Render/Prod où on ne peut pas avoir de fichier)
    FIREBASE_CRED_BASE64: Optional[str] = None 

    # --- 2. UNIPILE (Le Tuyau WhatsApp) ---
    UNIPILE_DSN: str = ""      # URL API
    UNIPILE_API_KEY: str = ""  # Token
    UNIPILE_ACCOUNT_ID: str = "" # <--- AJOUTE CETTE LIGNE

    # --- 3. INTELLIGENCE ARTIFICIELLE ---
    GOOGLE_API_KEY: str = ""           # Clé Gemini
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"

    # --- 4. GOOGLE SHEETS (Le Tableau de Bord) ---
    SHEET_ID_SALES: str = "1t24fk9NKkm8wJgrJCq1T-kVRSR8_oyORCFbDf4JbWAk"
    SHEET_ID_STRATEGY: str = "1Z1v2-T9ifdiwF5-ec3e4mVsFRDq6jJ1REMEZYBO0R1k"
    SHEET_ID_OPS: str = "1EJF6FQfFJYNHaYbaMvZW_8joKzBiPcayamD_ke0MoRA"
    FINANCE_SHEET_ID: str = "1FcOogvLNHlaDIDjqqWiJ659-B8O4MNI-gjFaSNUthHk"

    # --- 5. ANNUAIRE & RÔLES ---
    MY_NUMBER: str = ""
    COFOUNDER_NUMBER_Vincent: str = ""

    # Équipe
    PHONE_Jin: str = ""
    PHONE_Muna_Brian: str = ""
    PHONE_Josiah: str = ""
    PHONE_Seb: str = ""
    PHONE_Jamyang: str = ""
    PHONE_Jovie: str = ""
    PHONE_Haznallah: str = ""
    PHONE_Brayant: str = ""

    # Partenaires
    PHONE_GOODREC_Partnership: str = ""
    PHONE_GOODREC_Hosts: str = ""
    PHONE_GOODREC_Foot: str = ""
    PHONE_GOODREC_Volley: str = ""

    # Sécurité / Filtrage
    IGNORED_NUMBERS_STR: str = ""

    @property
    def ignored_numbers(self) -> List[str]:
        """Transforme la string '123,456' en liste Python propre"""
        if not self.IGNORED_NUMBERS_STR:
            return []
        return [n.strip() for n in self.IGNORED_NUMBERS_STR.split(",")]

    def get_firebase_credentials(self):
        """
        Logique Intelligente de chargement des identifiants :
        1. Essaie d'abord la variable d'env BASE64 (Priorité Prod/Render).
        2. Sinon, cherche le fichier local (Priorité Dev/PC).
        """
        # Cas 1 : Production (Base64)
        if self.FIREBASE_CRED_BASE64:
            print("🔒 [Config] Mode Cloud détecté : Chargement depuis Base64")
            try:
                decoded = base64.b64decode(self.FIREBASE_CRED_BASE64)
                return json.loads(decoded)
            except Exception as e:
                print(f"❌ [Config] CRITICAL : Impossible de décoder le Base64 Firebase. {e}")
                return None
        
        # Cas 2 : Local (Fichier)
        if os.path.exists(self.FIREBASE_CRED_PATH):
            print(f"📂 [Config] Mode Local détecté : Chargement depuis {self.FIREBASE_CRED_PATH}")
            return self.FIREBASE_CRED_PATH
            
        print("⚠️ [Config] Warning : Aucun identifiant Firebase trouvé (ni Fichier, ni Base64).")
        return None

    class Config:
        env_file = ".env"
        case_sensitive = False 
        extra = "ignore" # Si le .env contient des trucs en trop, on s'en fiche

# Singleton : On instancie la config une seule fois pour gagner en perf
@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()  # <--- CETTE LIGNE EST CRUCIALE !
