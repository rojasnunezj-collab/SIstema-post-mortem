# gemini_api.py
import os
import json
import re
import streamlit as st
import google.generativeai as genai

@st.cache_data(ttl=3600, show_spinner=False)
def obtener_modelo_valido(api_key):
    """Encuentra y prueba el mejor modelo disponible para esta API key, y lo cachea por 1 hora."""
    genai.configure(api_key=api_key)
    try:
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    except Exception:
        return None

    # Ordenar para priorizar los modelos 'flash' (más rápidos)
    flash_models = [m for m in modelos if 'flash' in m.lower()]
    otros_models = [m for m in modelos if 'flash' not in m.lower()]
    
    for nombre_modelo in (flash_models + otros_models):
        try:
            model = genai.GenerativeModel(nombre_modelo)
            # Prueba de vida rápida para descartar los modelos obsoletos o con error 404
            if model.generate_content("Hola"):
                return nombre_modelo
        except Exception:
            continue
            
    return None

from google_services import obtener_catalogo_ccr3

def extraer_datos_gemini(imagen_pil):
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
    ccr3_texto = "\n- ".join(ccr3_opciones[:50]) # Limitar a 50 si hay muchos para evitar sobrecarga de tokens
    
    prompt = f"""
    Eres un auditor experto de Operaciones Digitales. Analiza las capturas de pantalla de un caso de soporte y extrae los datos.
    
    REGLAS ESTRICTAS DE EXTRACCIÓN:
    1. HORA: Extrae la hora que está al lado de la palabra "WORKFLOW".
    2. AGENTE: Extrae solo el nombre y apellido del agente que está arrobado (ejemplo, si dice @SM_Milena Arias_NDO, extrae "Milena Arias").
    3. CASO: Extrae el texto que está después de la frase "reclamo de un:".
    4. NÚMERO DE CASO: Extrae el número después de "DETALLE DEL CASO #" (si no hay, pon "-").
    5. SEGUIDORES: Si el caso no dice "influencer", pon "no corresponde". Si sí, extrae el número.
    6. PAÍS: Extrae el texto al lado de "País:".
    7. CORREO: Extrae el texto al lado de "Correo:".
    8. LINK PEDIDO: Copia el link completo (si no hay pon "revisar").
    9. ORDER ID: Extrae el código que está en el link del pedido, justo después del último "/".
    10. MOTIVO DE RECLAMO: ¡MUY IMPORTANTE! NO copies el texto tal cual. Analiza el problema y redáctalo de forma resumida y profesional (máximo 3 líneas).
    11. CCR3: Basado en tu resumen, DEBES elegir ÚNICAMENTE una categoría de esta lista exacta:
    - {ccr3_texto}
    Si no estás seguro, elige la más parecida, pero NUNCA inventes una categoría fuera de esa lista.
    12. MONTOS: Busca los valores numéricos de "Total", "Cobrado" o "Devoluciones" (ej. de $22.644 extrae 22644.0).
    13. Para los demás datos (numeros, fraude, etc.) si no están visibles, déjalos en blanco "". No inventes.
    
    Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta de claves:
    {{
        "hora": "Hora visible en el mensaje",
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
        "seguidores": "Cantidad de seguidores si aplica",
        "contactos": "Contactos mencionados si aplica"
    }}
    """
    
    try:
        model = genai.GenerativeModel(modelo_seguro)
        response = model.generate_content([prompt, imagen_pil])
        
        match = re.search(r'\{.*\}', response.text.replace("```json", "").replace("```", ""), re.DOTALL)
        if match: 
            st.toast(f"✅ ¡Datos extraídos con éxito usando {modelo_seguro}!", icon="🚀")
            return json.loads(match.group(0))
        return None
        
    except Exception as e:
        st.error(f"❌ Error parseando JSON: {e}")
        return None