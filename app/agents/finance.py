import requests
import google.generativeai as genai
import gspread
import json
import re
from oauth2client.service_account import ServiceAccountCredentials
from app.config import settings
from datetime import datetime

class FinanceAnalyst:
    def __init__(self):
        # 1. Config Gemini
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
        
        # 2. Config WhatsApp (La conversation Finance)
        self.chat_id = "-zeA_LzlUnS3nCeRyIdS5Q"
        
        # 3. Connexion Google Sheets (Via tes creds Firebase)
        self.sheet = self._connect_to_sheets()

    def _connect_to_sheets(self):
        """Connecte le script au Google Sheet Finance"""
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds_data = settings.get_firebase_credentials()
            
            if not creds_data:
                print("❌ [Finance] Pas d'identifiants trouvés pour Google Sheets.")
                return None

            # Si on est en local (chemin de fichier) ou sur le Cloud (Dictionnaire JSON)
            if isinstance(creds_data, str):
                creds = ServiceAccountCredentials.from_json_keyfile_name(creds_data, scope)
            else:
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_data, scope)

            client = gspread.authorize(creds)
            # Ouvre le fichier par son ID et prend la première feuille
            return client.open_by_key(settings.FINANCE_SHEET_ID).sheet1
        except Exception as e:
            print(f"❌ [Finance] Erreur de connexion au Sheet : {e}")
            return None

    def get_recent_messages(self, limit=30):
        """Récupère les messages bruts via Unipile"""
        url = f"https://{settings.UNIPILE_DSN}/api/v1/chats/{self.chat_id}/messages"
        headers = {"X-API-Key": settings.UNIPILE_API_KEY}
        
        try:
            response = requests.get(url, headers=headers, params={"limit": limit})
            if response.status_code != 200:
                return ""
            
            messages = response.json().get("items", [])
            history = []
            for msg in messages:
                if msg.get("type") == "text":
                    sender = "Moi" if msg.get("sender_id") == settings.UNIPILE_ACCOUNT_ID else "Partenaire"
                    # On nettoie un peu le timestamp pour qu'il soit lisible
                    ts = msg.get("timestamp")
                    history.append(f"[{ts}] {sender}: {msg.get('text')}")
            
            return "\n".join(reversed(history))
        except Exception:
            return ""

    def process_and_save(self):
        """Fonction principale : Lit, Analyse, et Sauvegarde"""
        print("🔍 Lecture des messages WhatsApp...")
        conversation = self.get_recent_messages()
        if not conversation:
            return "Pas de messages ou erreur WhatsApp."

        print("🧠 Analyse par Gemini en cours...")
        # On demande du JSON strict pour pouvoir l'insérer dans le tableau
        prompt = f"""
        Analyse cette conversation WhatsApp financière.
        Extrais chaque dépense ou gain mentionné explicitement.
        
        Format de sortie OBLIGATOIRE : Une liste JSON pure. Rien d'autre.
        Exemple :
        [
            {{"date": "2024-05-20", "type": "DEPENSE", "montant": 25.50, "description": "Ballons Nike", "qui": "Vincent"}},
            {{"date": "2024-05-21", "type": "GAIN", "montant": 100, "description": "Inscription Team A", "qui": "Client"}}
        ]

        Si rien n'est trouvé, renvoie juste une liste vide : []

        Conversation :
        {conversation}
        """

        try:
            response = self.model.generate_content(prompt)
            # Nettoyage de la réponse (au cas où Gemini met des ```json ... ```)
            clean_json = response.text.replace("```json", "").replace("```", "").strip()
            transactions = json.loads(clean_json)

            if not transactions:
                return "✅ Aucune nouvelle transaction détectée."

            # Sauvegarde dans le Sheet
            if self.sheet:
                count = 0
                for t in transactions:
                    # On prépare la ligne à ajouter
                    # Ordre des colonnes : DATE | TYPE | MONTANT | DESCRIPTION | QUI
                    row = [
                        t.get("date", datetime.now().strftime("%Y-%m-%d")),
                        t.get("type", "INCONNU"),
                        t.get("montant", 0),
                        t.get("description", ""),
                        t.get("qui", "Inconnu")
                    ]
                    self.sheet.append_row(row)
                    count += 1
                return f"✅ Succès ! {count} transactions ajoutées au Google Sheet."
            else:
                return "⚠️ Transactions trouvées mais impossible d'accéder au Sheet."

        except json.JSONDecodeError:
            return "❌ Erreur : Gemini n'a pas renvoyé un JSON valide."
        except Exception as e:
            return f"❌ Erreur critique : {e}"

if __name__ == "__main__":
    bot = FinanceAnalyst()
    print(bot.process_and_save())
