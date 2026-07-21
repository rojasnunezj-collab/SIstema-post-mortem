# gemini_api.py
import os
import json
import streamlit as st
from google import genai
from pydantic import BaseModel, Field

# --- ESTRUCTURA EXACTA PARA GEMINI ---
class DatosEscalamiento(BaseModel):
    hora: str = Field(description="La hora del mensaje (ej. 6:02 PM).")
    agente_escala: str = Field(description="Nombre y apellido del agente, sin el @ ni prefijos/sufijos como SM_ o _NDO.")
    caso: str = Field(description="El tipo de caso.")
    numero_caso: str = Field(description="El número de caso.")
    pais: str = Field(description="País mencionado.")
    correo: str = Field(description="Correo electrónico del usuario.")
    pedido_link: str = Field(description="Enlace completo del pedido.")
    order_id: str = Field(description="El ID numérico del pedido extraído del enlace.")
    motivo_reclamo: str = Field(description="Resumen breve del problema.")
    ccr3: str = Field(description="Lista de CCR3 sugeridos basados en el problema (ej: Calidad de la comida, Producto incorrecto, etc).")

def extraer_datos_gemini(imagen_pil):
    """Envía la imagen a Gemini y recupera los datos estructurados."""
    # Obtenemos la API key de los secrets de Streamlit o del entorno local
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
    
    if not api_key:
        st.error("⚠️ No se encontró la API Key de Gemini en los Secrets.")
        return None
        
    client = genai.Client(api_key=api_key)
    
    prompt = """
    Extrae los datos de esta imagen de escalamiento según la estructura requerida. 
    Limpia el nombre del agente para dejar solo nombre y apellido.
    Analiza el problema y sugiere las tipificaciones CCR3 más precisas.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-1.5-flash', # VERSIÓN CORREGIDA AQUÍ
            contents=[prompt, imagen_pil],
            config={
                "response_mime_type": "application/json",
                "response_schema": DatosEscalamiento,
                "temperature": 0.1 # Temperatura baja para que sea muy preciso
            },
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"❌ Error al procesar la imagen con la IA: {e}")
        return None