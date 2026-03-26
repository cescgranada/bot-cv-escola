import os
import json
import base64
import io
import re
import time
import fitz  # PyMuPDF
from datetime import datetime
from email.utils import parsedate_to_datetime
from email.mime.text import MIMEText
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# === 1. CONFIGURACIÓ DE SEGURETAT I IA ===
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro')

IDS_CARPETES = {
    "INFANTIL": "1U0kw8nUIXJaqFFaf9977A7I7o4yGcMDo",
    "PRIMARIA": "1duFjwCFNYAK63h9Sw36zxNfSEc5jsPIV",
    "ESO": "11XTfeSsk3oAMaQMlXgmao8bcB3Bmk2rG",
    "GENERAL": "1MjDr5z_JoxbdqEx7XE895VKZbBKTxCtZ"
}
DESTINATARIS_RESUM = ["francesc.granada@noupatufet.coop", "ingrid.ribelles@noupatufet.coop"]

# === 2. EL PROMPT DE MISSIÓ CRÍTICA ===
PROMPT_CV_PATUFET = """
Ets un expert en Recursos Humans i Gestió Escolar de l'Escola Nou Patufet. La teva missió és analitzar el text següent extret d'un CV i classificar-lo amb precisió absoluta.

CONTEXT DE L'ESCOLA:
Som una cooperativa d'ensenyament que cobreix des de l'etapa Infantil (I3) fins a 4t d'ESO.

TEXT DEL CV A ANALITZAR:
{text_cv}

CRITERIS DE CLASSIFICACIÓ (JERARQUIA DE DECISIÓ):
- INFANTIL: Mestres amb grau en Educació Infantil o Tècnics en Educació Infantil (TEI). Mencions en P3, P4, P5 o Llar d'infants.
- PRIMARIA: Mestres amb grau en Educació Primària. Mencions: Angles, Música, EF, o Educació Especial (SIEI/PT).
- ESO: Llicenciats o Graduats amb el Màster de Formació del Professorat (CAP). Especialitats: Ciències, Filologia, Matemàtiques, Tecnologia, Socials, etc.
- GENERAL: Perfils no docents (Administració, Cuina, Manteniment, Vetlladors) o perfils on no es pugui determinar clarament l'etapa.

REGLA DE ROBUSTESA D'ARXIVAMENT:
- Si el candidat té titulació per a dues etapes (ex: Infantil i Primària), la teva resposta ha d'incloure AMBDÓS IDs de carpeta.
- Si hi ha un dubte raonable sobre la titulació oficial per fer classe, classifica a GENERAL per a revisió manual.

FORMAT DE SORTIDA (JSON PUR):
{{
  "nom_candidat": "Nom complet detectat",
  "especialitat_principal": "Ex: Filologia Catalana / Mestre Primària",
  "carpetes_id": ["ID_CARPETA_1", "ID_CARPETA_2"],
  "justificacio_tecnica": "Breu explicació de la classificació",
  "punts_forts": ["Punt 1", "Punt 2"],
  "prioritat_contractacio": 1-5
}}

IDS PER UTILITZAR:
- Infantil: {id_infantil}
- Primaria: {id_primaria}
- ESO: {id_eso}
- General: {id_general}
"""

# === 3. UTILITATS TÈCNIQUES ===

def extreure_text_pdf(pdf_bytes):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text.strip()
    except Exception as e:
        print(f"⚠️ Error llegint PDF: {e}")
        return ""

def processar_cv_ia(text_cv):
    if len(text_cv) < 200:
        return {
            "nom_candidat": "Revisió Manual",
            "especialitat_principal": "REVISIÓ_OCR_NECESSARI",
            "carpetes_id": [IDS_CARPETES["GENERAL"]],
            "justificacio_tecnica": "Text massa curt o imatge."
        }

    prompt_final = PROMPT_CV_PATUFET.format(
        text_cv=text_cv,
        id_infantil=IDS_CARPETES["INFANTIL"],
        id_primaria=IDS_CARPETES["PRIMARIA"],
        id_eso=IDS_CARPETES["ESO"],
        id_general=IDS_CARPETES["GENERAL"]
    )
    
    try:
        response = model.generate_content(prompt_final)
        net = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(net)
    except Exception as e:
        print(f"❌ Error IA: {e}")
        return None

def extreure_pdfs_recursiu(parts):
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
        cos = f"Hola,\n\nS'han processat els següents CVs amb IA profunda:\n\n{fileres}\n\nJa al Drive."
    
    msg = MIMEText(cos, 'plain', 'utf-8')
    msg['Subject'] = f"Resum Setmanal CVs - {datetime.now().strftime('%d/%m/%Y')}"
    msg['To'] = ", ".join(DESTINATARIS_RESUM)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    gmail.users().messages().send(userId='me', body={'raw': raw}).execute()

# === 4. EXECUCIÓ ===

def main():
    print("🚀 Iniciant Super-Bot Nou Patufet...")
    creds_info = json.loads(os.environ['GOOGLE_CREDENTIALS'])
    creds = Credentials.from_authorized_user_info(creds_info)
    gmail = build('gmail', 'v1', credentials=creds)
    drive = build('drive', 'v3', credentials=creds)

    query = 'is:unread has:attachment filename:pdf'
    results = gmail.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])
    
    cvs_processats = []

    for msg_ref in messages:
        try:
            msg = gmail.users().messages().get(userId='me', id=msg_ref['id']).execute()
            headers = msg['payload'].get('headers', [])
            
            date_h = next((h['value'] for h in headers if h['name'] == 'Date'), "")
            try:
                dt = parsedate_to_datetime(date_h)
                data_iso = dt.strftime('%Y-%m-%d')
            except: 
                data_iso = datetime.now().strftime('%Y-%m-%d')

            parts = msg['payload'].get('parts', [msg['payload']])
            adjunts_pdf = extreure_pdfs_recursiu(parts)
            
            for part in adjunts_pdf:
                att_id = part['body'].get('attachmentId')
                attachment = gmail.users().messages().attachments().get(
                    userId='me', messageId=msg_ref['id'], id=att_id).execute()
                
                pdf_bytes = base64.urlsafe_b64decode(attachment['data'])
                text_cv = extreure_text_pdf(pdf_bytes)
                analisi = processar_cv_ia(text_cv)
                
                if analisi:
                    nom_fitxer = f"{data_iso} - {analisi['especialitat_principal']} - {analisi['nom_candidat']}.pdf"
                    carpetes = analisi.get('carpetes_id', [IDS_CARPETES["GENERAL"]])
                    for folder_id in carpetes:
                        media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype='application/pdf')
                        drive.files().create(body={'name': nom_fitxer, 'parents': [folder_id]}, media_body=media).execute()
                    
                    cvs_processats.append(f"{nom_fitxer}")
                    print(f"✅ OK: {nom_fitxer}")

            # Marcar com a llegit
            gmail.users().messages().batchModify(userId='me', body={'ids': [msg_ref['id']], 'removeLabelIds': ['UNREAD']}).execute()

        except Exception as e:
            print(f"⚠️ Error en bucle principal: {e}")

    enviar_resum(gmail, cvs_processats)

if __name__ == '__main__':
    main()
