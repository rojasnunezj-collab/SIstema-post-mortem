# text_processor.py
import os
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

    flash_models = [m for m in modelos if 'flash' in m.lower()]
    otros_models = [m for m in modelos if 'flash' not in m.lower()]
    
    for nombre_modelo in (flash_models + otros_models):
        try:
            model = genai.GenerativeModel(nombre_modelo)
            if model.generate_content("Hola"):
                return nombre_modelo
        except Exception:
            continue
            
    return None

def mejorar_redaccion(borrador):
    """
    Toma el texto crudo del analista y lo reescribe con tono ejecutivo, 
    eliminando muletillas y optimizando la estructura para el Postmortem.
    """
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
    
    if not api_key:
        st.error("⚠️ No se encontró la API Key de Gemini.")
        return None
        
    try:
        genai.configure(api_key=api_key.strip())
    except Exception as e:
        st.error(f"❌ Error API: {e}")
        return None
        
    modelo_seguro = obtener_modelo_valido(api_key.strip())
    
    if not modelo_seguro:
        st.error("❌ Ningún modelo en tu API Key funcionó.")
        return None
    
    prompt = f"""
    Actúa como un auditor de operaciones digitales y control de calidad. 
    Reescribe el siguiente texto que describe la resolución de un caso crítico de soporte.
    
    Reglas estrictas:
    - Mantén un tono formal, directo, profesional y corporativo.
    - Elimina absolutamente todas las muletillas, redundancias y palabras repetidas.
    - Estructura las acciones tomadas de forma clara y concisa.
    - Mantén la fidelidad de los hechos: NO inventes datos, montos, ni acciones que no estén en el texto original.
    
    Texto original del analista:
    {borrador}
    """
    
    try:
        model = genai.GenerativeModel(modelo_seguro)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"❌ Error al mejorar la redacción con IA: {e}")
        return None