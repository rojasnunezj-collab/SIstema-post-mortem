# text_processor.py
import os
import streamlit as st
import google.generativeai as genai

@st.cache_data(ttl=3600, show_spinner=False)
def obtener_modelo_valido(api_key):
    """Encuentra el mejor modelo disponible probando máximo 3 opciones para evitar el límite de cuota y evadir 404s."""
    genai.configure(api_key=api_key)
    try:
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    except Exception:
        modelos = ["models/gemini-1.5-flash", "models/gemini-pro"]

    # Excluir modelos experimentales o descontinuados que causan 404 (ej. 2.5, 3.6)
    modelos_seguros = [m for m in modelos if "2.5" not in m and "3.6" not in m]
    
    flash = [m for m in modelos_seguros if 'flash' in m.lower()]
    otros = [m for m in modelos_seguros if 'flash' not in m.lower()]
    
    # Solo probamos máximo 3 candidatos para NO agotar tu cuota de API por minuto
    candidatos = (flash[:2] + otros[:1]) if flash else otros[:3]
    
    if not candidatos:
        candidatos = ["models/gemini-pro"] # Fallback histórico indestructible
        
    for m in candidatos:
        try:
            model = genai.GenerativeModel(m)
            if model.generate_content("a"): # Prueba súper ligera
                return m
        except Exception:
            continue
            
    return candidatos[0]

def mejorar_redaccion(reporte_cliente, analisis_caso, resolucion_caso, pais):
    """
    Reescribe las 3 secciones utilizando una única llamada con JSON Schema forzado.
    Retorna una tupla de 3 strings: (reporte, analisis, resolucion).
    """
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
    
    if not api_key:
        st.error("❌ No se encontró la API Key de Gemini.")
        return reporte_cliente, analisis_caso, resolucion_caso
        
    try:
        genai.configure(api_key=api_key.strip())
    except Exception as e:
        st.error(f"❌ Error API: {e}")
        return reporte_cliente, analisis_caso, resolucion_caso
        
    modelo_seguro = obtener_modelo_valido(api_key.strip())
    
    if not modelo_seguro:
        st.error("❌ Ningún modelo en tu API Key funcionó.")
        return reporte_cliente, analisis_caso, resolucion_caso
        
    regla_wallet = "pedidos ya pagos" if pais.strip().lower() == "argentina" else "wallet o billetera"
    
    prompt = f"""
Reescribe los siguientes textos (Reporte, Análisis, Resolución) para un documento oficial de Postmortem de atención al cliente.

OBJETIVO:
El texto resultante debe ser sumamente corporativo, analítico, profesional, y con ortografía perfecta. 

REGLAS DE ESTILO (¡OBLIGATORIO!):
1. Eres un formateador puro. NO agregues introducciones, NO expliques tus cambios, NO devuelvas markdown fuera del JSON.
2. NUNCA empieces los párrafos con frases repetitivas como "Tras revisar", "Al verificar", "Se procede a", o "Tras realizar la revisión". Usa variedad y ve directo al grano (ej: "Se identificó...", "El usuario indicó...", "El sistema muestra...").
3. Evita redundancias. Si el texto original repite lo mismo, condénsalo en un texto claro y potente.
4. Vocabulario Obligatorio: Usa "reintegro" o "reembolso", "cupo" o "voucher". Llama a la billetera virtual del cliente exactamente como: "{regla_wallet}". Alterna entre los términos "cliente" y "usuario" para enriquecer la lectura.
5. NO inventes datos, fechas, motivos ni montos que no estén en el texto original.
6. Mantén la objetividad absoluta: no uses lenguaje emocional ("lamentablemente", "desafortunadamente", "por suerte").

TEXTOS A REESCRIBIR:
[Reporte]: {reporte_cliente}
[Análisis]: {analisis_caso}
[Resolución]: {resolucion_caso}
"""
    
    import time
    import typing_extensions as typing
    import json
    
    class DraftResponse(typing.TypedDict):
        reporte_editado: str
        analisis_editado: str
        resolucion_editado: str
        
    model = genai.GenerativeModel(modelo_seguro)
    for intento in range(3):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1, 
                    max_output_tokens=1000,
                    response_mime_type="application/json",
                    response_schema=DraftResponse
                )
            )
            
            datos = json.loads(response.text)
            return datos.get("reporte_editado", ""), datos.get("analisis_editado", ""), datos.get("resolucion_editado", "")
        except Exception as sub_e:
            if "500" in str(sub_e) or "429" in str(sub_e):
                if intento < 2:
                    time.sleep(2)
                    continue
            return reporte_cliente, analisis_caso, resolucion_caso # Fallback
            
    return reporte_cliente, analisis_caso, resolucion_caso