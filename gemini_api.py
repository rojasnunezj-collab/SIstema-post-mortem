# gemini_api.py
import os
import json
import streamlit as st
import google.generativeai as genai

def extraer_datos_gemini(imagen_pil):
    """Envía la imagen a Gemini usando la librería clásica y estable para garantizar la conexión."""
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
    
    if not api_key:
        st.error("⚠️ No se encontró la API Key de Gemini en los Secrets.")
        return None
        
    # Configuración de la librería clásica
    genai.configure(api_key=api_key)
    
    prompt = """
    Extrae los datos de esta imagen de escalamiento. 
    Limpia el nombre del agente para dejar solo nombre y apellido, sin el @ ni prefijos.
    Analiza el problema y sugiere las tipificaciones CCR3 más precisas.
    
    Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta de claves:
    {
        "hora": "La hora del mensaje (ej. 6:02 PM)",
        "agente_escala": "Nombre y apellido",
        "caso": "El tipo de caso",
        "numero_caso": "Número de caso",
        "pais": "País mencionado",
        "correo": "Correo electrónico",
        "pedido_link": "Enlace completo",
        "order_id": "El ID numérico extraído del enlace",
        "motivo_reclamo": "Resumen muy breve del problema",
        "ccr3": "Lista de CCR3 sugeridos"
    }
    """
    
    try:
        # Usamos el modelo más estable y rápido disponible
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        response = model.generate_content(
            [prompt, imagen_pil],
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1 # Temperatura baja para que no alucine datos
            )
        )
        
        st.toast("✅ Conexión exitosa y datos extraídos.", icon="🚀")
        return json.loads(response.text)
        
    except Exception as e:
        st.error(f"❌ Error al procesar la imagen con la IA: {e}")
        return None