# gemini_api.py
import os
import json
import re
import streamlit as st
import google.generativeai as genai

@st.cache_data(ttl=3600, show_spinner=False)
def obtener_modelo_valido(api_key):
    """Encuentra el mejor modelo disponible probando máximo 3 opciones para evitar el límite de cuota y evadir 404s."""
    genai.configure(api_key=api_key)
    try:
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    except Exception:
        modelos = ["models/gemini-1.5-flash", "models/gemini-pro"]

    # Excluir modelos experimentales o descontinuados que causan 404 (ej. 2.5, 3.6)
    modelos_seguros = [m for m in modelos if "2.5" not in m and "3.6" not in m]
    
    flash = [m for m in modelos_seguros if 'flash' in m.lower()]
    otros = [m for m in modelos_seguros if 'flash' not in m.lower()]
    
    # Solo probamos máximo 3 candidatos para NO agotar tu cuota de API por minuto
    candidatos = (flash[:2] + otros[:1]) if flash else otros[:3]
    
    if not candidatos:
        candidatos = ["models/gemini-pro"] # Fallback histórico indestructible
        
    for m in candidatos:
        try:
            model = genai.GenerativeModel(m)
            if model.generate_content("a"): # Prueba súper ligera
                return m
        except Exception:
            continue
            
    return candidatos[0]

from google_services import obtener_catalogo_ccr3

def extraer_datos_gemini(imagenes_pil):
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
    
    if not api_key:
        st.error("⚠️ No se encontró la API Key.")
        return None
        
    try:
        genai.configure(api_key=api_key.strip())
    except Exception as e:
        st.error(f"❌ Error API: {e}")
        return None
    
    modelo_seguro = obtener_modelo_valido(api_key.strip())
    
    if not modelo_seguro:
        st.error("❌ Ningún modelo en tu API Key funcionó o todos devolvieron error 404.")
        return None
        
    # Obtener CCR3 dinámicamente
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
    14. MONTOS: Busca los valores numéricos de "Total", "Cobrado" o "Devoluciones" (ej. de $22.644 extrae 22644.0).
    15. CAMPOS VACÍOS: Si un campo requerido (correo, país, order id, etc.) no está visible en NINGUNA de las imágenes, escribe la palabra "Revisar". EXCEPCIÓN: Para 'fraude_operacional', 'fraude_fintech' y 'contactos', si no están, déjalos completamente vacíos "".
    
    Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta de claves:
    {{
        "hora": "Hora visible en el mensaje inicial",
        "ultima_interaccion": "Marca de tiempo del último mensaje",
        "agente_escala": "Nombre del agente",
        "caso": "Tipo de caso reportado",
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
        "numeros": "Números de contacto o referencia si los hay",
        "fraude_operacional": "Indicador o texto de fraude operacional",
        "fraude_fintech": "Indicador o texto de fraude fintech",
        "seguidores": "Cantidad de seguidores si aplica (número o 'no corresponde')",
        "red_social": "Nombre de la red social o 'no corresponde'",
        "contactos": "Contactos mencionados si aplica"
    }}
    """
    
    try:
        from PIL import Image
        model = genai.GenerativeModel(modelo_seguro)
        
        # Enviamos el prompt seguido de TODAS las imágenes en la lista (optimizadas)
        contenido = [prompt]
        if not isinstance(imagenes_pil, list):
            imagenes_pil = [imagenes_pil]
            
        for img in imagenes_pil:
            # Optimización de tamaño extrema para acelerar el procesamiento de IA
            max_size = 800
            if max(img.size) > max_size:
                ratio = max_size / float(max(img.size))
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            contenido.append(img)
            
        response = model.generate_content(contenido)
        
        # Extractor robusto de JSON para evadir basura generada por la IA
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        start = raw_text.find('{')
        
        if start != -1:
            raw_text = raw_text[start:]
            end = raw_text.rfind('}')
            while end != -1:
                try:
                    parsed_json = json.loads(raw_text[:end+1])
                    st.toast(f"✅ ¡Datos extraídos con éxito usando {modelo_seguro}!", icon="🕵️‍♂️")
                    return parsed_json
                except json.JSONDecodeError:
                    end = raw_text.rfind('}', 0, end)
                    
        st.error("❌ La IA no devolvió un formato válido.")
        return None
        
    except Exception as e:
        st.error(f"❌ Error parseando JSON: {e}")
        return None