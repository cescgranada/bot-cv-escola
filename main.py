import os
import json
import base64
import io
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

# === CONFIGURACIÓ DE LES CARPETES ===
IDS_CARPETES = {
    "INFANTIL": "1CBISCKWhZuAGIRZmqSpp0APfLdO5EF3T",
    "PRIMARIA": "1ZPilSJZgOb_1YP5H3aJDrwB9FG7fQ4Vn",
    "ESO": "1lMyaQCafWuYqROiqyqf51ROwmt4baodT",
    "GENERAL": "10UttFXthAAx0GhWI8fFkuADfEOZ9fUzu"
}

def determinar_carpeta(subject, body):
    """Lògica robusta per classificar el CV segons paraules clau."""
    text_complet = (subject + " " + body).lower()
    
    if any(x in text_complet for x in ["infantil", "p3", "p4", "p5", "llar", "bressol"]):
        return IDS_CARPETES["INFANTIL"]
    elif any(x in text_complet for x in ["primaria", "primària", "cicle", "clicle inicial", "cicle mitjà", "cicle superior"]):
        return IDS_CARPETES["PRIMARIA"]
    elif any(x in text_complet for x in ["eso", "secundaria", "secundària", "batxillerat", "materia", "matèria"]):
        return IDS_CARPETES["ESO"]
    
    return IDS_CARPETES["GENERAL"]

def cercar_pdfs_recursiu(parts):
    """Explora totes les capes del correu per trobar adjunts PDF."""
    trobats = []
    for part in parts:
        filename = part.get('filename', '')
        if filename and filename.lower().endswith('.pdf'):
            trobats.append(part)
        if 'parts' in part:
            trobats.extend(cercar_pdfs_recursiu(part['parts']))
    return trobats

def main():
    print("🚀 Iniciant el Bot de CVs del Nou Patufet...")
    
    try:
        creds_info = json.loads(os.environ['GOOGLE_CREDENTIALS'])
        creds = Credentials.from_authorized_user_info(creds_info)
        
        gmail = build('gmail', 'v1', credentials=creds)
        drive = build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ Error carregant credencials o APIs: {e}")
        return

    # Busquem correus no llegits amb PDF
    try:
        query = 'is:unread has:attachment filename:pdf'
        results = gmail.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
    except HttpError as e:
        print(f"❌ Error en connectar amb Gmail: {e}")
        return

    if not messages:
        print("☕ Tot al dia! No hi ha correus nous per processar.")
        return

    print(f"📂 S'han trobat {len(messages)} correus nous. Processant...")

    for msg_ref in messages:
        try:
            msg = gmail.users().messages().get(userId='me', id=msg_ref['id']).execute()
            payload = msg.get('payload', {})
            headers = payload.get('headers', [])
            
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "")
            snippet = msg.get('snippet', "") # El resum del cos del correu
            
            # Decidim la carpeta
            folder_id = determinar_carpeta(subject, snippet)
            
            parts = payload.get('parts', [])
            if not parts: parts = [payload]
            
            pdfs = cercar_pdfs_recursiu(parts)
            
            for pdf in pdfs:
                att_id = pdf['body'].get('attachmentId')
                attachment = gmail.users().messages().attachments().get(
                    userId='me', messageId=msg_ref['id'], id=att_id).execute()
                
                file_data = base64.urlsafe_b64decode(attachment['data'])
                
                # Pujada a Drive
                fh = io.BytesIO(file_data)
                media = MediaIoBaseUpload(fh, mimetype='application/pdf', resumable=True)
                
                file_metadata = {
                    'name': f"{pdf['filename']}",
                    'parents': [folder_id]
                }
                
                f = drive.files().create(body=file_metadata, media_body=media, fields='id').execute()
                print(f"✅ CV '{pdf['filename']}' guardat correctament.")

            # Marcar com a llegit
            gmail.users().messages().batchModify(
                userId='me',
                body={'ids': [msg_ref['id']], 'removeLabelIds': ['UNREAD']}
            ).execute()

        except Exception as e:
            print(f"⚠️ Error processant el correu {msg_ref['id']}: {e}")

    print("🏁 Procés finalitzat amb èxit.")

if __name__ == '__main__':
    main()
