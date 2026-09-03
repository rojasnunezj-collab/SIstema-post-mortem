# gemini_api.py
import os
import io
import json
import re
import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from PIL import Image

PROJECT_ID = "postmortem-503102"

def _init_vertex():
    """Inicializa Vertex AI usando las credenciales de st.secrets o Application Default Credentials."""
    if st.session_state.get("vertex_initialized"):
        return True
    try:
        from google.oauth2 import service_account
        if "gcp_service_account" in st.secrets:
            secret_val = st.secrets["gcp_service_account"]
            if isinstance(secret_val, str):
                cred_dict = json.loads(secret_val)
            else:
                cred_dict = dict(secret_val)
            if "private_key" in cred_dict:
                cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            credentials = service_account.Credentials.from_service_account_info(cred_dict)
            vertexai.init(project=PROJECT_ID, location="us-central1", credentials=credentials)
        else:
            vertexai.init(project=PROJECT_ID, location="us-central1")
        st.session_state["vertex_initialized"] = True
        return True
    except Exception as e:
        st.error(f"❌ Error inicializando Vertex AI: {e}")
        return False

def obtener_modelo_valido():
    if "modelo_gemini_cache" in st.session_state:
        return st.session_state["modelo_gemini_cache"]

    if not _init_vertex():
        return None

    msg = st.empty()
    msg.info("⏳ Buscando IA disponible...")

    # Modelos Vertex AI actuales (sin prefijo models/, sin versión numérica)
    priority_list = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-002",
        "gemini-2.5-flash-001",
        "gemini-2.5-pro",
        "gemini-1.5-flash-002",
        "gemini-1.5-flash-001",
        "gemini-1.5-pro-002",
    ]

    errores = []
    for model_name in priority_list:
        try:
            m = GenerativeModel(model_name)
            m.generate_content("test")
            st.session_state["modelo_gemini_cache"] = model_name
            msg.empty()
            return model_name
        except Exception as e:
            errores.append(f"{model_name}: {e}")
            continue

    msg.empty()
    st.error("❌ Ningún modelo de Vertex AI respondió. Errores:")
    for err in errores:
        st.write(err)
    return None

from google_services import obtener_catalogo_ccr3

def extraer_datos_gemini(imagenes_pil):
    if not _init_vertex():
        return None

    modelo_seguro = obtener_modelo_valido()
    if not modelo_seguro:
        st.error("❌ No se pudo encontrar un modelo de Vertex AI.")
        return None

    ccr3_opciones = obtener_catalogo_ccr3()
    ccr3_texto = "\n    - ".join(ccr3_opciones)

    prompt = f"""
    Eres un asistente experto en lectura de capturas de pantalla de operaciones de atención al cliente (postmortem).
    Se te proporcionarán varias imágenes que corresponden a un mismo caso continuo. Debes analizarlas todas en conjunto.
    
    REGLAS ESTRICTAS DE EXTRACCIÓN:
    1. HORA: Extrae la hora exacta de inicio del caso (al lado de la palabra "WORKFLOW", ej. "7:21 PM").
    2. ÚLTIMA INTERACCIÓN: Extrae la HORA EXACTA (formato HH:MM PM) del último mensaje de resolución visible en TODAS las imágenes. ¡DEBE SER UNA HORA ABSOLUTA! Si el último mensaje dice "hace 27 minutos", deduce matemáticamente la hora sumando minutos a la hora de inicio (ej. si inició a las 7:21 PM y tardó ~27 mins, pon "7:48 PM") o basándote en la hora del mensaje anterior. NUNCA devuelvas frases relativas como "hace 27 minutos".
    3. AGENTE: Extrae solo el nombre y apellido del agente que está arrobado (ejemplo, si dice @SM_Milena Arias_NDO, extrae "Milena Arias").
    4. CASO: Extrae el texto que está después de la frase "reclamo de un:".
    5. NÚMERO DE CASO: Extrae el número después de "DETALLE DEL CASO #" (si no hay, pon "-").
    6. SEGUIDORES: Si en las imágenes NO aparece explícitamente la palabra "influencer", estás OBLIGADO a poner exactamente la frase "no corresponde" (en minúsculas, sin comillas). NUNCA inventes números ni pongas "Revisar". Solo si dice explícitamente "influencer", extrae la cantidad.
    7. RED SOCIAL: Si es influencer, identifica la red social (Instagram, TikTok, YouTube, Twitter, Facebook, etc.). Si no es, pon "no corresponde".
    8. PAÍS: Extrae el texto al lado de "País:".
    9. CORREO: Extrae el texto al lado de "Correo:".
    10. LINK PEDIDO: Copia el link completo (si no hay pon "revisar").
    11. ORDER ID: Extrae el código que está en el link del pedido, justo después del último "/".
    12. MOTIVO DE RECLAMO: ¡MUY IMPORTANTE! NO copies el texto tal cual. Analiza el problema y redáctalo de forma resumida y profesional (máximo 3 líneas).
    13. CCR3: Basado en tu resumen, DEBES elegir una categoría de esta lista exacta. REGLA CLAVE: Si se menciona "producto dañado" o "en mal estado", la opción debe ser referente a la "calidad de la comida". Si no estás seguro de una sola, puedes devolver un máximo de 3 opciones separadas por un guion o barra (ej. "Opción 1 / Opción 2 / Opción 3"). Lista de opciones:
    - {ccr3_texto}
    14. MONTOS: Busca los valores numéricos de "Total", "Cobrado", "Devoluciones" o "Propina" (ej. de $22.644 extrae 22644.0). Debes extraer tanto el monto del pedido, la devolución y la propina de forma independiente.
    15. CAMPOS VACÍOS: Si un campo requerido (correo, país, order id, etc.) no está visible en NINGUNA de las imágenes, escribe la palabra "Revisar". EXCEPCIÓN: Para 'fraude_operacional', 'fraude_fintech' y 'contactos', si no están, déjalos completamente vacíos "".
    
    Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta de claves:
    {{
        "hora": "Hora visible en el mensaje inicial",
        "ultima_interaccion": "Marca de tiempo del último mensaje",
        "agente_escala": "Nombre del agente",
        "caso": "Tipo de caso reportado",
        "tipologia": "Tipología o categoría del caso si está indicada, si no pon vacío",
        "numero_caso": "ID o número de caso",
        "pais": "País mencionado (ej. Chile, Perú, etc)",
        "correo": "Correo del cliente",
        "pedido_link": "Enlace completo",
        "order_id": "ID del pedido o pago (ej. PAY3-...)",
        "user_id": "User ID si aparece",
        "motivo_reclamo": "Resumen conciso del problema de 1 o 2 líneas",
        "ccr3": "Categoría exacta del catálogo provisto",
        "monto_pedido": 0.0,
        "monto_devolucion": 0.0,
        "propina": 0.0,
        "numeros": "Números de contacto o referencia si los hay",
        "fraude_operacional": "Indicador o texto de fraude operacional",
        "fraude_fintech": "Indicador o texto de fraude fintech",
        "seguidores": "Cantidad de seguidores si aplica (número o 'no corresponde')",
        "red_social": "Nombre de la red social o 'no corresponde'",
        "contactos": "Contactos mencionados si aplica"
    }}
    """

    try:
        model = GenerativeModel(modelo_seguro)

        contenido = [prompt]
        if not isinstance(imagenes_pil, list):
            imagenes_pil = [imagenes_pil]

        for img in imagenes_pil:
            max_size = 800
            if max(img.size) > max_size:
                ratio = max_size / float(max(img.size))
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG')
            contenido.append(Part.from_data(data=img_byte_arr.getvalue(), mime_type="image/jpeg"))

        response = model.generate_content(
            contenido,
            generation_config={"temperature": 0.1, "response_mime_type": "application/json"}
        )

        try:
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
        except ValueError:
            st.error("❌ La IA no pudo generar una respuesta (posible bloqueo por seguridad o error de formato).")
            return None

        start = raw_text.find('{')
        if start != -1:
            raw_text = raw_text[start:]
            end = raw_text.rfind('}')
            while end != -1:
                try:
                    parsed_json = json.loads(raw_text[:end+1], strict=False)
                    parsed_json = {k.lower(): v for k, v in parsed_json.items()}
                    st.toast(f"✅ ¡Datos extraídos con éxito usando Vertex AI ({modelo_seguro})!", icon="🕵️‍♂️")
                    return parsed_json
                except json.JSONDecodeError:
                    end = raw_text.rfind('}', 0, end)

        st.error("❌ La IA no devolvió un formato válido.")
        return None

    except Exception as e:
        if "modelo_gemini_cache" in st.session_state:
            del st.session_state["modelo_gemini_cache"]
        if "vertex_initialized" in st.session_state:
            del st.session_state["vertex_initialized"]
        error_msg = str(e)
        st.error(f"❌ Error con Vertex AI: {error_msg}")
        return None


def evaluar_oms_gemini(transcripcion, comunicacion_data, gestion_data, agente_c=""):
    if not _init_vertex():
        return {"om1": "Error Vertex AI", "om2": "Error", "om3": "Error", "om4": "Error"}

    modelo_seguro = obtener_modelo_valido()
    if not modelo_seguro:
        return {"om1": "Error Modelo", "om2": "Error", "om3": "Error", "om4": "Error"}

    lista_comunicacion = []
    for fila in comunicacion_data[1:]:
        if len(fila) >= 3 and fila[2].strip():
            lista_comunicacion.append(fila[2].strip())

    lista_gestion = []
    for fila in gestion_data[1:]:
        if len(fila) >= 2 and fila[1].strip():
            lista_gestion.append(fila[1].strip())

    es_bot = "bot" in agente_c.lower()

    instrucciones_om = f"""
    Tienes dos listas de errores definidos:
    
    Lista de Errores de Comunicación posibles (devuelve exactamente el texto si ocurre):
    - {chr(10) + '    - '.join(lista_comunicacion)}
    
    Lista de Errores de Gestión posibles (devuelve exactamente el texto si ocurre):
    - {chr(10) + '    - '.join(lista_gestion)}
    
    REGLAS ESTRICTAS PARA LAS OM:
    1. Identifica TODOS los errores que el agente haya cometido basados en las dos listas anteriores.
    2. Si encuentras un error grave que NO está en las listas, también puedes agregarlo como una OM general.
    3. Asigna los errores encontrados a las claves 'om1', 'om2', 'om3' y 'om4' por orden de importancia.
    4. DEBES intentar extraer entre 2 y 4 OMs (oportunidades de mejora) si aplican. Si hay menos de 4, llena los espacios sobrantes con 'no aplica'. Si la interacción fue excelente y no hay errores, pon 'no aplica' en todas.
    """ if not es_bot else "El agente es un BOT. NO busques Oportunidades de Mejora (OM), asigna directamente 'no aplica' a las claves 'om1', 'om2', 'om3' y 'om4'."

    prompt = f"""
    Eres un auditor de calidad de atención al cliente. Analiza la siguiente transcripción de chat entre un agente y un cliente.
    
    TRANSCRIPCIÓN:
    {transcripcion}
    
    TAREA:
    Evaluación de Oportunidades de Mejora (OM):
    {instrucciones_om}
       
    Devuelve ÚNICAMENTE un JSON válido con las claves "om1", "om2", "om3" y "om4".
    """

    try:
        model = GenerativeModel(modelo_seguro)
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.1, "response_mime_type": "application/json"}
        )

        try:
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
        except ValueError:
            return {"om1": "Bloqueo API", "om2": "Bloqueo API", "om3": "Bloqueo API", "om4": "Bloqueo API"}

        start = raw_text.find('{')
        if start != -1:
            raw_text = raw_text[start:]
            end = raw_text.rfind('}')
            if end != -1:
                parsed_json = json.loads(raw_text[:end+1], strict=False)
                parsed_json = {k.lower(): v for k, v in parsed_json.items()}
                for key in ["om1", "om2", "om3", "om4"]:
                    if key not in parsed_json or not parsed_json[key]:
                        parsed_json[key] = "no aplica"
                return parsed_json

        return {"om1": "Error JSON", "om2": "Error", "om3": "Error", "om4": "Error"}
    except Exception as e:
        if "modelo_gemini_cache" in st.session_state:
            del st.session_state["modelo_gemini_cache"]
        if "vertex_initialized" in st.session_state:
            del st.session_state["vertex_initialized"]
        error_msg = str(e)
        return {"om1": f"Error: {error_msg}", "om2": "Error", "om3": "Error", "om4": "Error"}


def evaluar_resumen_gemini(transcripcion):
    if not _init_vertex():
        return "Error Vertex AI"

    modelo_seguro = obtener_modelo_valido()
    if not modelo_seguro:
        return "Error Modelo"

    prompt = f"""
    Eres un analista de operaciones de atención al cliente. Tu objetivo es redactar un resumen ejecutivo y narrativo de la siguiente interacción para un postmortem corporativo.
    
    TRANSCRIPCIÓN:
    {transcripcion}
    
    REGLAS ESTRICTAS DE REDACCIÓN:
    1. Ve DIRECTO al grano. Empieza directamente narrando lo sucedido en la interacción (ej: "El cliente se comunica reportando...", "El usuario consulta por...").
    2. ESTÁ TOTALMENTE PROHIBIDO incluir preámbulos, saludos o introducciones tales como:
       - "Como auditor de calidad..."
       - "El análisis de la transcripción revela lo siguiente:"
       - "A continuación se presenta el resumen..."
       - "En esta interacción..."
    3. Sintetiza toda la conversación en un único párrafo conciso y fluido (máximo 4 a 5 líneas) que cubra:
       - Motivo de contacto y problema del cliente.
       - Acciones, validaciones o respuestas del agente (o bot).
       - Resolución final o estado en que quedó el caso.
    4. Tono neutral, profesional y objetivo en tercera persona.
    """

    try:
        model = GenerativeModel(modelo_seguro)
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.1}
        )
        try:
            texto = response.text.strip()
            # Limpiar cualquier preámbulo residual que la IA haya colocado
            patrones_preambulo = [
                r"^como auditor(?: de calidad)?[^:\n]*[:\n-]+\s*",
                r"^el an[áa]lisis de la transcripci[óo]n[^:\n]*[:\n-]+\s*",
                r"^an[áa]lisis de la transcripci[óo]n[^:\n]*[:\n-]+\s*",
                r"^an[áa]lisis de la interacci[óo]n[^:\n]*[:\n-]+\s*",
                r"^resumen de la interacci[óo]n[^:\n]*[:\n-]+\s*",
                r"^a continuaci[óo]n[^:\n]*[:\n-]+\s*",
            ]
            for pat in patrones_preambulo:
                texto = re.sub(pat, "", texto, flags=re.IGNORECASE).strip()
            texto = re.sub(r"^[-*•\s]+", "", texto).strip()
            return texto
        except ValueError:
            return "El modelo no pudo generar un resumen (posible bloqueo por seguridad)."
    except Exception as e:
        if "modelo_gemini_cache" in st.session_state:
            del st.session_state["modelo_gemini_cache"]
        if "vertex_initialized" in st.session_state:
            del st.session_state["vertex_initialized"]
        return f"Error Vertex AI: {e}"
