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
    """Obtiene credenciales desde token de usuario (OAuth) o cuenta de servicio en Streamlit Secrets."""
    import json
    # 1. Intentamos usar el Token Personal OAuth del usuario (si está en los secretos)
    try:
        if "gcp_oauth_token" in st.secrets:
            token_info = st.secrets["gcp_oauth_token"]
            if isinstance(token_info, str):
                token_info = json.loads(token_info)
                
            from google.oauth2.credentials import Credentials as UserCredentials
            creds = UserCredentials.from_authorized_user_info(token_info, SCOPES)
            
            # Refrescar token si está expirado
            if creds and creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
            return creds
    except Exception as e:
        st.warning(f"No se pudo cargar el token personal: {e}")

    # 2. Si no hay token personal, usamos la cuenta de servicio (el Bot)
    try:
        service_account_info = st.secrets["gcp_service_account"]
        if isinstance(service_account_info, str):
            service_account_info = json.loads(service_account_info)
            
        from google.oauth2.service_account import Credentials
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
        
@st.cache_data(ttl=3600, show_spinner=False)
def obtener_criterios_evaluacion():
    """Descarga los criterios de evaluación de interacciones desde el Sheet especificado."""
    creds = get_credentials()
    if not creds: return [], []
    try:
        client = gspread.authorize(creds)
        # ID de la hoja proporcionada
        doc = client.open_by_key("1dIHOqJS7su3rnBRFKP4RgxZkib77Uj6K8ZOtGIhAJfc")
        
        import unicodedata
        comunicacion = []
        gestion = []
        
        for w in doc.worksheets():
            title_lower = w.title.strip().lower()
            title_norm = unicodedata.normalize('NFD', title_lower).encode('ascii', 'ignore').decode('utf-8')
            
            if "comunica" in title_norm:
                try:
                    comunicacion = w.get_all_values()
                except Exception:
                    pass
            elif "gestion" in title_norm:
                try:
                    gestion = w.get_all_values()
                except Exception:
                    pass
            
        return comunicacion, gestion
    except Exception as e:
        st.error(f"Error leyendo Criterios de Evaluación: {e}")
        return [], []

@st.cache_data(ttl=60, show_spinner=False)
def obtener_metricas_registro():
    """Obtiene la cantidad de documentos y acciones contando la columna de resolución."""
    try:
        from config import SPREADSHEET_ID
        creds = get_credentials()
        client = gspread.authorize(creds)
        doc = client.open_by_key(SPREADSHEET_ID)
        try:
            sheet = doc.worksheet("REGISTRO")
        except gspread.WorksheetNotFound:
            sheet = doc.sheet1
        
        # Columna Y (índice 25) es la resolución.
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
        import streamlit as st
        st.warning(f"Error en contador: {e}")
        return 0, 0

def registrar_en_sheet(datos, resolucion):
    """
    Registra el postmortem aprobado en el Google Sheet corporativo.
    """
    creds = get_credentials()
    if not creds:
        return False
        
    try:
        from config import SPREADSHEET_ID
        client = gspread.authorize(creds)
        doc = client.open_by_key(SPREADSHEET_ID)
        try:
            sheet = doc.worksheet("REGISTRO")
        except gspread.WorksheetNotFound:
            sheet = doc.sheet1
        # Preparamos la fila a insertar
        from datetime import datetime, timedelta, timezone
        tz = timezone(timedelta(hours=-5)) # America/Lima
        fila = [
            datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S"),
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
        
        col_a_values = sheet.col_values(1)
        next_row = len(col_a_values) + 1
        for idx, val in enumerate(col_a_values):
            if idx > 0 and not str(val).strip():
                next_row = idx + 1
                break
                
        rango = f"A{next_row}"
        try:
            sheet.update(range_name=rango, values=[fila])
        except TypeError:
            # Fallback para versiones antiguas de gspread
            sheet.update(rango, [fila])
            
        return True
    except Exception as e:
        import streamlit as st
        st.error(f"Error al registrar en Sheet: {e}")
        return False

def generar_documento_postmortem(datos, rep_limpio, ana_limpio, res_limpia, imagenes_docs=None, datos_contactos=None):
    """
    Clona la plantilla base de Docs, reemplaza variables de texto e inyecta imágenes.
    Retorna el enlace del documento generado.
    """
    if datos_contactos is None:
        datos_contactos = []
        
    creds = get_credentials()
    if not creds:
        return None
        
    try:
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)
        
        # 1. Copiar el documento plantilla a la carpeta destino
        order = str(datos.get('order_id', '')).strip()
        user_val = str(datos.get('user_id', '')).strip()
        
        # Determine the ID for the title
        is_order_invalid = not order or order.lower() in ['revisar', 'no tiene', '-']
        id_final = user_val if is_order_invalid else order
        if not id_final or id_final.lower() in ['revisar', '-']: 
            id_final = str(datos.get('caso', 'SinID')).strip()
        
        title = f"Post mortem {id_final}"
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
        
        # 2. Preparar los reemplazos base
        from datetime import datetime
        def format_monto(m):
            try:
                m_f = float(m)
                if m_f == 0:
                    return "0"
                if m_f.is_integer():
                    return str(int(m_f))
                return str(m_f)
            except:
                return str(m)

        monto_dev = format_monto(datos.get('monto_devolucion', 0))
        monto_comp = format_monto(datos.get('compensacion', 0))
        otras_str = datos.get("otras_gestiones", "")
        variables = {
            "{{FECHA}}": datetime.now().strftime("%d/%m/%Y"),
            "{{CCR3}}": datos.get("ccr3", ""),
            "{{PROBLEMA}}": datos.get("motivo_reclamo", ""),
            "{{CASO}}": datos.get("caso", ""),
            "{{DEVOLUCION}}": monto_dev,
            "{{VALOR_RECLAMO}}": monto_dev,
            "{{TEXTO_DEVOLUCION}}": datos.get("devolucion_str", ""),
            "{{COMPENSACION_FINAL}}": monto_comp,
            "{{TEXTO_COMPENSACION}}": datos.get("compensacion_str", ""),
            "{{OTRAS_GESTIONES}}": "@@OTRAS_GESTIONES_MARKER@@" if otras_str else "",
            "{{ORDER_ID}}": datos.get("order_id", ""),
            "{{USER_ID}}": datos.get("user_id", ""),
            "{{CORREO}}": datos.get("correo", ""),
            "{{LINK_PEDIDO}}": datos.get("pedido_link", ""),
            "{{AGENTE}}": datos.get("agente_escala", ""),
            "{{REPORTE}}": rep_limpio,
            "{{ANALISIS}}": ana_limpio,
            "{{SOLUCION}}": res_limpia,
            "{{CLIENTE_FRAUDE}}": datos.get("fraude_str", ""),
            "{{NUMERO}}": datos.get("telefono", ""),
            "{{CANTIDAD_CONTACTOS}}": str(datos.get("cantidad_contactos", "")),
            "{{CON_SIN}}": str(datos.get("con_sin", "")).upper(),
            "{{CONTACTO_GURU}}": datos.get("contacto_guru", "")
        }
        
        # 2.1 Preparar reemplazos para los bloques de contactos
        MAX_CONTACTS = 8
        for i in range(1, MAX_CONTACTS + 1):
            if i <= len(datos_contactos):
                # Este bloque se usa, preparamos las variables
                c_data = datos_contactos[i - 1]
                variables[f"{{{{NUMERO_CONTACTOS_{i}}}}}"] = str(i)
                variables[f"{{{{FECHA_CONTACTO_{i}}}}}"] = c_data.get("fecha", "")
                variables[f"{{{{AGENTES_INFO_{i}}}}}"] = c_data.get("agentes_info", "")
                variables[f"{{{{LINK_HERO_{i}}}}}"] = c_data.get("link", "")
                variables[f"{{{{OM1_{i}}}}}"] = c_data.get("om1", "")
                variables[f"{{{{OM2_{i}}}}}"] = c_data.get("om2", "")
                
                variables[f"{{{{OM3_1_1}}}}"] = c_data.get("om3", "") if i == 1 else ""
                variables[f"{{{{OM3_{i}}}}}"] = c_data.get("om3", "")
                variables[f"{{{{OM4_{i}}}}}"] = c_data.get("om4", "")
                
                variables[f"{{{{DESCRIPCION_CONTACTO_{i}}}}}"] = c_data.get("descripcion", "")
                
                # Eliminamos las etiquetas START y END para que queden limpias
                variables[f"<<START_{i}>>"] = ""
                variables[f"<<END_{i}>>"] = ""
            else:
                # Este bloque no se usa, no hacemos reemplazos de texto porque vamos a borrar el bloque completo.
                pass
                
        requests = []
        if not datos.get("compensacion_str", "").strip():
            variables["{{COMPENSACION_FINAL}}"] = ""
            variables["{{TEXTO_COMPENSACION}}"] = ""
            # Primero intentamos reemplazar la línea completa si coincide con el formato esperado original
            requests.append({
                'replaceAllText': {
                    'containsText': {'text': 'Compensación: {{COMPENSACION_FINAL}} {{TEXTO_COMPENSACION}}\n', 'matchCase': True},
                    'replaceText': ''
                }
            })
            requests.append({
                'replaceAllText': {
                    'containsText': {'text': 'Compensación: {{COMPENSACION_FINAL}} {{TEXTO_COMPENSACION}}', 'matchCase': True},
                    'replaceText': ''
                }
            })
            
        for key, value in variables.items():
            if value == "@@BOT_NO_APLICA@@":
                # Special cleanup for BOT so it removes the OM1 label
                om_label = key.replace("{{", "").replace("}}", "")
                base_om = om_label.split('_')[0]
                requests.append({
                    'replaceAllText': {
                        'containsText': {'text': f"{base_om}: {key}", 'matchCase': True},
                        'replaceText': value
                    }
                })
                requests.append({
                    'replaceAllText': {
                        'containsText': {'text': f"{base_om} : {key}", 'matchCase': True},
                        'replaceText': value
                    }
                })
                requests.append({
                    'replaceAllText': {
                        'containsText': {'text': f"{base_om} {key}", 'matchCase': True},
                        'replaceText': value
                    }
                })
                requests.append({
                    'replaceAllText': {
                        'containsText': {'text': key, 'matchCase': True},
                        'replaceText': value
                    }
                })
            elif key.startswith("{{OM") and not value.strip():
                # If an OM is blank, try to remove the label before it as well if it exists.
                om_label = key.replace("{{", "").replace("}}", "")
                base_om = om_label.split('_')[0] # e.g. OM1
                
                # Para eliminar la línea vacía en Google Docs, incluimos el salto de línea (\n)
                requests.append({
                    'replaceAllText': {
                        'containsText': {'text': f"{base_om}: {key}\n", 'matchCase': True},
                        'replaceText': ''
                    }
                })
                requests.append({
                    'replaceAllText': {
                        'containsText': {'text': f"{base_om}: {key}", 'matchCase': True},
                        'replaceText': ''
                    }
                })
                requests.append({
                    'replaceAllText': {
                        'containsText': {'text': f"{base_om} : {key}\n", 'matchCase': True},
                        'replaceText': ''
                    }
                })
                requests.append({
                    'replaceAllText': {
                        'containsText': {'text': f"{base_om} : {key}", 'matchCase': True},
                        'replaceText': ''
                    }
                })
                requests.append({
                    'replaceAllText': {
                        'containsText': {'text': f"{base_om} {key}\n", 'matchCase': True},
                        'replaceText': ''
                    }
                })
                requests.append({
                    'replaceAllText': {
                        'containsText': {'text': f"{base_om} {key}", 'matchCase': True},
                        'replaceText': ''
                    }
                })
                # Fallback to replace just the variable with empty
                requests.append({
                    'replaceAllText': {
                        'containsText': {'text': f"{key}\n", 'matchCase': True},
                        'replaceText': ''
                    }
                })
                requests.append({
                    'replaceAllText': {
                        'containsText': {'text': key, 'matchCase': True},
                        'replaceText': ''
                    }
                })
            else:
                requests.append({
                    'replaceAllText': {
                        'containsText': {
                            'text': key,
                            'matchCase': True
                        },
                        'replaceText': str(value)
                    }
                })
                
        # Fallback for Compensación si no hay compensación
        if not datos.get("compensacion_str", "").strip():
            requests.append({
                'replaceAllText': {
                    'containsText': {'text': 'Compensación: \n', 'matchCase': True},
                    'replaceText': ''
                }
            })
            requests.append({
                'replaceAllText': {
                    'containsText': {'text': 'Compensación: ', 'matchCase': True},
                    'replaceText': ''
                }
            })
            requests.append({
                'replaceAllText': {
                    'containsText': {'text': 'Compensación:\n', 'matchCase': True},
                    'replaceText': ''
                }
            })
            
        # Preparar tags de imágenes
        # Hack para Google Docs: Si un tag de imagen como {{EXTRA_1}} se dividió en múltiples textRuns por formato, 
        # find() manual fallará. Para evitarlo, usamos la API nativa de replaceAllText para normalizar los tags a @@EXTRA_1@@.
        image_search_tags = {}
        if imagenes_docs:
            for var_key, img_file in imagenes_docs.items():
                if not img_file:
                    # Si no hay imagen, simplemente borramos el tag original
                    requests.append({
                        'replaceAllText': {
                            'containsText': {'text': var_key, 'matchCase': True},
                            'replaceText': ''
                        }
                    })
                else:
                    # Si HAY imagen, normalizamos el tag en el documento para buscarlo luego sin cortes
                    clean_tag = var_key.replace("{", "@").replace("}", "@")
                    image_search_tags[var_key] = clean_tag
                    requests.append({
                        'replaceAllText': {
                            'containsText': {'text': var_key, 'matchCase': True},
                            'replaceText': clean_tag
                        }
                    })
                    
        # 3. Ejecutar los reemplazos de TEXTO en el documento copiado
        if requests:
            docs_service.documents().batchUpdate(
                documentId=new_doc_id, 
                body={'requests': requests}
            ).execute()
            
        try:
            # 3.5 Borrar los bloques sobrantes (del 2 al 7 si no se usan)
            doc_content = docs_service.documents().get(documentId=new_doc_id).execute()
            
            # Mapeamos el texto completo para encontrar los índices exactos
            full_text = ""
            index_map = []
            
            def extract_text_and_indices(content):
                nonlocal full_text, index_map
                for element in content:
                    if 'paragraph' in element:
                        for p_elem in element['paragraph'].get('elements', []):
                            if 'textRun' in p_elem:
                                text = p_elem['textRun'].get('content', '')
                                start_idx = p_elem['startIndex']
                                for char in text:
                                    index_map.append(start_idx)
                                    full_text += char
                                    start_idx += 1
                    elif 'table' in element:
                        for row in element['table'].get('tableRows', []):
                            for cell in row.get('tableCells', []):
                                extract_text_and_indices(cell.get('content', []))
                                
            extract_text_and_indices(doc_content.get('body', {}).get('content', []))
            
            delete_requests = []
            # Empezamos desde el bloque que no se va a usar (puede ser desde el 1)
            start_idx_delete = max(1, len(datos_contactos) + 1)
            if len(datos_contactos) == 0:
                start_idx_delete = 1
                
            import re
            for i in range(start_idx_delete, MAX_CONTACTS + 1):
                start_pattern = r'<<\s*START_' + str(i) + r'\s*>>'
                end_pattern = r'<<\s*END_' + str(i) + r'\s*>>'
                
                start_match = re.search(start_pattern, full_text)
                end_match = re.search(end_pattern, full_text)
                
                if start_match and end_match:
                    # endIndex debe abarcar el final del tag <<END_X>>
                    start_idx_str = start_match.start()
                    end_idx_str_final = end_match.end()
                    
                    real_start = index_map[start_idx_str]
                    # tomamos el índice correspondiente al final
                    real_end = index_map[end_idx_str_final - 1] + 1
                    
                    delete_requests.append({
                        'deleteContentRange': {
                            'range': {
                                'startIndex': real_start,
                                'endIndex': real_end
                            }
                        }
                    })
            
            # Ejecutamos las eliminaciones en orden reverso para no afectar los índices
            if delete_requests:
                delete_requests.reverse()
                docs_service.documents().batchUpdate(
                    documentId=new_doc_id, 
                    body={'requests': delete_requests}
                ).execute()
        except Exception as e:
            st.warning(f"Error al borrar bloques sobrantes de contactos: {e}. El documento se generó, pero puede contener texto extra.")
            
        # Procesar Formatos Especiales (Bot y Otras Gestiones)
        try:
            doc_content = docs_service.documents().get(documentId=new_doc_id).execute()
            
            def find_marker(content, m):
                for element in content:
                    if 'paragraph' in element:
                        for p_elem in element['paragraph'].get('elements', []):
                            if 'textRun' in p_elem:
                                texto_p = p_elem['textRun'].get('content', '')
                                idx = texto_p.find(m)
                                if idx != -1:
                                    start = p_elem['startIndex'] + idx
                                    end = start + len(m)
                                    return start, end
                    elif 'table' in element:
                        for row in element['table'].get('tableRows', []):
                            for cell in row.get('tableCells', []):
                                res = find_marker(cell.get('content', []), m)
                                if res:
                                    return res
                return None
                
            # Format Bot OMs
            marker_bot = "@@BOT_NO_APLICA@@"
            while True:
                res = find_marker(doc_content.get('body', {}).get('content', []), marker_bot)
                if not res:
                    break
                start, end = res
                reqs = [
                    {
                        'deleteContentRange': {
                            'range': {'startIndex': start, 'endIndex': end}
                        }
                    },
                    {
                        'insertText': {
                            'location': {'index': start},
                            'text': 'No aplica'
                        }
                    },
                    {
                        'updateTextStyle': {
                            'range': {'startIndex': start, 'endIndex': start + len('No aplica')},
                            'textStyle': {
                                'bold': True,
                                'foregroundColor': {
                                    'color': {'rgbColor': {'red': 1.0, 'green': 0.0, 'blue': 0.0}}
                                }
                            },
                            'fields': 'bold,foregroundColor'
                        }
                    }
                ]
                docs_service.documents().batchUpdate(documentId=new_doc_id, body={'requests': reqs}).execute()
                doc_content = docs_service.documents().get(documentId=new_doc_id).execute()
                
            # Format Otras Gestiones
            marker_otras = "@@OTRAS_GESTIONES_MARKER@@"
            while True:
                res = find_marker(doc_content.get('body', {}).get('content', []), marker_otras)
                if not res:
                    break
                start, end = res
                reqs = [
                    {
                        'deleteContentRange': {
                            'range': {'startIndex': start, 'endIndex': end}
                        }
                    },
                    {
                        'insertText': {
                            'location': {'index': start},
                            'text': otras_str
                        }
                    }
                ]
                
                if otras_str.startswith("Otras gestiones:"):
                    reqs.append({
                        'updateTextStyle': {
                            'range': {'startIndex': start, 'endIndex': start + len("Otras gestiones:")},
                            'textStyle': {'bold': True},
                            'fields': 'bold'
                        }
                    })
                    
                docs_service.documents().batchUpdate(documentId=new_doc_id, body={'requests': reqs}).execute()
                doc_content = docs_service.documents().get(documentId=new_doc_id).execute()
                
        except Exception as e:
            import logging
            logging.error(f"Error formating especiales: {e}")
            
        # 4. Procesar IMÁGENES
        if imagenes_docs:
            import io
            from googleapiclient.http import MediaIoBaseUpload
            
            # Recargar el documento porque los índices cambiaron tras la eliminación
            doc_content = docs_service.documents().get(documentId=new_doc_id).execute()
            
            for var_key, img_file in imagenes_docs.items():
                if img_file:
                    try:
                        # 4.1 Subir a Drive
                        file_metadata = {
                            'name': f"Postmortem_IMG_{var_key}_{id_final}",
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
                        
                        # 4.2 Localizar la variable en Docs usando una búsqueda fresca por cada imagen
                        start, end = None, None
                        
                        search_target = image_search_tags.get(var_key, var_key)
                        def find_image_placeholder(content):
                            nonlocal start, end
                            for element in content:
                                if 'paragraph' in element:
                                    for p_elem in element['paragraph'].get('elements', []):
                                        if 'textRun' in p_elem:
                                            texto_p = p_elem['textRun'].get('content', '')
                                            idx = texto_p.find(search_target)
                                            if idx != -1:
                                                start = p_elem['startIndex'] + idx
                                                end = start + len(search_target)
                                                return True
                                elif 'table' in element:
                                    for row in element['table'].get('tableRows', []):
                                        for cell in row.get('tableCells', []):
                                            if find_image_placeholder(cell.get('content', [])):
                                                return True
                            return False
                            
                        find_image_placeholder(doc_content.get('body', {}).get('content', []))
                                
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
                            
                            # Recargamos el documento otra vez porque la imagen inyectada desplaza los índices para la siguiente
                            doc_content = docs_service.documents().get(documentId=new_doc_id).execute()
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
