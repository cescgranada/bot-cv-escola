import os
import json
import base64
import io
import time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# === NOUS IDS DE LES CARPETES (Compte propi) ===
IDS_CARPETES = {
    "INFANTIL": "1U0kw8nUIXJaqFFaf9977A7I7o4yGcMDo",
    "PRIMARIA": "1duFjwCFNYAK63h9Sw36zxNfSEc5jsPIV",
    "ESO": "11XTfeSsk3oAMaQMlXgmao8bcB3Bmk2rG",
    "GENERAL": "1MjDr5z_JoxbdqEx7XE895VKZbBKTxCtZ"
}

def main():
    print("🚀 Iniciant el Bot de CVs (Versió Directa)...")
    
    # Configuració de credencials
    try:
        creds_info = json.loads(os.environ['GOOGLE_CREDENTIALS'])
        creds = Credentials.from_authorized_user_info(creds_info)
        
        gmail = build('gmail', 'v1', credentials=creds)
        drive = build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ Error de connexió amb Google: {e}")
        return

    # 1. Buscar correus no llegits amb adjunts PDF
    query = 'is:unread has:attachment filename:pdf'
    results = gmail.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])

    if not messages:
        print("☕ No hi ha correus nous per processar.")
        return

    print(f"📂 S'han trobat {len(messages)} correus. Començant la descàrrega...")

    for msg_ref in messages:
        try:
            msg = gmail.users().messages().get(userId='me', id=msg_ref['id']).execute()
            payload = msg.get('payload', {})
            headers = payload.get('headers', [])
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "").lower()
            
            # Decidir carpeta segons el contingut de l'Assumpte (Subject)
            folder_id = IDS_CARPETES["GENERAL"]
            target_name = "GENERAL"
            
            if "infantil" in subject:
                folder_id = IDS_CARPETES["INFANTIL"]
                target_name = "INFANTIL"
            elif "primaria" in subject or "primària" in subject:
                folder_id = IDS_CARPETES["PRIMARIA"]
                target_name = "PRIMÀRIA"
            elif "eso" in subject:
                folder_id = IDS_CARPETES["ESO"]
                target_name = "ESO"

            # Buscar el fitxer adjunt dins de les parts del correu
            parts = payload.get('parts', [])
            if not parts and 'body' in payload: parts = [payload] # Per correus simples

            pdf_trobat = False
            for part in parts:
                filename = part.get('filename')
                if filename and filename.lower().endswith('.pdf'):
                    att_id = part['body'].get('attachmentId')
                    attachment = gmail.users().messages().attachments().get(
                        userId='me', messageId=msg_ref['id'], id=att_id).execute()
                    
                    # Preparar dades per Drive
                    file_data = base64.urlsafe_b64decode(attachment['data'])
                    fh = io.BytesIO(file_data)
                    media = MediaIoBaseUpload(fh, mimetype='application/pdf')
                    
                    file_metadata = {
                        'name': filename,
                        'parents': [folder_id]
                    }
                    
                    # Pujar a Drive
                    drive.files().create(body=file_metadata, media_body=media).execute()
                    print(f"✅ CV '{filename}' guardat a {target_name}.")
                    pdf_trobat = True

            # Marcar el correu com a llegit només si hem processat el PDF
            gmail.users().messages().batchModify(
                userId='me', 
                body={'ids': [msg_ref['id']], 'removeLabelIds': ['UNREAD']}
            ).execute()
            
            # Espera d'un segon per no saturar l'API de Google amb els 100 correus
            time.sleep(0.5)

        except Exception as e:
            print(f"⚠️ Error processant el correu {msg_ref['id']}: {e}")

    print("🏁 Procés finalitzat. Revisa el teu Drive!")

if __name__ == '__main__':
    main()
