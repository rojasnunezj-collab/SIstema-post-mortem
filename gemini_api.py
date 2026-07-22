# gemini_api.py
import os
import json
import re
import streamlit as st
import google.generativeai as genai

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
    
    prompt = """
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
    10. MOTIVO DE RECLAMO: Resume el motivo del reclamo en máximo 3 líneas, sintetizando sin eliminar cosas importantes.
    11. CCR3: Basado en tu resumen del motivo, sugiere la categoría de resolución (máximo 3 palabras).
    12. MONTOS: Busca los valores numéricos de "Total", "Cobrado" o "Devoluciones" (ej. de $22.644 extrae 22644.0).
    13. Para los demás datos (numeros, fraude, etc.) si no están visibles, déjalos en blanco "". No inventes.
    
    Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta de claves:
    {
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
        "ccr3": "Sugerencia temporal de categoría",
        "monto_pedido": 0.0,
        "monto_devolucion": 0.0,
        "numeros": "Números de contacto o referencia si los hay",
        "fraude_operacional": "Indicador o texto de fraude operacional",
        "fraude_fintech": "Indicador o texto de fraude fintech",
        "seguidores": "Cantidad de seguidores si aplica",
        "contactos": "Contactos mencionados si aplica"
    }
    """
    
    modelos_fallback = [
        'gemini-2.0-flash',
        'gemini-2.0-flash-exp',
        'gemini-1.5-flash-latest',
        'gemini-1.5-flash-002',
        'gemini-1.5-flash',
        'gemini-pro'
    ]
    
    response = None
    ultimo_error = ""
    
    for nombre_modelo in modelos_fallback:
        try:
            model = genai.GenerativeModel(nombre_modelo)
            response = model.generate_content([prompt, imagen_pil])
            if response:
                st.toast(f"✅ ¡Datos extraídos con éxito usando {nombre_modelo}!", icon="🚀")
                break
        except Exception as e:
            ultimo_error = str(e)
            continue
            
    if not response:
        st.error(f"❌ Error al procesar con IA. Último error: {ultimo_error}")
        return None

    try:
        match = re.search(r'\{.*\}', response.text.replace("```json", "").replace("```", ""), re.DOTALL)
        if match: 
            return json.loads(match.group(0))
        return None
        
    except Exception as e:
        st.error(f"❌ Error parseando JSON: {e}")
        return None