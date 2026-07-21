# gemini_api.py
import os
import json
import streamlit as st
import google.generativeai as genai

def extraer_datos_gemini(imagen_pil):
    """Envía la imagen probando solo los modelos de visión más rápidos y estables."""
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
    
    if not api_key:
        st.error("⚠️ No se encontró la API Key de Gemini en los Secrets.")
        return None
        
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
    
    # Lista estricta solo con los modelos actuales de visión
    modelos_seguros = [
        'gemini-1.5-flash',
        'gemini-1.5-flash-8b',
        'gemini-1.5-pro'
    ]
    
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
            return json.loads(response.text)
            
        except Exception as e:
            ultimo_error = str(e)
            print(f"Fallo controlado con {modelo}: {ultimo_error}") # Se verá en los logs de Streamlit
            continue
            
    # Si falla con los 3 principales, lo mostramos de inmediato sin dejarlo cargando
    st.error(f"❌ Los modelos de visión fallaron. Último error: {ultimo_error}")
    return None