# text_processor.py
import os
import io
import json
import time
import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel

def mejorar_redaccion(reporte_cliente, analisis_caso, resolucion_caso, pais):
    """
    Reescribe las 3 secciones utilizando una única llamada con JSON Schema forzado.
    Retorna una tupla de 4 strings: (reporte, analisis, resolucion, warning_msg).
    """
    # Reutiliza la inicialización de gemini_api para no duplicar código
    try:
        from gemini_api import _init_vertex, obtener_modelo_valido
    except ImportError:
        return reporte_cliente, analisis_caso, resolucion_caso, "Error importando módulo gemini_api."

    if not _init_vertex():
        return reporte_cliente, analisis_caso, resolucion_caso, "Error inicializando Vertex AI."

    modelo_seguro = obtener_modelo_valido()
    if not modelo_seguro:
        return reporte_cliente, analisis_caso, resolucion_caso, "No se encontró un modelo de Vertex AI disponible."

    regla_wallet = "pedidos ya pagos" if pais.strip().lower() == "argentina" else "wallet o billetera"

    prompt = f"""
Reescribe los siguientes textos (Reporte, Análisis, Resolución) para un documento oficial de Postmortem de atención al cliente.

OBJETIVO:
El texto resultante debe ser sumamente corporativo, analítico, profesional, y con ortografía perfecta. 

REGLAS DE ESTILO (¡OBLIGATORIO!):
1. Eres un formateador puro. Tu única tarea es mejorar y reescribir los textos. NUNCA devuelvas el texto original sin cambios a menos que ya sea perfecto.
2. NUNCA empieces los párrafos con frases repetitivas como "Tras revisar", "Al verificar", "Se procede a", o "Tras realizar la revisión". Usa variedad y ve directo al grano (ej: "Se identificó...", "El usuario indicó...", "El sistema muestra...").
3. Evita redundancias. Si el texto original repite lo mismo, condénsalo en un texto claro y potente.
4. Vocabulario Obligatorio: Usa "reintegro" o "reembolso", "cupo" o "voucher". Llama a la billetera virtual del cliente exactamente como: "{regla_wallet}". Alterna entre los términos "cliente" y "usuario" para enriquecer la lectura.
5. NO inventes datos, fechas, motivos ni montos que no estén en el texto original.
6. Mantén la objetividad absoluta: no uses lenguaje emocional ("lamentablemente", "desafortunadamente", "por suerte").

TEXTOS A REESCRIBIR (MEJÓRALOS OBLIGATORIAMENTE):
[Reporte]: {reporte_cliente}
[Análisis]: {analisis_caso}
[Resolución]: {resolucion_caso}

IMPORTANTE: Responde ÚNICAMENTE con un objeto JSON válido. El JSON debe tener exactamente estas claves:
"reporte_editado", "analisis_editado", "resolucion_editado".
No agregues comentarios ni comillas invertidas fuera del JSON.
"""

    model = GenerativeModel(modelo_seguro)
    for intento in range(3):
        try:
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 2048, "response_mime_type": "application/json"}
            )

            try:
                raw_text = response.text.replace("```json", "").replace("```", "").strip()
            except ValueError:
                return reporte_cliente, analisis_caso, resolucion_caso, "La IA no pudo generar el texto (posible bloqueo por seguridad o formato)."

            start = raw_text.find('{')
            if start != -1:
                raw_text = raw_text[start:]
                end = raw_text.rfind('}')
                if end != -1:
                    datos = json.loads(raw_text[:end+1], strict=False)
                else:
                    return reporte_cliente, analisis_caso, resolucion_caso, "El formato JSON quedó incompleto (sin cierre)."
            else:
                return reporte_cliente, analisis_caso, resolucion_caso, "La IA no devolvió un JSON válido."

            if not datos.get("reporte_editado"):
                return reporte_cliente, analisis_caso, resolucion_caso, "La IA devolvió campos vacíos, se usaron los originales."
            return datos.get("reporte_editado", ""), datos.get("analisis_editado", ""), datos.get("resolucion_editado", ""), None

        except Exception as e:
            if "modelo_gemini_cache" in st.session_state:
                del st.session_state["modelo_gemini_cache"]
            if "vertex_initialized" in st.session_state:
                del st.session_state["vertex_initialized"]
            error_msg = str(e)
            if intento < 2:
                time.sleep(2)
                continue
            return reporte_cliente, analisis_caso, resolucion_caso, f"Error del mejorador: {error_msg}"

    return reporte_cliente, analisis_caso, resolucion_caso, "No se pudo mejorar el texto después de varios intentos."