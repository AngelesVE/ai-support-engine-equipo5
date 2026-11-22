"""API de AI Support Engine.

POST /api/analyze  {message, mode: "traditional" | "generative"}
GET  /health

Errores: 422 entrada inválida, 503 motor no disponible, 502 salida del motor
fuera del contrato, 500 falla interna. Nunca se devuelve el detalle interno.
"""

import asyncio
import importlib
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.contract import AnalyzeRequest, AnalyzeResponse

log = logging.getLogger("app.main")

app = FastAPI(title="AI Support Engine", version="1.0.0")

MODULOS = {
    "traditional": "app.engines.traditional",
    "generative": "app.engines.generative",
}

# mode -> función analyze(message) -> dict. Se llena al arrancar; un motor que
# todavía no existe (o no importa) queda fuera y la API responde 503 para él.
MOTORES: dict = {}


def cargar_motores() -> None:
    for mode, ruta in MODULOS.items():
        try:
            MOTORES[mode] = importlib.import_module(ruta).analyze
        except Exception as exc:  # ImportError, AttributeError, fallas al importar
            log.warning("Motor %s no disponible (%s)", mode, type(exc).__name__)


cargar_motores()


def _error(status: int, mensaje: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": mensaje})


@app.exception_handler(RequestValidationError)
async def entrada_invalida(request: Request, exc: RequestValidationError):
    campos = sorted({".".join(str(p) for p in e["loc"][1:]) or "cuerpo" for e in exc.errors()})
    return _error(
        422,
        "Entrada inválida en: " + ", ".join(campos)
        + ". Se requiere message (texto no vacío) y mode ('traditional' o 'generative').",
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "motores": sorted(MOTORES)}


def _es_respuesta_de_error(mode: str, resultado: dict) -> bool:
    """El motor generativo no lanza excepción si Ollama falla: devuelve una
    respuesta de error fija. Se detecta para contestar 503 en vez de 200."""
    try:
        modulo = importlib.import_module(MODULOS[mode])
    except ImportError:
        return False  # motor sustituido (p. ej. en pruebas): no hay respuesta fija
    fabrica = getattr(modulo, "respuesta_error", None)
    return callable(fabrica) and resultado == fabrica()


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest):
    motor = MOTORES.get(payload.mode)
    if motor is None:
        return _error(503, f"El motor '{payload.mode}' no está disponible por ahora.")

    try:
        resultado = await asyncio.to_thread(motor, payload.message)
    except ValueError:
        return _error(422, "El motor rechazó el mensaje por no ser válido.")
    except (ConnectionError, TimeoutError):
        return _error(503, f"El motor '{payload.mode}' no responde.")
    except Exception as exc:
        log.error("Falla en el motor %s (%s)", payload.mode, type(exc).__name__)
        return _error(500, "Error interno al analizar la solicitud.")

    if _es_respuesta_de_error(payload.mode, resultado):
        return _error(503, f"El motor '{payload.mode}' no pudo analizar la solicitud (¿proveedor caído?).")

    try:
        validado = AnalyzeResponse(**resultado)
        if validado.mode != payload.mode:
            raise ValueError("modo distinto al solicitado")
    except (ValidationError, TypeError, ValueError):
        log.error("El motor %s devolvió una salida fuera del contrato", payload.mode)
        return _error(502, "El motor devolvió una respuesta fuera del contrato.")
    return validado
