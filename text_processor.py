# text_processor.py
import os
import streamlit as st
import google.generativeai as genai

@st.cache_data(ttl=3600, show_spinner=False)
def obtener_modelo_valido(api_key):
    """Encuentra el mejor modelo disponible para esta API key."""
    genai.configure(api_key=api_key)
    
    # Evitar modelos experimentales o descontinuados que retornan 404
    return "gemini-1.5-flash"

def mejorar_redaccion(reporte_cliente, analisis_caso, resolucion_caso, pais):
    """
    Toma los tres textos crudos del analista y los reescribe con tono ejecutivo, 
    aplicando reglas estrictas de sinonimia y limpieza.
    """
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
    
    if not api_key:
        st.error("❌ No se encontró la API Key de Gemini.")
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
        
    regla_wallet = "pedidos ya pagos" if pais.strip().lower() == "argentina" else "wallet o billetera"
    
    prompt = f"""
    Actúa como un auditor de operaciones y redactor corporativo. 
    A continuación recibirás tres partes de un informe de soporte: lo que el cliente reporta, el análisis y la resolución.
    Tu objetivo es unir y mejorar la redacción de todo el texto bajo estas REGLAS ESTRICTAS:
    
    1. ESTRUCTURA INTACTA: Mantén estrictamente el orden cronológico de las 3 partes (Reporte, Análisis, Resolución).
    2. SIN MULETILLAS NI REPETICIONES: Elimina por completo muletillas, redundancias y evita repetir las mismas palabras cerca unas de otras.
    3. SINÓNIMOS OBLIGATORIOS: Debes usar variedad léxica. Usa estos sinónimos a lo largo del texto:
       - Para devoluciones usa: "reintegro" o "reembolso".
       - Para referirte a la persona usa intercaladamente: "cliente" y "usuario".
       - Para referirte a cupones usa: "cupo" o "voucher".
       - Para referirte a algo que corresponde usa: "correspondiente" o "respectivo".
       - Para referirte a la billetera virtual DEBES usar: "{regla_wallet}".
    4. FIDELIDAD: NO inventes datos, montos, ni acciones que no estén en el texto original.
    
    --- TEXTO ORIGINAL ---
    
    **El cliente / líder reporta:**
    {reporte_cliente}
    
    **Análisis del caso que se hizo:**
    {analisis_caso}
    
    **Resolución del caso:**
    {resolucion_caso}
    
    ---
    
    Devuelve ÚNICAMENTE la versión mejorada del texto completo, estructurado en párrafos limpios y formales, sin saludar ni agregar comentarios adicionales.
    """
    
    try:
        model = genai.GenerativeModel(modelo_seguro)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"❌ Error al mejorar la redacción con IA: {e}")
        return None