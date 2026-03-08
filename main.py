import os
import json
import base64
import io
import time
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# === CONFIGURACIÓ ===
IDS_CARPETES = {
    "INFANTIL": "1U0kw8nUIXJaqFFaf9977A7I7o4yGcMDo",
    "PRIMARIA": "1duFjwCFNYAK63h9Sw36zxNfSEc5jsPIV",
    "ESO": "11XTfeSsk3oAMaQMlXgmao8bcB3Bmk2rG",
    "GENERAL": "1MjDr5z_JoxbdqEx7XE895VKZbBKTxCtZ"
}
DESTINATARIS_RESUM = ["francesc.granada@noupatufet.coop", "ingrid.ribelles@noupatufet.coop"]

def extreure_especialitat(text):
    t = text.lower()
    especialitats = {
        "Angles": ["anglès", "english", "aicle", "angles"],
        "Ed-Fisica": ["física", "esport", "ef", "gym", "educació física"],
        "Catala-Castella": ["català", "castellà", "llengua", "filologia"],
        "STEAM": ["mates", "tecnologia", "robòtica", "ciències", "biologia"],
        "Musica-Art": ["música", "art", "plàstica"],
        "Atencio-Diversitat": ["nee", "psicopedagogia", "orientació", "logopèdia"]
    }
    for esp, claus in especialitats.items():
        if any(c in t for c in claus): return esp
    return "General"

def extreure_pdfs_recursiu(parts):
    """Busca PDFs en qualsevol nivell de profunditat del correu."""
    pdfs = []
    for part in parts:
        if part.get('filename') and part['filename'].lower().endswith('.pdf'):
            pdfs.append(part)
        if 'parts' in part:
            pdfs.extend(extreure_pdfs_recursiu(part['parts']))
    return pdfs

def enviar_resum(gmail, llista_cvs):
    if not llista_cvs:
        cos = "Hola,\n\nAquest dilluns no s'ha rebut cap currículum nou."
    else:
        fileres = "\n".join([f"- {cv}" for cv in llista_cvs])
        cos = f"Hola,\n\nS'han processat correctament els següents currículums aquest matí:\n\n{fileres}\n\nJa estan disponibles a les carpetes corresponents del Drive."
    
    # Afegim 'utf-8' per evitar problemes amb accents i caràcters especials
    msg = MIMEText(cos, 'plain', 'utf-8')
    msg['Subject'] = f"Resum Setmanal CVs - {datetime.now().strftime('%d/%m/%Y')}"
    msg['To'] = ", ".join(DESTINATARIS_RESUM)
    
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    gmail.users().messages().send(userId='me', body={'raw': raw}).execute()

def main():
    print("🚀 Iniciant processament setmanal de CVs...")
    creds_info = json.loads(os.environ['GOOGLE_CREDENTIALS'])
    creds = Credentials.from_authorized_user_info(creds_info)
    gmail = build('gmail', 'v1', credentials=creds)
    drive = build('drive', 'v3', credentials=creds)

    # Només correus NO LLEGITS amb PDF
    query = 'is:unread has:attachment filename:pdf'
    
    # Recollim TOTS els missatges (paginació)
    messages = []
    request = gmail.users().messages().list(userId='me', q=query)
    while request is not None:
        response = request.execute()
        messages.extend(response.get('messages', []))
        request = gmail.users().messages().list_next(previous_request=request, previous_response=response)
    
    cvs_processats = []

    for msg_ref in messages:
        try:
            msg = gmail.users().messages().get(userId='me', id=msg_ref['id']).execute()
            headers = msg['payload'].get('headers', [])
            
            # Metadata: Nom segur (sense caràcters estranys)
            from_h = next((h['value'] for h in headers if h['name'] == 'From'), "Desconegut")
            nom_candidat = re.sub(r'<.*?>', '', from_h).replace('"', '').strip()
            nom_candidat = re.sub(r'[/\\?%*:|"<>]', '', nom_candidat) # Neteja per nom d'arxiu
            
            # Metadata: Data robusta
            date_h = next((h['value'] for h in headers if h['name'] == 'Date'), "")
            try:
                dt = parsedate_to_datetime(date_h)
                data_iso = dt.strftime('%Y-%m-%d')
            except: 
                data_iso = datetime.now().strftime('%Y-%m-%d')

            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "")
            snippet = msg.get('snippet', "")
            
            # Classificació
            text_full = (subject + " " + snippet).lower()
            especialitat = extreure_especialitat(text_full)
            
            folder_id = IDS_CARPETES["GENERAL"]
            if "infantil" in text_full: folder_id = IDS_CARPETES["INFANTIL"]
            elif any(x in text_full for x in ["primaria", "primària"]): folder_id = IDS_CARPETES["PRIMARIA"]
            elif any(x in text_full for x in ["eso", "secundaria"]): folder_id = IDS_CARPETES["ESO"]

            # Processar Adjunts (Recursivament)
            parts = msg['payload'].get('parts', [msg['payload']])
            adjunts_pdf = extreure_pdfs_recursiu(parts)
            
            for part in adjunts_pdf:
                nou_nom = f"{data_iso} - {especialitat} - {nom_candidat}.pdf"
                
                att_id = part['body'].get('attachmentId')
                attachment = gmail.users().messages().attachments().get(
                    userId='me', messageId=msg_ref['id'], id=att_id).execute()
                
                media = MediaIoBaseUpload(io.BytesIO(base64.urlsafe_b64decode(attachment['data'])), mimetype='application/pdf')
                drive.files().create(body={'name': nou_nom, 'parents': [folder_id]}, media_body=media).execute()
                
                cvs_processats.append(nou_nom)
                print(f"✅ Processat: {nou_nom}")

            # Marcar com a llegit
            gmail.users().messages().batchModify(userId='me', body={'ids': [msg_ref['id']], 'removeLabelIds': ['UNREAD']}).execute()

        except Exception as e:
            print(f"⚠️ Error al correu {msg_ref['id']}: {e}")

    enviar_resum(gmail, cvs_processats)
    print(f"🏁 Finalitzat. S'ha enviat el resum amb {len(cvs_processats)} CVs.")

if __name__ == '__main__':
    main()
