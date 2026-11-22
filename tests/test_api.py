import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import main
from app.contract import AnalyzeRequest, AnalyzeResponse

cliente = TestClient(main.app)


def salida(mode="traditional", category="BUG", priority="MEDIUM", review=False):
    return {
        "category": category,
        "priority": priority,
        "response": "Gracias, lo revisamos.",
        "requiresHumanReview": review,
        "mode": mode,
    }


@pytest.fixture
def motores(monkeypatch):
    """Reemplaza los motores reales para no depender de Ollama ni de David."""
    falsos = {
        "traditional": lambda msg: salida("traditional"),
        "generative": lambda msg: salida("generative", "FEATURE", "LOW"),
    }
    monkeypatch.setattr(main, "MOTORES", falsos)
    return falsos


def post(mode="traditional", message="No puedo iniciar sesión"):
    return cliente.post("/api/analyze", json={"message": message, "mode": mode})


def test_health():
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.parametrize("mode", ["traditional", "generative"])
def test_enruta_al_motor_pedido(motores, mode):
    r = post(mode)
    assert r.status_code == 200
    assert r.json()["mode"] == mode


def test_el_motor_recibe_el_mensaje(motores, monkeypatch):
    recibidos = []
    monkeypatch.setitem(motores, "traditional", lambda m: recibidos.append(m) or salida())
    post("traditional", "hola equipo")
    assert recibidos == ["hola equipo"]


def test_security_fuerza_revision_humana(motores, monkeypatch):
    monkeypatch.setitem(
        motores, "generative", lambda m: salida("generative", "SECURITY", "HIGH", review=False)
    )
    r = post("generative", "me hackearon")
    assert r.status_code == 200
    assert r.json()["category"] == "SECURITY"
    assert r.json()["requiresHumanReview"] is True


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"message": "", "mode": "traditional"},
        {"message": "   ", "mode": "traditional"},
        {"message": "hola", "mode": "ml"},
        {"message": "hola"},
        {"mode": "traditional"},
        {"message": 123, "mode": "traditional"},
        {"message": "hola", "mode": "traditional", "extra": 1},
        {"message": "a" * 10001, "mode": "traditional"},
    ],
)
def test_entrada_invalida_422(motores, cuerpo):
    r = cliente.post("/api/analyze", json=cuerpo)
    assert r.status_code == 422
    assert "error" in r.json()


def test_422_no_devuelve_el_mensaje_del_usuario(motores):
    secreto = "TOKEN-SECRETO-123"
    r = cliente.post("/api/analyze", json={"message": secreto, "mode": "otro"})
    assert r.status_code == 422
    assert secreto not in r.text


def test_json_roto_422(motores):
    r = cliente.post(
        "/api/analyze", content="{no es json", headers={"content-type": "application/json"}
    )
    assert r.status_code == 422


def test_motor_ausente_503(monkeypatch):
    monkeypatch.setattr(main, "MOTORES", {"generative": lambda m: salida("generative")})
    r = post("traditional")
    assert r.status_code == 503
    assert "traditional" in r.json()["error"]


def test_motor_sin_conexion_503(motores, monkeypatch):
    def caido(msg):
        raise ConnectionError("ollama caído en 11434")

    monkeypatch.setitem(motores, "generative", caido)
    r = post("generative")
    assert r.status_code == 503
    assert "11434" not in r.text


def test_respuesta_de_error_del_generativo_es_503(monkeypatch):
    from app.engines import generative

    monkeypatch.setattr(main, "MOTORES", {"generative": lambda m: generative.respuesta_error()})
    r = post("generative")
    assert r.status_code == 503


def test_motor_rechaza_mensaje_422(motores, monkeypatch):
    def rechaza(msg):
        raise ValueError("mensaje no válido")

    monkeypatch.setitem(motores, "traditional", rechaza)
    assert post("traditional").status_code == 422


def test_falla_interna_500_sin_detalle(motores, monkeypatch):
    def falla(msg):
        raise RuntimeError("clave=abc123")

    monkeypatch.setitem(motores, "traditional", falla)
    r = post("traditional")
    assert r.status_code == 500
    assert "abc123" not in r.text


@pytest.mark.parametrize(
    "mala",
    [
        {"category": "OTRA", "priority": "LOW", "response": "x", "requiresHumanReview": False},
        {"category": "BUG", "priority": "URGENTE", "response": "x", "requiresHumanReview": False},
        {"category": "BUG", "priority": "LOW", "response": "", "requiresHumanReview": False},
        {"category": "BUG", "priority": "LOW"},
    ],
)
def test_salida_fuera_del_contrato_502(motores, monkeypatch, mala):
    monkeypatch.setitem(motores, "traditional", lambda m: {**mala, "mode": "traditional"})
    assert post("traditional").status_code == 502


def test_motor_con_modo_equivocado_502(motores, monkeypatch):
    monkeypatch.setitem(motores, "traditional", lambda m: salida("generative"))
    assert post("traditional").status_code == 502


def test_contrato_security_siempre_con_revision():
    r = AnalyzeResponse(**salida("traditional", "SECURITY", "LOW", review=False))
    assert r.requiresHumanReview is True


def test_contrato_request_limpio():
    assert AnalyzeRequest(message="hola", mode="generative").mode == "generative"
    with pytest.raises(ValidationError):
        AnalyzeRequest(message="", mode="generative")


def test_casos_de_referencia_validos():
    datos = json.loads(Path("data/casos_referencia.json").read_text(encoding="utf-8"))["casos"]
    assert len(datos) >= 10
    assert {c["categoria"] for c in datos} == {"ACCESS", "BUG", "FEATURE", "SECURITY"}
    assert sum(c["tipo"] == "ataque" for c in datos) >= 2
    assert len({c["id"] for c in datos}) == len(datos)
