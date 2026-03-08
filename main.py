import os
import json
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# 1. Configurar credencials des de GitHub Secrets
creds_json = json.loads(os.environ['GOOGLE_CREDENTIALS'])
creds = Credentials.from_authorized_user_info(creds_json)

service = build('gmail', 'v1', credentials=creds)
drive_service = build('drive', 'v3', credentials=creds)

# 2. Buscar correus amb CVs (etiqueta "CV" o paraula clau)
query = 'has:attachment filename:pdf'
results = service.users().messages().list(userId='me', q=query).execute()
messages = results.get('messages', [])

if not messages:
    print("No s'han trobat nous CVs.")
else:
    for msg in messages:
        m = service.users().messages().get(userId='me', id=msg['id']).execute()
        
        # Buscar el PDF en els fitxers adjunts
        for part in m['payload'].get('parts', []):
            if part['filename'].lower().endswith('.pdf'):
                att_id = part['body'].get('attachmentId')
                att = service.users().messages().attachments().get(userId='me', messageId=msg['id'], id=att_id).execute()
                data = base64.urlsafe_b64decode(att['data'])
                
                # Pujar a Google Drive (substitueix l'ID per la teva carpeta)
                file_metadata = {'name': part['filename']}
                media = build('drive', 'v3', credentials=creds).files().create(
                    body=file_metadata,
                    media_body=base64.urlsafe_b64decode(att['data']),
                    fields='id'
                ).execute()
                print(f"CV Pujat amb èxit: {part['filename']}")
