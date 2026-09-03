# text_processor.py
import os
import io
import re
import json
import time
import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel

def _extraer_json_tolerante(raw_text, reporte_orig, analisis_orig, resolucion_orig):
    """
    Intenta parsear JSON estrictamente y, si está incompleto o truncado,
    rescata las secciones mediante regex para no perder el trabajo de la IA.
    """
    datos = {}
    start = raw_text.find('{')
    if start != -1:
        text_candidate = raw_text[start:]
        end = text_candidate.rfind('}')
        if end != -1:
            try:
                datos = json.loads(text_candidate[:end+1], strict=False)
            except json.JSONDecodeError:
                datos = {}

    claves = ["reporte_editado", "analisis_editado", "resolucion_editado"]
    for clave in claves:
        if not datos.get(clave):
            # Intentar extraer campo cerrado
            patron_cerrado = rf'"{clave}"\s*:\s*"(.*?)(?<!\\)"'
            match = re.search(patron_cerrado, raw_text, re.DOTALL)
            if match:
                val = match.group(1).replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').strip()
                datos[clave] = val
            else:
                # Si quedó cortado a mitad del texto (sin comilla final)
                patron_abierto = rf'"{clave}"\s*:\s*"(.*)'
                match_open = re.search(patron_abierto, raw_text, re.DOTALL)
                if match_open:
                    val = match_open.group(1).strip()
                    val = re.sub(r'["}\s]+$', '', val)
                    val = val.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').strip()
                    datos[clave] = val

    rep = datos.get("reporte_editado") or reporte_orig
    ana = datos.get("analisis_editado") or analisis_orig
    res = datos.get("resolucion_editado") or resolucion_orig
    
    exito = bool(datos.get("reporte_editado") or datos.get("analisis_editado") or datos.get("resolucion_editado"))
    return rep, ana, res, exito

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

IMPORTANTE: Responde ÚNICAMENTE con un objeto JSON válido cerrado correctamente. El JSON debe tener exactamente estas claves:
"reporte_editado", "analisis_editado", "resolucion_editado".
No agregues comentarios ni comillas invertidas fuera del JSON.
"""

    model = GenerativeModel(modelo_seguro)
    ultimo_error = None

    for intento in range(3):
        try:
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 8192, "response_mime_type": "application/json"}
            )

            try:
                raw_text = response.text.replace("```json", "").replace("```", "").strip()
            except ValueError:
                ultimo_error = "La IA no pudo generar el texto (posible bloqueo por seguridad o formato)."
                if intento < 2:
                    time.sleep(2)
                    continue
                return reporte_cliente, analisis_caso, resolucion_caso, ultimo_error

            rep, ana, res, exito = _extraer_json_tolerante(raw_text, reporte_cliente, analisis_caso, resolucion_caso)
            if exito:
                return rep, ana, res, None
            
            ultimo_error = "La IA devolvió un formato no reconocido."
            if intento < 2:
                time.sleep(2)
                continue

        except Exception as e:
            if "modelo_gemini_cache" in st.session_state:
                del st.session_state["modelo_gemini_cache"]
            if "vertex_initialized" in st.session_state:
                del st.session_state["vertex_initialized"]
            ultimo_error = f"Error del mejorador: {e}"
            if intento < 2:
                time.sleep(2)
                continue

    return reporte_cliente, analisis_caso, resolucion_caso, ultimo_error or "No se pudo mejorar el texto después de varios intentos."