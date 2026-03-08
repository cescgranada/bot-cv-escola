import os
import json
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def main():
    # 1. Carregar credencials
    creds_json = json.loads(os.environ['GOOGLE_CREDENTIALS'])
    creds = Credentials.from_authorized_user_info(creds_json)

    service = build('gmail', 'v1', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)

    # 2. Buscar correus NO LLEGITS que tinguin un PDF
    query = 'is:unread has:attachment filename:pdf'
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])

    if not messages:
        print("No s'han trobat nous correus amb CVs per processar.")
        return

    for msg in messages:
        m = service.users().messages().get(userId='me', id=msg['id']).execute()
        print(f"Processant correu ID: {msg['id']}")
        
        # Buscar el PDF en els adjunts
        payload = m.get('payload', {})
        parts = payload.get('parts', [])
        
        for part in parts:
            if part.get('filename') and part['filename'].lower().endswith('.pdf'):
                att_id = part['body'].get('attachmentId')
                attachment = service.users().messages().attachments().get(
                    userId='me', messageId=msg['id'], id=att_id).execute()
                
                file_data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))
                
                # 3. Pujar a Google Drive
                file_metadata = {'name': part['filename']}
                media_body = build('drive', 'v3', credentials=creds).files().create(
                    body=file_metadata,
                    media_body=base64.urlsafe_b64decode(attachment['data']),
                    fields='id'
                ).execute()
                
                print(f"✅ CV '{part['filename']}' pujat correctament a Drive.")

        # 4. Marcar el correu com a LLEGIT perquè no es torni a processar
        service.users().messages().batchModify(
            userId='me',
            body={'ids': [msg['id']], 'removeLabelIds': ['UNREAD']}
        ).execute()

if __name__ == '__main__':
    main()
