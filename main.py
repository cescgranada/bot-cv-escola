import os
import json
import base64
import io
import time
import re
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# === CONFIGURACIÓ DE LES CARPETES ===
IDS_CARPETES = {
    "INFANTIL": "1U0kw8nUIXJaqFFaf9977A7I7o4yGcMDo",
    "PRIMARIA": "1duFjwCFNYAK63h9Sw36zxNfSEc5jsPIV",
    "ESO": "11XTfeSsk3oAMaQMlXgmao8bcB3Bmk2rG",
    "GENERAL": "1MjDr5z_JoxbdqEx7XE895VKZbBKTxCtZ"
}

def extreure_especialitat(text):
    """Cerca paraules clau per determinar l'especialitat del candidat."""
    t = text.lower()
    especialitats = {
        "Angles": ["anglès", "english", "angles"],
        "Educacio-Fisica": ["física", "esport", "ef", "gym", "educació física"],
        "Catala": ["català", "catala", "filologia"],
        "Castella": ["castellà", "castellano", "lengua"],
        "Matematiques": ["mates", "matemàtiques", "matemáticas", "números"],
        "Musica": ["música", "music", "instrument"],
        "Artistica": ["art", "plàstica", "dibuix"],
        "Tecnologia": ["tecnologia", "informàtica", "tic", "programació"],
        "Primaria": ["primaria", "primària"],
        "Infantil": ["infantil", "llar", "bressol"]
    }
    for esp, claus in especialitats.items():
        if any(c in t for c in claus):
            return esp
    return "General"

def main():
    print("🚀 Iniciant Prova de 25 CVs amb format AAAA-MM-DD...")
    
    creds_info = json.loads(os.environ['GOOGLE_CREDENTIALS'])
    creds = Credentials.from_authorized_user_info(creds_info)
    
    gmail = build('gmail', 'v1', credentials=creds)
    drive = build('drive', 'v3', credentials=creds)

    # Busquem els últims 25 correus amb PDF
    results = gmail.users().messages().list(userId='me', q='has:attachment filename:pdf', maxResults=25).execute()
    messages = results.get('messages', [])

    if not messages:
        print("No s'han trobat missatges.")
        return

    for msg_ref in messages:
        try:
            msg = gmail.users().messages().get(userId='me', id=msg_ref['id']).execute()
            headers = msg['payload'].get('headers', [])
            
            # 1. Extreure i formatar la Data (AAAA-MM-DD)
            date_header = next((h['value'] for h in headers if h['name'] == 'Date'), "")
            try:
                # Intentem netejar la data per al parsing
                clean_date = re.sub(r' \(.*\)', '', date_header).strip()
                date_dt = datetime.strptime(clean_date[:25].strip(), '%a, %d %b %Y %H:%M:%S')
                data_iso = date_dt.strftime('%Y-%m-%d')
            except:
                data_iso = "0000-00-00"

            # 2. Extreure el Nom del Remitent
            from_header = next((h['value'] for h in headers if h['name'] == 'From'), "Desconegut")
            nom_persona = re.sub(r'<.*?>', '', from_header).replace('"', '').strip()
            
            # 3. Especialitat i Carpeta
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "")
            snippet = msg.get('snippet', "")
            text_analisi = (subject + " " + snippet).lower()
            
            especialitat = extreure_especialitat(text_analisi)
            
            folder_id = IDS_CARPETES["GENERAL"]
            if "infantil" in text_analisi: folder_id = IDS_CARPETES["INFANTIL"]
            elif "primaria" in text_analisi or "primària" in text_analisi: folder_id = IDS_CARPETES["PRIMARIA"]
            elif "eso" in text_analisi or "secundaria" in text_analisi: folder_id = IDS_CARPETES["ESO"]

            # 4. Adjunts
            parts = msg['payload'].get('parts', [])
            if not parts: parts = [msg['payload']]
            
            for part in parts:
                if part.get('filename') and part['filename'].lower().endswith('.pdf'):
                    # NOU FORMAT: AAAA-MM-DD - Especialitat - Nom.pdf
                    nou_nom = f"{data_iso} - {especialitat} - {nom_persona}.pdf"
                    
                    att_id = part['body'].get('attachmentId')
                    attachment = gmail.users().messages().attachments().get(
                        userId='me', messageId=msg_ref['id'], id=att_id).execute()
                    
                    file_data = base64.urlsafe_b64decode(attachment['data'])
                    fh = io.BytesIO(file_data)
                    media = MediaIoBaseUpload(fh, mimetype='application/pdf')
                    
                    file_metadata = {'name': nou_nom, 'parents': [folder_id]}
                    drive.files().create(body=file_metadata, media_body=media).execute()
