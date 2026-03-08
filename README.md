# 🤖 Bot de Gestió de CVs - Nou Patufet

Aquest projecte automatitza la recepció, classificació i arxivament dels currículums que arriben al correu de l'escola (`treballaambnosaltres@noupatufet.coop`).

## 📋 Descripció de la Missió
El bot s'executa automàticament **cada dilluns a les 08:00 AM**. La seva funció és:
1. **Auditar la bústia d'entrada**: Cerca correus no llegits amb fitxers adjunts en format PDF.
2. **Classificar per Etapa**: Analitza l'assumpte i el cos del missatge per moure el fitxer a la carpeta de Google Drive corresponent (Infantil, Primària, ESO o General).
3. **Intel·ligència de Nomenclatura**: Rebateja el fitxer automàticament amb el format: `AAAA-MM-DD - Especialitat - Nom del Candidat.pdf`.
4. **Notificació de Resum**: Envia un correu electrònic de resum amb tots els CVs processats a Direcció i Secretaria.

## 📂 Estructura del Drive
El bot escriu directament a les següents carpetes gestionades des del compte de l'escola:
* **Infantil**: `1U0kw8nUIXJaqFFaf...`
* **Primària**: `1duFjwCFNYAK63h...`
* **ESO**: `11XTfeSsk3oAMaQM...`
* **General**: `1MjDr5z_JoxbdqEx...`

## 🛠️ Stack Tècnic
* **Llenguatge**: Python 3.10
* **Infraestructura**: GitHub Actions (Workflows)
* **APIs**: Google Gmail API & Google Drive API
* **Autenticació**: OAuth2 amb Service Account/Credentials des de GitHub Secrets.

## 🚀 Manteniment
### Com afegir noves especialitats?
Si vols que el bot detecti noves matèries, edita la funció `extreure_especialitat` al fitxer `main.py` i afegeix paraules clau al diccionari.

### Com executar-lo manualment?
1. Ves a la pestanya **Actions** d'aquest repositori.
2. Selecciona "Bot de CVs Nou Patufet - Execució Setmanal".
3. Clica a **Run workflow**.

## 🔐 Seguretat
Les credencials d'accés no estan al codi. Es gestionen mitjançant el secret de GitHub: `GOOGLE_CREDENTIALS`.

---
*Configurat per a l'Escola Nou Patufet - 2026*