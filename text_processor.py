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
            response = model.generate_content(prompt)
            if response:
                break
        except Exception as e:
            ultimo_error = str(e)
            continue
            
    if response:
        return response.text
    else:
        st.error(f"❌ Error al mejorar la redacción con IA. Último error: {ultimo_error}")
        return None