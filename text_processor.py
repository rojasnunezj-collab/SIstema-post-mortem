# text_processor.py
import os
import streamlit as st
import google.generativeai as genai

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
        model = genai.GenerativeModel('gemini-3.0-flash')
    except Exception as e:
        st.error(f"❌ Error conectando con Gemini: {e}")
        return None

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"❌ Error al mejorar la redacción con IA: {e}")
        return None