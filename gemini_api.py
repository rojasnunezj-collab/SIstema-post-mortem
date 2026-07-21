# gemini_api.py
import os
import json
import streamlit as st
import google.generativeai as genai

def extraer_datos_gemini(imagen_pil):
    """Envía la imagen iterando sobre todos los modelos de la API Key hasta que uno funcione."""
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
    
    try:
        # Obtenemos absolutamente todos los modelos que soportan generación de contenido
        modelos_disponibles = [
            m.name for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
        ]
        
        if not modelos_disponibles:
            st.error("❌ Tu API Key no tiene modelos asignados. Revisa tu proyecto en Google Cloud.")
            return None
            
        ultimo_error = ""
        
        # EL BUCLE INDESTRUCTIBLE: Prueba uno por uno
        for nombre_modelo in modelos_disponibles:
            try:
                model = genai.GenerativeModel(nombre_modelo)
                response = model.generate_content(
                    [prompt, imagen_pil],
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        temperature=0.1
                    )
                )
                
                # Si llega a esta línea, el modelo funcionó. Salimos del bucle.
                st.toast(f"✅ ¡Éxito! Datos extraídos usando: {nombre_modelo}", icon="🚀")
                return json.loads(response.text)
                
            except Exception as e:
                # Si falla, guardamos el error en silencio y pasamos al siguiente modelo
                ultimo_error = str(e)
                continue
                
        # Si termina el bucle y ninguno funcionó, mostramos el error del último intento
        st.error(f"❌ Todos los modelos fallaron. Último error: {ultimo_error}")
        return None
        
    except Exception as e:
        st.error(f"❌ Error al conectar con Google Cloud: {e}")
        return None