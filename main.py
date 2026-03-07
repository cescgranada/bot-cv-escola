import os
import io
import base64
import json
import pdfplumber
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# ELS TEUS IDs DE CARPETA
FOLDER_IDS = {
    "Educació_Infantil": "1CBISCKWhZuAGIRZmqSpp0APfLdO5EF3T",
    "Educació_Primària": "1ZPilSJZgOb_1YP5H3aJDrwB9FG7fQ4Vn",
    "ESO": "1lMyaQCafWuYqROiqyqf51ROwmt4baodT"
}

# PARAULES CLAU PER CLASSIFICAR
KEYWORDS = {
    "Educació_Infantil": ["infantil", "llar d'infants", "parvulari", "0-3", "0-6"],
    "Educació_Primària": ["primària", "primaria", "mestre", "mestra"],
    "ESO": ["eso", "secundària", "secundaria", "batxillerat", "adolescents"]
}

def get_services():
    # Llegim el contingut del fitxer JSON que vas posar als Secrets
    info = json.loads(os.environ.get("GOOGLE_CREDENTIALS"))
    
    # Com que és un ID de client OAuth, necessitem crear el flux
    # Nota: La primera vegada podria requerir una autorització manual si no tenim el token.
    # Per simplificar, usarem el mètode de les credencials directes.
    creds = Credentials.from_authorized_user_info(info)
    
    gmail = build('gmail', 'v1', credentials=creds)
    drive = build('drive', 'v3', credentials=creds)
    return gmail, drive

def extract_text_from_pdf(content):
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return " ".join([page.extract_text() for page in pdf.pages if page.extract_text()]).lower()
    except Exception as e:
        print(f"Error llegint PDF: {e}")
        return ""

def classify_cv(text):
    categories = []
    for cat, keywords in KEYWORDS.items():
        if any(kw in text for kw in keywords):
            categories.append(cat)
    return categories

def main():
    try:
        gmail, drive = get_services()
        
        # Busquem correus no llegits amb "currículum" o "cv"
        query = 'is:unread (subject:currículum OR subject:cv OR "cv" OR "currículum")'
        results = gmail.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])

        if not messages:
            print("No hi ha correus nous per processar.")
            return

        for msg in messages:
            msg_data = gmail.users().messages().get(userId='me', id=msg['id']).execute()
            payload = msg_data.get('payload', {})
            parts = payload.get('parts', [])

            for part in parts:
                filename = part.get('filename')
                if filename and filename.lower().endswith('.pdf'):
                    att_id = part['body'].get('attachmentId')
                    att = gmail.users().messages().attachments().get(userId='me', messageId=msg['id'], id=att_id).execute()
                    data = base64.urlsafe_b64decode(att['data'])
                    
                    text = extract_text_from_pdf(data)
                    categories = classify_cv(text)
                    
                    if not categories:
                        categories = ["ESO"] # Carpeta per defecte si no troba res

                    for cat in categories:
                        file_metadata = {'name': filename, 'parents': [FOLDER_IDS[cat]]}
                        media = MediaIoBaseUpload(io.BytesIO(data), mimetype='application/pdf')
                        drive.files().create(body=file_metadata, media_body=media).execute()
                        print(f"✅ {filename} pujat a {cat}")

            # Marcar com a llegit
            gmail.users().messages().batchModify(
                userId='me', body={'removeLabelIds': ['UNREAD'], 'ids': [msg['id']]}
            ).execute()

    except Exception as e:
        print(f"S'ha produït un error: {e}")

if __name__ == "__main__":
    main()
