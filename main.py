import os
import io
import base64
import json
import pdfplumber
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials

# CONFIGURACIÓ DE LES TEVES CARPETES DE DRIVE
FOLDER_IDS = {
    "Educació_Infantil": "1CBISCKWhZuAGIRZmqSpp0APfLdO5EF3T",
    "Educació_Primària": "1ZPilSJZgOb_1YP5H3aJDrwB9FG7fQ4Vn",
    "ESO": "1lMyaQCafWuYqROiqyqf51ROwmt4baodT"
}

# PARAULES CLAU PER A LA CLASSIFICACIÓ
KEYWORDS = {
    "Educació_Infantil": ["infantil", "llar d'infants", "parvulari", "p3", "p4", "p5", "0-3", "0-6"],
    "Educació_Primària": ["primària", "primaria", "mestre", "mestra", "cicle inicial"],
    "ESO": ["eso", "secundària", "secundaria", "batxillerat", "adolescents", "professor", "professora"]
}

def get_services():
    # Carreguem les credencials des del Secret de GitHub
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("No s'ha trobat el secret GOOGLE_CREDENTIALS")
    
    info = json.loads(creds_json)
    creds = Credentials.from_authorized_user_info(info)
    
    gmail = build('gmail', 'v1', credentials=creds)
    drive = build('drive', 'v3', credentials=creds)
    return gmail, drive

def extract_text_from_pdf(content):
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + " "
            return full_text.lower()
    except Exception as e:
        print(f"⚠️ Error analitzant el PDF: {e}")
        return ""

def classify_cv(text):
    found_categories = []
    for category, tags in KEYWORDS.items():
        if any(tag in text for tag in tags):
            found_categories.append(category)
    return found_categories

def main():
    gmail, drive = get_services()
    
    # BUSQUEM: No llegits + Enviats a l'adreça de treball + que tinguin CV o Currículum
    query = 'is:unread to:treballaambnosaltres@noupatufet.coop (subject:currículum OR subject:cv OR "cv" OR "currículum")'
    
    results = gmail.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])

    if not messages:
        print("📭 No hi ha currículums nous per processar.")
        return

    print(f"📩 S'han trobat {len(messages)} correus nous.")

    for msg in messages:
        msg_data = gmail.users().messages().get(userId='me', id=msg['id']).execute()
        payload = msg_data.get('payload', {})
        parts = payload.get('parts', [])

        for part in parts:
            filename = part.get('filename')
            # Només processem fitxers PDF
            if filename and filename.lower().endswith('.pdf'):
                att_id = part['body'].get('attachmentId')
                attachment = gmail.users().messages().attachments().get(
                    userId='me', messageId=msg['id'], id=att_id
                ).execute()
                
                file_data = base64.urlsafe_b64decode(attachment['data'])
                
                # Analitzem el text del PDF
                pdf_text = extract_text_from_pdf(file_data)
                categories = classify_cv(pdf_text)
                
                # Si no troba paraules clau, ho enviem a ESO per defecte (o podríem crear una carpeta 'Altres')
                if not categories:
                    categories = ["ESO"]
                
                # Pugem el fitxer a cada carpeta corresponent (per si és polivalent)
                for cat in list(set(categories)):
                    file_metadata = {
                        'name': f"{filename}",
                        'parents': [FOLDER_IDS[cat]]
                    }
                    media = MediaIoBaseUpload(io.BytesIO(file_data), mimetype='application/pdf')
                    drive.files().create(body=file_metadata, media_body=media).execute()
                    print(f"✅ Fitxer '{filename}' desat a la carpeta: {cat}")

        # Un cop processat, el marquem com a llegit perquè no es torni a processar
        gmail.users().messages().batchModify(
            userId='me',
            body={'removeLabelIds': ['UNREAD'], 'ids': [msg['id']]}
        ).execute()

if __name__ == "__main__":
    main()
