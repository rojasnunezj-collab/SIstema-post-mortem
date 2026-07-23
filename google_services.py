# google_services.py
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime

from config import SPREADSHEET_ID, DOC_TEMPLATE_ID

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents'
]

def get_credentials():
    """Obtiene las credenciales de la cuenta de servicio desde Streamlit Secrets."""
    # Intentamos obtener el secreto completo como diccionario
    try:
        service_account_info = st.secrets["gcp_service_account"]
        # En st.secrets, si usamos un archivo TOML, [gcp_service_account] se lee como un dict
        if isinstance(service_account_info, str):
            import json
            service_account_info = json.loads(service_account_info)
            
        creds = Credentials.from_service_account_info(
            service_account_info,
            scopes=SCOPES
        )
        return creds
    except Exception as e:
        st.error(f"Error al cargar credenciales de Google: {e}")
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def obtener_catalogo_ccr3():
    """Descarga la lista de categorías CCR3 desde la primera hoja del sheet de referencia."""
    from config import CCR3_SHEET_ID
    creds = get_credentials()
    if not creds: return []
    try:
        client = gspread.authorize(creds)
        doc = client.open_by_key(CCR3_SHEET_ID)
        try:
            sheet = doc.worksheet("Hoja 1")
        except gspread.WorksheetNotFound:
            # Si no existe "Hoja 1" (por ejemplo si está en inglés como "Sheet1"), usamos la primera pestaña.
            sheet = doc.get_worksheet(0)
            
        # Asumiendo que la lista está en la columna C (índice 3)
        valores = sheet.col_values(3)
        # Filtramos vacíos y encabezados si los hay (saltando la fila 1 si es encabezado)
        lista = [v.strip() for v in valores[1:] if v.strip()]
        return lista if lista else ["No se encontraron categorías en la columna C"]
    except Exception as e:
        st.error(f"Error leyendo CCR3 de Sheet (ID {CCR3_SHEET_ID}): {e}")
        return []

@st.cache_data(ttl=3600, show_spinner=False)
def obtener_limites_pais():
    """Descarga el diccionario de límites por país desde la pestaña 'importes maximo pais'."""
    creds = get_credentials()
    if not creds: return {}
    try:
        client = gspread.authorize(creds)
        doc = client.open_by_key(SPREADSHEET_ID)
        try:
            sheet = doc.worksheet("importes maximo pais")
        except gspread.WorksheetNotFound:
            # Búsqueda difusa para lidiar con espacios, mayúsculas o tildes
            nombres = [w.title for w in doc.worksheets()]
            hoja_encontrada = None
            for w in doc.worksheets():
                if "importe" in w.title.lower() or "limite" in w.title.lower() or "maximo" in w.title.lower():
                    hoja_encontrada = w
                    break
            if not hoja_encontrada:
                st.error(f"Pestaña de límites no encontrada. Las pestañas reales son: {nombres}")
                return {}
            sheet = hoja_encontrada

        # Obtiene todas las filas
        filas = sheet.get_all_values()
        limites = {}
        # Asume Col A = Pais (0), Col C = Limite numérico (2)
        for fila in filas[1:]: # Saltar encabezado
            if len(fila) >= 3 and fila[0].strip():
                pais = fila[0].strip()
                try:
                    # Limpiar símbolo $ y convertir a float
                    val_str = fila[2].replace("$", "").replace(",", "").strip()
                    if val_str:
                        limites[pais] = float(val_str)
                except:
                    pass
        return limites
    except Exception as e:
        st.error(f"Error leyendo Límites de Sheet: {e}")
        return {}

@st.cache_data(ttl=3600, show_spinner=False)
def obtener_reglas_influencer():
    """Descarga las reglas de seguidores mínimos para cada red social desde la pestaña 'reglas'."""
    from config import INFLUENCER_SHEET_ID
    creds = get_credentials()
    if not creds: return {}
    try:
        client = gspread.authorize(creds)
        doc = client.open_by_key(INFLUENCER_SHEET_ID)
        try:
            sheet = doc.worksheet("reglas")
        except gspread.WorksheetNotFound:
            # Fallback en caso de que esté mal escrita
            sheet = doc.get_worksheet(0)
            
        filas = sheet.get_all_values()
        reglas = {}
        # Asume Col A = Red Social, Col B = Mínimo de Seguidores (ej. 10000)
        for fila in filas[1:]: # Saltar encabezado
            if len(fila) >= 2 and fila[0].strip():
                red_social = fila[0].strip().lower()
                try:
                    # Limpiar comas o texto y convertir a entero
                    val_str = ''.join(filter(str.isdigit, fila[1]))
                    if val_str:
                        reglas[red_social] = int(val_str)
                except:
                    pass
        return reglas
    except Exception as e:
        st.error(f"Error leyendo reglas de Influencers (ID {INFLUENCER_SHEET_ID}): {e}")
        return {}

def registrar_en_sheet(datos, resolucion):
    """
    Registra el postmortem aprobado en la pestaña REGISTRO del Google Sheet corporativo.
    """
    creds = get_credentials()
    if not creds:
        return False
        
    try:
        client = gspread.authorize(creds)
        doc = client.open_by_key(SPREADSHEET_ID)
        try:
            sheet = doc.worksheet("REGISTRO")
        except gspread.WorksheetNotFound:
            # Fallback (búsqueda difusa)
            sheet = doc.worksheet(doc.worksheets()[0].title)
            for w in doc.worksheets():
                if "registro" in w.title.lower():
                    sheet = w
                    break
        
        # Preparamos la fila a insertar
        # Ajusta el orden según las columnas de tu hoja de cálculo
        fila = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            datos.get("numero_caso", ""),
            datos.get("hora", ""),
            datos.get("fin_accion", ""),
            datos.get("inicio_pm", ""),
            datos.get("caso", ""),
            datos.get("agente_escala", ""),
            datos.get("motivo_reclamo", ""),
            datos.get("ccr3", ""),
            datos.get("correo", ""),
            datos.get("pedido_link", ""),
            datos.get("order_id", ""),
            datos.get("user_id", ""),
            datos.get("numeros", ""),
            datos.get("fraude_operacional", ""),
            datos.get("fraude_fintech", ""),
            datos.get("pais", ""),
            datos.get("seguidores", ""),
            datos.get("contactos", ""),
            str(datos.get("limite", 0)),
            str(datos.get("monto_pedido", 0)),
            str(datos.get("monto_devolucion", 0)),
            str(datos.get("compensacion", 0)),
            f"${datos.get('total', 0)} - {datos.get('evaluacion_limite', '')}",
            resolucion
        ]
        
        sheet.append_row(fila)
        return True
    except Exception as e:
        st.error(f"Error al registrar en Sheet: {e}")
        return False

def obtener_cantidad_documentos():
    """
    Lee la cantidad de filas en la pestaña REGISTRO para calcular cuántos documentos se han hecho.
    """
    creds = get_credentials()
    if not creds:
        return 0
        
    try:
        client = gspread.authorize(creds)
        doc = client.open_by_key(SPREADSHEET_ID)
        try:
            sheet = doc.worksheet("REGISTRO")
        except gspread.WorksheetNotFound:
            for w in doc.worksheets():
                if "registro" in w.title.lower():
                    sheet = w
                    break
        
        # Restamos 1 para descartar la fila del encabezado
        filas = len(sheet.get_all_values())
        return max(0, filas - 1)
    except Exception:
        return 0

def get_oauth_credentials():
    """Obtiene las credenciales OAuth de usuario real desde Streamlit Secrets para evadir límites de cuota."""
    from google.oauth2.credentials import Credentials
    try:
        token_info = st.secrets["gcp_oauth_token"]
        if isinstance(token_info, str):
            import json
            token_info = json.loads(token_info)
            
        creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        return creds
    except Exception as e:
        st.error(f"Error al cargar credenciales OAuth (Token): {e}")
        return None

def generar_documento_postmortem(datos, rep_limpio, ana_limpio, res_limpia):
    """
    Clona la plantilla base de Docs y reemplaza las variables dinámicas.
    Retorna el enlace del documento generado.
    """
    creds = get_oauth_credentials()
    if not creds:
        return None
        
    try:
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)
        
        # 1. Copiar el documento plantilla a la carpeta destino
        numero_caso = datos.get("numero_caso", "S_N")
        title = f"Post mortem {numero_caso}"
        folder_id = "16IaiuHgqtGu09T0MIC1TL9Zq0e-nsfAY"
        
        body = {
            'name': title,
            'parents': [folder_id]
        }
        
        # Copia el archivo
        copied_file = drive_service.files().copy(
            fileId=DOC_TEMPLATE_ID, 
            body=body
        ).execute()
        
        new_doc_id = copied_file.get('id')
        
        # 2. Preparar los reemplazos
        variables = {
            "{{CCR3}}": datos.get("ccr3", ""),
            "{{PROBLEMA}}": datos.get("motivo_reclamo", ""),
            "{{CASO}}": datos.get("caso", ""),
            "{{DEVOLUCION}}": f"${datos.get('monto_devolucion', 0)}",
            "{{COMPENSACION_FINAL}}": f"${datos.get('compensacion', 0)}",
            "{{ORDER_ID}}": datos.get("order_id", ""),
            "{{USER_ID}}": datos.get("user_id", ""),
            "{{CORREO}}": datos.get("correo", ""),
            "{{LINK_PEDIDO}}": datos.get("pedido_link", ""),
            "{{AGENTE}}": datos.get("agente_escala", ""),
            "{{REPORTE}}": rep_limpio,
            "{{ANALISIS}}": ana_limpio,
            "{{SOLUCION}}": res_limpia
        }
        
        requests = []
        for key, value in variables.items():
            requests.append({
                'replaceAllText': {
                    'containsText': {
                        'text': key,
                        'matchCase': True
                    },
                    'replaceText': str(value)
                }
            })
            
        # 3. Ejecutar los reemplazos en el documento copiado
        docs_service.documents().batchUpdate(
            documentId=new_doc_id, 
            body={'requests': requests}
        ).execute()
        
        # Compartir para que quien tenga el link pueda leer o editar
        drive_service.permissions().create(
             fileId=new_doc_id,
             body={'type': 'anyone', 'role': 'writer'}
        ).execute()
        
        link = f"https://docs.google.com/document/d/{new_doc_id}/edit"
        return link
        
    except Exception as e:
        st.error(f"Error al generar Google Doc: {e}")
        return None
