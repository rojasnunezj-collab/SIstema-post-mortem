# gemini_api.py
import os
import json
import streamlit as st
import google.generativeai as genai

def extraer_datos_gemini(imagen_pil):
    """Envía la imagen a Gemini detectando automáticamente el modelo disponible."""
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
    
    if not api_key:
        st.error("⚠️ No se encontró la API Key de Gemini en los Secrets.")
        return None
        
    genai.configure(api_key=api_key)
    
    # 1. AUTODETECCIÓN INTELIGENTE DEL MODELO
    modelo_elegido = None
    try:
        # Le preguntamos a Google qué modelos soporta esta API Key
        modelos_disponibles = [
            m.name for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
        ]
        
        if not modelos_disponibles:
            st.error("❌ Tu API Key no tiene modelos asignados. Revisa que 'Generative Language API' esté habilitada en Google Cloud.")
            return None
            
        # Buscamos nuestra primera opción (flash), si no, usamos el que esté disponible
        for m in modelos_disponibles:
            if '1.5-flash' in m:
                modelo_elegido = m
                break
        
        if not modelo_elegido:
            modelo_elegido = modelos_disponibles[0] # Agarra el primero de la lista de Google
            
    except Exception as e:
        st.error(f"❌ Error al consultar a Google los modelos disponibles: {e}")
        return None

    # 2. PROCESAMIENTO
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
        model = genai.GenerativeModel(modelo_elegido)
        response = model.generate_content(
            [prompt, imagen_pil],
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        
        st.toast(f"✅ Extraído con éxito usando: {modelo_elegido}", icon="🚀")
        return json.loads(response.text)
        
    except Exception as e:
        st.error(f"❌ Error al procesar con el modelo {modelo_elegido}: {e}")
        return None