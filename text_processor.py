# text_processor.py
import os
import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel
import json
import time

def obtener_modelo_valido():
    if "modelo_gemini_cache" in st.session_state and "vertex_location" in st.session_state:
        try:
            from google.oauth2 import service_account
            cred_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in cred_dict:
                cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            credentials = service_account.Credentials.from_service_account_info(cred_dict)
            vertexai.init(project="postmortem-503102", location=st.session_state["vertex_location"], credentials=credentials)
            return st.session_state["modelo_gemini_cache"]
        except:
            pass

    try:
        from google.oauth2 import service_account
        if "gcp_service_account" in st.secrets:
            secret_val = st.secrets["gcp_service_account"]
            if isinstance(secret_val, str):
                import json
                cred_dict = json.loads(secret_val)
            else:
                cred_dict = dict(secret_val)
            if "private_key" in cred_dict:
                cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            credentials = service_account.Credentials.from_service_account_info(cred_dict)
        else:
            credentials = None
            
        msg = st.empty()
        msg.info("⏳ Buscando modelo y región disponible en Vertex AI...")
        
        combinaciones = [
            ("us-central1", "gemini-1.5-flash-001"),
            ("us-central1", "gemini-1.5-flash-002"),
            ("us-central1", "gemini-1.5-flash"),
            ("us-central1", "gemini-1.0-pro-002"),
            ("us-east4", "gemini-1.5-flash-001"),
            ("us-east4", "gemini-1.5-flash-002"),
            ("us-east4", "gemini-1.5-flash")
        ]
        
        errores_ocultos = []
        for loc, mod in combinaciones:
            try:
                vertexai.init(project="postmortem-503102", location=loc, credentials=credentials)
                test_model = GenerativeModel(mod)
                test_model.generate_content("a")
                st.session_state["modelo_gemini_cache"] = mod
                st.session_state["vertex_location"] = loc
                msg.empty()
                return mod
            except Exception as e:
                errores_ocultos.append(f"[{loc}] {mod}: {e}")
                continue
                
        msg.empty()
        st.error("❌ Ningún modelo funcionó en ninguna región. Detalles de los errores:")
        for err in errores_ocultos:
            st.write(err)
        return None
    except Exception as e:
        st.error(f"Error cargando credenciales: {e}")
        return None

def mejorar_redaccion(reporte_cliente, analisis_caso, resolucion_caso, pais):
    """
    Reescribe las 3 secciones utilizando una única llamada con JSON Schema forzado.
    Retorna una tupla de 4 strings: (reporte, analisis, resolucion, warning_msg).
    """
    modelo_seguro = obtener_modelo_valido()
    
    if not modelo_seguro:
        st.error("❌ No se encontró modelo Vertex AI.")
        return reporte_cliente, analisis_caso, resolucion_caso, "Modelo Vertex AI no encontrado."
        
    prompt = f"""
    Eres un auditor experto de calidad en atención al cliente para un servicio en {pais}.
    Tu objetivo es mejorar la redacción, corregir ortografía y dar un tono formal y técnico a los siguientes 3 textos de un 'postmortem' o reporte de incidencia.
    
    TEXTO 1 (Reporte del Cliente):
    {reporte_cliente}
    
    TEXTO 2 (Análisis del Caso):
    {analisis_caso}
    
    TEXTO 3 (Resolución del Caso):
    {resolucion_caso}
    
    REGLAS:
    - NO alteres los hechos, las cantidades, los nombres ni la historia. Solo mejora la redacción.
    - Evita un tono robótico, debe sonar como escrito por un humano experto y serio.
    - Trata el texto como si viniera de {pais}, usando la terminología adecuada (ej. si es Chile, mantén términos chilenos válidos).
    
    Devuelve ÚNICAMENTE un JSON válido con estas claves exactas:
    {{
        "reporte_editado": "Texto mejorado 1",
        "analisis_editado": "Texto mejorado 2",
        "resolucion_editado": "Texto mejorado 3"
    }}
    """
    
    for intento in range(3):
        try:
            model = GenerativeModel(modelo_seguro)
            
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.3, "response_mime_type": "application/json"}
            )
            
            try:
                raw_text = response.text.replace("```json", "").replace("```", "").strip()
            except ValueError:
                return reporte_cliente, analisis_caso, resolucion_caso, "El modelo bloqueó la respuesta por seguridad."
                
            start = raw_text.find('{')
            if start == -1:
                return reporte_cliente, analisis_caso, resolucion_caso, "La IA no devolvió el formato esperado."
                
            raw_text = raw_text[start:]
            end = raw_text.rfind('}')
            if end == -1:
                return reporte_cliente, analisis_caso, resolucion_caso, "Formato JSON incompleto."
                
            datos = json.loads(raw_text[:end+1], strict=False)
            
            if not datos.get("reporte_editado"):
                return reporte_cliente, analisis_caso, resolucion_caso, "La IA devolvió campos vacíos, se usaron los originales."
            return datos.get("reporte_editado", ""), datos.get("analisis_editado", ""), datos.get("resolucion_editado", ""), None
        except Exception as e:
            if "modelo_gemini_cache" in st.session_state:
                del st.session_state["modelo_gemini_cache"]
            if "vertex_location" in st.session_state:
                del st.session_state["vertex_location"]
            error_msg = str(e)
            if "500" in error_msg or "429" in error_msg or "Quota" in error_msg:
                if intento < 2:
                    time.sleep(2)
                    continue
                return reporte_cliente, analisis_caso, resolucion_caso, f"⚠️ Bloqueo de Vertex AI. Detalle: {error_msg}"
            return reporte_cliente, analisis_caso, resolucion_caso, f"Error del mejorador: {error_msg}"
            
    return reporte_cliente, analisis_caso, resolucion_caso, "No se pudo mejorar el texto después de varios intentos."