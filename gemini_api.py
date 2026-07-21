# gemini_api.py
import os
import json
import streamlit as st
import google.generativeai as genai

def extraer_datos_gemini(imagen_pil):
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
    
    if not api_key:
        st.error("⚠️ No se encontró la API Key.")
        return None
        
    genai.configure(api_key=api_key)
    
    prompt = """
    Eres un auditor experto de Operaciones Digitales. Analiza esta captura de pantalla de un caso de soporte y extrae los datos.
    
    REGLAS ESTRICTAS:
    1. Si un dato no está visible, déjalo en blanco "". No inventes.
    2. Agente: Extrae solo el Nombre y Apellido.
    3. Montos: Busca valores numéricos con el símbolo $. Conviértelos a formato numérico (ej. si dice $22.644, escribe 22644.0).
    4. Resumen: Lee todo el texto del problema y haz un resumen conciso de máximo 2 líneas.
    
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
        "motivo_reclamo": "Resumen conciso del problema de 1 o 2 líneas",
        "ccr3": "Sugerencia temporal de categoría",
        "monto_pedido": 0.0,
        "monto_devolucion": 0.0
    }
    """
    
    modelos_seguros = ['gemini-1.5-flash', 'gemini-1.5-flash-8b', 'gemini-1.5-pro']
    ultimo_error = ""
    
    for modelo in modelos_seguros:
        try:
            model = genai.GenerativeModel(modelo)
            response = model.generate_content(
                [prompt, imagen_pil],
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            st.toast(f"✅ ¡Datos extraídos usando: {modelo}!", icon="🚀")
            
            # Limpieza forzada del texto por si la IA devuelve formato Markdown
            texto_limpio = response.text.replace('```json', '').replace('```', '').strip()
            
            return json.loads(texto_limpio)
            
        except Exception as e:
            ultimo_error = str(e)
            continue
            
    st.error(f"❌ Los modelos fallaron al leer la imagen. Error exacto: {ultimo_error}")
    return None