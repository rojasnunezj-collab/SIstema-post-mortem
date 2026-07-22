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
    """Descarga la lista de categorías CCR3 desde la hoja 1 del sheet de referencia."""
    from config import CCR3_SHEET_ID
    creds = get_credentials()
    if not creds: return []
    try:
        client = gspread.authorize(creds)
        # La hoja 1 es típicamente la primera
        sheet = client.open_by_key(CCR3_SHEET_ID).worksheet("Hoja 1")
        # Asumiendo que la lista está en la primera columna
        valores = sheet.col_values(1)
        # Filtramos vacíos y encabezados si los hay
        lista = [v.strip() for v in valores if v.strip()]
        return lista if lista else ["No se encontraron categorías"]
    except Exception as e:
        st.error(f"Error leyendo CCR3 de Sheet: {e}")
        return []

@st.cache_data(ttl=3600, show_spinner=False)
def obtener_limites_pais():
    """Descarga el diccionario de límites por país desde la pestaña 'importes maximo pais'."""
    creds = get_credentials()
    if not creds: return {}
    try:
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet("importes maximo pais")
        # Obtiene todas las filas
        filas = sheet.get_all_values()
        limites = {}
        # Asume Col A = Pais, Col B = Limite numérico
        for fila in filas[1:]: # Saltar encabezado
            if len(fila) >= 2 and fila[0].strip():
                pais = fila[0].strip()
                try:
                    # Limpiar símbolo $ y convertir a float
                    val_str = fila[1].replace("$", "").replace(",", "").strip()
                    limites[pais] = float(val_str)
                except:
                    pass
        return limites
    except Exception as e:
        st.error(f"Error leyendo Límites de Sheet: {e}")
        return {}

def registrar_en_sheet(datos, resolucion):
    """
    Registra el postmortem aprobado en el Google Sheet corporativo.
    """
    creds = get_credentials()
    if not creds:
        return False
        
    try:
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        
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

def generar_documento_postmortem(datos, resolucion):
    """
    Clona la plantilla base de Docs y reemplaza las variables dinámicas.
    Retorna el enlace del documento generado.
    """
    creds = get_credentials()
    if not creds:
        return None
        
    try:
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)
        
        # 1. Copiar el documento plantilla
        title = f"Postmortem - Caso {datos.get('numero_caso', 'S/N')} - {datos.get('pais', '')}"
        body = {'name': title}
        
        # Copia el archivo
        copied_file = drive_service.files().copy(
            fileId=DOC_TEMPLATE_ID, 
            body=body
        ).execute()
        
        new_doc_id = copied_file.get('id')
        
        # 2. Preparar los reemplazos
        # Asegúrate de que tu documento plantilla de Docs contenga estas variables escritas exactamente así:
        # {{NUMERO_CASO}}, {{AGENTE}}, {{PAIS}}, etc.
        variables = {
            "{{CASO_NUMERO}}": datos.get("numero_caso", ""),
            "{{HORA}}": datos.get("hora", ""),
            "{{FIN_ACCION}}": datos.get("fin_accion", ""),
            "{{INICIO_PM}}": datos.get("inicio_pm", ""),
            "{{CASO}}": datos.get("caso", ""),
            "{{AGENTE}}": datos.get("agente_escala", ""),
            "{{PROBLEMA}}": datos.get("motivo_reclamo", ""),
            "{{CCR3}}": datos.get("ccr3", ""),
            "{{CORREO}}": datos.get("correo", ""),
            "{{LINK_PEDIDO}}": datos.get("pedido_link", ""),
            "{{ORDER_ID}}": datos.get("order_id", ""),
            "{{USER_ID}}": datos.get("user_id", ""),
            "{{NUMERO}}": datos.get("numeros", ""),
            "{{FRAUDE_OPERACIONAL}}": datos.get("fraude_operacional", ""),
            "{{FRAUDE_FINTECH}}": datos.get("fraude_fintech", ""),
            "{{PAIS}}": datos.get("pais", ""),
            "{{SEGUIDORES}}": datos.get("seguidores", ""),
            "{{CONTACTOS}}": datos.get("contactos", ""),
            "{{LIMITE}}": f"${datos.get('limite', 0)}",
            "{{PEDIDO}}": f"${datos.get('monto_pedido', 0)}",
            "{{DEVOLUCION}}": f"${datos.get('monto_devolucion', 0)}",
            "{{COMPENSACION}}": f"${datos.get('compensacion', 0)}",
            "{{TOTAL}}": f"${datos.get('total', 0)}, {datos.get('evaluacion_limite', '')}",
            "{{RESOLUCION}}": resolucion
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
        
        # Compartir para que quien tenga el link pueda leer o editar (Opcional, pero recomendado si el bot lo crea)
        drive_service.permissions().create(
             fileId=new_doc_id,
             body={'type': 'anyone', 'role': 'writer'}
        ).execute()
        
        link = f"https://docs.google.com/document/d/{new_doc_id}/edit"
        return link
        
    except Exception as e:
        st.error(f"Error al generar Google Doc: {e}")
        return None
