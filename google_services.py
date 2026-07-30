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
def obtener_reglas_influencer_v2():
    """Descarga las reglas de seguidores mínimos para cada red social desde la pestaña 'reglas'.
       Formato esperado de la hoja: Col A=Mercado, Col B=FB, Col C=Instagram, Col D=TW.
    """
    from config import INFLUENCER_SHEET_ID
    creds = get_credentials()
    if not creds: return {}
    try:
        client = gspread.authorize(creds)
        doc = client.open_by_key(INFLUENCER_SHEET_ID)
        
        # Búsqueda case-insensitive de la pestaña "Reglas"
        hoja = None
        for w in doc.worksheets():
            if w.title.strip().lower() == "reglas":
                hoja = w
                break
        sheet = hoja or doc.get_worksheet(0)
            
        filas = sheet.get_all_values()
        reglas = {}
        
        # 1. Encontrar la cabecera dinámicamente
        mercado_idx, fb_idx, ig_idx, tw_idx = -1, -1, -1, -1
        start_row = 1
        
        for i, fila in enumerate(filas):
            fila_lower = [str(c).strip().lower() for c in fila]
            if "mercado" in fila_lower:
                mercado_idx = fila_lower.index("mercado")
                if "fb" in fila_lower: fb_idx = fila_lower.index("fb")
                if "instagram" in fila_lower: ig_idx = fila_lower.index("instagram")
                if "tw" in fila_lower: tw_idx = fila_lower.index("tw")
                start_row = i + 1
                break
                
        if mercado_idx == -1:
            # Fallback rígido asumiendo formato A, B, C, D
            mercado_idx, fb_idx, ig_idx, tw_idx = 0, 1, 2, 3
        
        # Helper para limpiar sufijos como 'k' o 'K' y comas
        def parse_k(val_str):
            val_str = val_str.lower().replace(",", ".").strip()
            if not val_str: return None
            multiplier = 1
            if "k" in val_str:
                multiplier = 1000
                val_str = val_str.replace("k", "")
            try:
                cleaned = ''.join(c for c in val_str if c.isdigit() or c == '.')
                if cleaned:
                    return int(float(cleaned) * multiplier)
                return None
            except:
                return None

        # Parseando formato de tabla 2D
        for fila in filas[start_row:]:
            if len(fila) > max(mercado_idx, fb_idx, ig_idx, tw_idx) and str(fila[mercado_idx]).strip():
                pais = str(fila[mercado_idx]).strip().lower()
                reglas[pais] = {}
                
                fb_limit = parse_k(str(fila[fb_idx])) if fb_idx != -1 else None
                ig_limit = parse_k(str(fila[ig_idx])) if ig_idx != -1 else None
                tw_limit = parse_k(str(fila[tw_idx])) if tw_idx != -1 else None
                
                if fb_limit: reglas[pais]["fb"] = fb_limit
                if ig_limit: reglas[pais]["instagram"] = ig_limit
                if tw_limit: reglas[pais]["tw"] = tw_limit
                
        return reglas
    except Exception as e:
        st.error(f"Error leyendo reglas de Influencers (ID {INFLUENCER_SHEET_ID}): {e}")
        return {}
        
@st.cache_data(ttl=60, show_spinner=False)
def obtener_metricas_registro():
    """Obtiene la cantidad de documentos y acciones contando la columna de resolución."""
    try:
        from config import SPREADSHEET_ID
        creds = get_credentials()
        client = gspread.authorize(creds)
        doc = client.open_by_key(SPREADSHEET_ID)
        sheet = doc.worksheet("REGISTRO")
        
        # Columna Y (índice 25) es la resolución. O podemos traer todas y contar.
        # get_all_values() es seguro si no es gigante.
        filas = sheet.get_all_values()
        
        docs_count = 0
        acciones_count = 0
        
        # Saltar encabezado
        for fila in filas[1:]:
            # Validar que la fila no esté completamente vacía
            if not "".join(fila).strip():
                continue
                
            # La columna 25 (índice 24) tiene la resolución ("SOLO ACCIONAR" u otro texto)
            resolucion = fila[24] if len(fila) > 24 else ""
            if "SOLO ACCIONAR" in str(resolucion).upper():
                acciones_count += 1
            else:
                # Si tiene número de caso u hora en col 1/2, es un doc legítimo
                docs_count += 1
                
        return docs_count, acciones_count
    except Exception as e:
        return 0, 0

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
        # Obtener fecha en hora local de Lima usando built-in timezone
        from datetime import timezone, timedelta
        lima_tz = timezone(timedelta(hours=-5))
        fecha_lima = datetime.now(lima_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        fila = [
            fecha_lima,
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
            datos.get("telefono", ""),  # Antes "numeros"
            datos.get("fraude_str", ""), # Antes "fraude_operacional"
            "",                          # Antes "fraude_fintech", ahora combinado en str
            datos.get("pais", ""),
            datos.get("seguidores", ""),
            datos.get("contactos", ""),
            str(datos.get("limite", 0)),
            str(datos.get("monto_pedido", 0)),
            str(datos.get("monto_devolucion", 0)),
            str(datos.get("compensacion", 0)),
            f"${datos.get('total', 0)} - {datos.get('evaluacion_limite', '')}",
            resolucion,
            datos.get("user_email", "")
        ]
        
        # table_range="A1" obliga a buscar el final de la tabla real de datos e ignora el formato de celdas vacías.
        # value_input_option='USER_ENTERED' permite que los números sean tratados como números reales en el sheet.
        sheet.append_row(fila, table_range="A1", value_input_option='USER_ENTERED')
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

def generar_documento_postmortem(datos, rep_limpio, ana_limpio, res_limpia, imagenes_docs=None):
    """
    Clona la plantilla base de Docs, reemplaza variables de texto e inyecta imágenes.
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
        from datetime import datetime
        variables = {
            "{{FECHA}}": datetime.now().strftime("%d/%m/%Y"),
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
            "{{SOLUCION}}": res_limpia,
            "{{CLIENTE_FRAUDE}}": datos.get("fraude_str", ""),
            "{{NUMERO}}": datos.get("telefono", "")
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
            
        # Si no se subió imagen, borramos la variable de la plantilla
        if imagenes_docs:
            for var_key, img_file in imagenes_docs.items():
                if not img_file:
                    requests.append({
                        'replaceAllText': {
                            'containsText': {'text': var_key, 'matchCase': True},
                            'replaceText': ''
                        }
                    })
                    
        # 3. Ejecutar los reemplazos de TEXTO en el documento copiado
        if requests:
            docs_service.documents().batchUpdate(
                documentId=new_doc_id, 
                body={'requests': requests}
            ).execute()
            
        # 4. Procesar IMÁGENES
        if imagenes_docs:
            import io
            from googleapiclient.http import MediaIoBaseUpload
            
            for var_key, img_file in imagenes_docs.items():
                if img_file:
                    try:
                        # 4.1 Subir a Drive
                        file_metadata = {
                            'name': f"Postmortem_IMG_{var_key}_{numero_caso}",
                            'parents': ["1n0J019rRNm3vg5xABuia-7Qje__qBG8i"]
                        }
                        file_stream = io.BytesIO(img_file.getvalue())
                        media = MediaIoBaseUpload(file_stream, mimetype=img_file.type, resumable=True)
                        drive_img = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                        img_id = drive_img.get('id')
                        
                        # Dar permisos de lectura
                        drive_service.permissions().create(
                            fileId=img_id,
                            body={'type': 'anyone', 'role': 'reader'}
                        ).execute()
                        
                        img_url = f"https://drive.google.com/uc?id={img_id}"
                        
                        # 4.2 Localizar la variable en Docs
                        doc_content = docs_service.documents().get(documentId=new_doc_id).execute()
                        start, end = None, None
                        for element in doc_content.get('body', {}).get('content', []):
                            if 'paragraph' in element:
                                for p_elem in element['paragraph'].get('elements', []):
                                    if 'textRun' in p_elem:
                                        texto_p = p_elem['textRun'].get('content', '')
                                        idx = texto_p.find(var_key)
                                        if idx != -1:
                                            start = p_elem['startIndex'] + idx
                                            end = start + len(var_key)
                                            break
                                if start: break
                                
                        # 4.3 Inyectar
                        if start and end:
                            img_requests = [
                                {
                                    'deleteContentRange': {
                                        'range': {'startIndex': start, 'endIndex': end}
                                    }
                                },
                                {
                                    'insertInlineImage': {
                                        'uri': img_url,
                                        'location': {'index': start},
                                        'objectSize': {
                                            'width': {'magnitude': 450, 'unit': 'PT'}
                                        }
                                    }
                                }
                            ]
                            docs_service.documents().batchUpdate(documentId=new_doc_id, body={'requests': img_requests}).execute()
                    except Exception as e:
                        st.warning(f"No se pudo insertar la imagen para {var_key}: {e}")
        
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
