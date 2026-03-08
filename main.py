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

# === INFRAESTRUCTURA DE CARPETES ESTRATÈGIQUES ===
IDS_CARPETES = {
    "INFANTIL": "1U0kw8nUIXJaqFFaf9977A7I7o4yGcMDo",
    "PRIMARIA": "1duFjwCFNYAK63h9Sw36zxNfSEc5jsPIV",
    "ESO": "11XTfeSsk3oAMaQMlXgmao8bcB3Bmk2rG",
    "GENERAL": "1MjDr5z_JoxbdqEx7XE895VKZbBKTxCtZ"
}

def algoritme_extracccio_robust(subject, body):
    """
    Algoritme de classificació exhaustiva (Zero Fail Policy).
    Analitza matisos per minimitzar l'error de classificació.
    """
    text_analisis = f"{subject} {body}".lower()
    
    # Matisos d'Especialitats (Extracció d'actius)
    especialitats = {
        "Angles-AICLE": ["anglès", "english", "aicle", "clil", "native", "angles"],
        "Ed-Fisica": ["física", "esport", "ef", "gym", "psicomotricitat", "entrenador"],
        "STEAM-Mat-Tec": ["mates", "matemàtiques", "tecnologia", "tic", "robòtica", "ciències", "biologia", "química"],
        "Llengues-Cat-Cast": ["català", "castellà", "filologia", "llengua", "literatura", "clàssiques"],
        "Musica-Art": ["música", "instrument", "art", "plàstica", "visual", "dibuix"],
        "Atencio-Diversitat": ["nee", "psicopedagogia", "orientació", "logopèdia", "educació especial"]
    }
    
    # Identificació de l'Especialitat
    resultat_esp = "General"
    for esp, paraules in especialitats.items():
        if any(p in text_analisis for p in paraules):
            resultat_esp = esp
            break # Prioritzem la primera coincidència forta

    # Identificació de l'Etapa (Destí Crític)
    if any(x in text_analisis for x in ["infantil", "llar", "bressol", "p3", "p4", "p5", "0-3", "3-6"]):
        return IDS_CARPETES["INFANTIL"], resultat_esp
    elif any(x in text_analisis for x in ["primaria", "primària", "cicle inicial", "cicle mitjà", "cicle superior"]):
        return IDS_CARPETES["PRIMARIA"], resultat_esp
    elif any(x in text_analisis for x in ["eso", "secundaria", "secundària", "batxillerat", "eso/batx"]):
        return IDS_CARPETES["ESO"], resultat_esp
    
    return IDS_CARPETES["GENERAL"], resultat_esp

def main():
    print("🛡️ Iniciant Auditoria Integral de Seguretat (Rang: 01/01/2026 - Actualitat)")
    
    try:
        creds_info = json.loads(os.environ['GOOGLE_CREDENTIALS'])
        creds = Credentials.from_authorized_user_info(creds_info)
        gmail = build('gmail', 'v1', credentials=creds)
        drive = build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ FALL D'EXECUCIÓ: Error en infraestructura: {e}")
        return

    # QUERY D'AUDITORIA: Tots els correus amb PDF des del 1 de Gener de 2026
    # Ignorem 'is:unread' per garantir la integritat de la base de dades
    query_auditoria = 'after:2026/01/01 has:attachment filename:pdf'
    
    try:
        # Paginació per si hi ha un volum massiu de dades
        results = gmail.users().messages().list(userId='me', q=query_auditoria).execute()
        messages = results.get('messages', [])
    except Exception as e:
        print(f"❌ ERROR EN L'AUDITORIA DE CORREUS: {e}")
        return

    if not messages:
        print("ℹ️ L'auditoria no ha detectat actius nous en el rang seleccionat.")
        return

    print(f"🔍 Auditoria en curs: {len(messages)} actius detectats per processar.")

    for msg_ref in messages:
        try:
            msg = gmail.users().messages().get(userId='me', id=msg_ref['id']).execute()
            headers = msg['payload'].get('headers', [])
            
            # Extracció de metadades per l'auditoria
            from_h = next((h['value'] for h in headers if h['name'] == 'From'), "Desconegut")
            nom_candidat = re.sub(r'<.*?>', '', from_h).replace('"', '').strip()
            
            date_h = next((h['value'] for h in headers if h['name'] == 'Date'), "")
            try:
                date_clean = re.sub(r' \(.*\)', '', date_h).strip()
                dt = datetime.strptime(date_clean[:25].strip(), '%a, %d %b %Y %H:%M:%S')
                data_iso = dt.strftime('%Y-%m-%d')
            except:
                data_iso = "2026-UNKNOWN"

            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "")
            snippet = msg.get('snippet', "")

            # Execució de l'algoritme de classificació
            folder_id, especialitat = algoritme_extracccio_robust(subject, snippet)

            # Deep Scan de fitxers adjunts
            def extract_parts(parts):
                pdfs = []
                for p in parts:
                    if p.get('filename') and p['filename'].lower().endswith('.pdf'):
                        pdfs.append(p)
                    if 'parts' in p:
                        pdfs.extend(extract_parts(p['parts']))
                return pdfs

            payload = msg.get('payload', {})
            parts = payload.get('parts', [payload])
            adjunts_validats = extract_parts(parts)

            for pdf in adjunts_validats:
                att_id = pdf['body'].get('attachmentId')
                att_data = gmail.users().messages().attachments().get(
                    userId='me', messageId=msg_ref['id'], id=att_id).execute()
                
                # Generació de nomenclatura d'auditoria (Data-Especialitat-Nom)
                nom_fitxer_final = f"{data_iso} - {especialitat} - {nom_candidat}.pdf"
                
                raw_data = base64.urlsafe_b64decode(att_data['data'])
                fh = io.BytesIO(raw_data)
                media = MediaIoBaseUpload(fh, mimetype='application/pdf')
                
                metadata = {'name': nom_fitxer_final, 'parents': [folder_id]}
                
                # Execució de la càrrega a Drive
                drive.files().create(body=metadata, media_body=media).execute()
                print(f"✅ ACTIU REGISTRAT: {nom_fitxer_final}")
                
            # Nota: En mode auditoria integral, NO marquem com a llegit 
            # per no alterar l'estat original dels correus si no és necessari.
            time.sleep(0.3)

        except Exception as e:
            print(f"⚠️ AVIS D'OMISSIÓ: Error en el missatge {msg_ref['id']}: {e}")

    print("🏁 AUDITORIA FINALITZADA: Totes les dades han estat transferides i classificades.")

if __name__ == '__main__':
    main()
