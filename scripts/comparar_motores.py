"""Compara los motores con los casos de data/casos_referencia.json.

Calcula % de aciertos de categoría y prioridad y el tiempo promedio por motor,
y guarda la tabla en evidence/comparativa.md y evidence/comparativa.json.
Si un motor no está disponible lo reporta y sigue con el otro.

Uso:
  python scripts/comparar_motores.py                 # llama a los motores directo
  python scripts/comparar_motores.py --api http://127.0.0.1:8000
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.contract import AnalyzeResponse  # noqa: E402

MODOS = ("traditional", "generative")


def pct(parte: int, total: int) -> float:
    return round(100 * parte / total, 1) if total else 0.0


def llamar_directo(modo: str, mensaje: str) -> dict:
    from app import main

    motor = main.MOTORES.get(modo)
    if motor is None:
        raise RuntimeError("motor no disponible (no se encontró app/engines/%s.py)" % modo)
    resultado = motor(mensaje)
    if main._es_respuesta_de_error(modo, resultado):
        raise RuntimeError("el motor devolvió su respuesta de error (¿Ollama caído?)")
    return resultado


def llamar_api(base: str):
    def llamar(modo: str, mensaje: str) -> dict:
        r = httpx.post(f"{base}/api/analyze", json={"message": mensaje, "mode": modo}, timeout=120)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
        return r.json()
    return llamar


def evaluar(caso: dict, llamar, modo: str) -> dict:
    t0 = time.perf_counter()
    try:
        crudo = llamar(modo, caso["mensaje"])
        segundos = round(time.perf_counter() - t0, 2)
        datos = AnalyzeResponse(**crudo)
    except Exception as exc:
        return {"error": str(exc), "segundos": round(time.perf_counter() - t0, 2)}
    return {
        "categoria": datos.category,
        "prioridad": datos.priority,
        "revision_humana": datos.requiresHumanReview,
        "respuesta": datos.response,
        "segundos": segundos,
        "cat_ok": datos.category == caso["categoria"],
        "prio_ok": datos.priority == caso["prioridad"],
    }


def resumir(filas: list, modo: str) -> dict:
    ok = [f[modo] for f in filas if "error" not in f[modo]]
    if not ok:
        errores = {f[modo]["error"] for f in filas}
        return {"disponible": False, "motivo": sorted(errores)[0]}
    n = len(filas)
    return {
        "disponible": True,
        "casos": n,
        "respondidos": len(ok),
        "pct_categoria": pct(sum(x["cat_ok"] for x in ok), n),
        "pct_prioridad": pct(sum(x["prio_ok"] for x in ok), n),
        "pct_ambas": pct(sum(x["cat_ok"] and x["prio_ok"] for x in ok), n),
        "segundos_promedio": round(sum(x["segundos"] for x in ok) / len(ok), 2),
    }


def celda(r: dict) -> str:
    if "error" in r:
        return "sin respuesta"
    marca = "✅" if r["cat_ok"] and r["prio_ok"] else "❌"
    return f"{r['categoria']} / {r['prioridad']} {marca}"


def escribir_md(filas: list, resumen: dict, destino: Path, origen: str) -> None:
    md = [
        "# Comparativa de motores", "",
        f"Origen de las llamadas: {origen}. La clasificación esperada está en "
        "`data/casos_referencia.json` y se definió antes de correr los motores. "
        "En la tabla, ✅ = categoría y prioridad iguales a la esperada.", "",
        "| # | Tipo | Mensaje | Esperado | Tradicional | Generativo |",
        "|---|---|---|---|---|---|",
    ]
    for f in filas:
        c = f["caso"]
        msg = c["mensaje"].replace("|", "/")
        msg = msg if len(msg) <= 80 else msg[:77] + "..."
        md.append(f"| {c['id']} | {c['tipo']} | {msg} | {c['categoria']} / {c['prioridad']} | "
                  f"{celda(f['traditional'])} | {celda(f['generative'])} |")
    md += ["", "## Resultados por motor", "", "| Métrica | Tradicional | Generativo |", "|---|---|---|"]

    def fila(nombre, clave, sufijo=""):
        vals = [f"{resumen[m][clave]}{sufijo}" if resumen[m]["disponible"] else "no disponible" for m in MODOS]
        md.append(f"| {nombre} | {vals[0]} | {vals[1]} |")

    fila("Aciertos de categoría", "pct_categoria", " %")
    fila("Aciertos de prioridad", "pct_prioridad", " %")
    fila("Aciertos de ambas", "pct_ambas", " %")
    fila("Tiempo promedio por solicitud", "segundos_promedio", " s")
    for m in MODOS:
        if not resumen[m]["disponible"]:
            md += ["", f"**Motor {m} no disponible:** {resumen[m]['motivo']}"]
    destino.write_text("\n".join(md) + "\n", encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", help="URL base de la API en vez de llamar a los motores directo")
    parser.add_argument("--casos", default=str(ROOT / "data" / "casos_referencia.json"))
    parser.add_argument("--salida", default=str(ROOT / "evidence"))
    args = parser.parse_args()

    casos = json.loads(Path(args.casos).read_text(encoding="utf-8"))["casos"]
    llamar = llamar_api(args.api.rstrip("/")) if args.api else llamar_directo
    origen = f"API {args.api}" if args.api else "motores directos (app.main.MOTORES)"

    filas = []
    for caso in casos:
        fila = {"caso": caso}
        for modo in MODOS:
            fila[modo] = evaluar(caso, llamar, modo)
        filas.append(fila)
        print(f"{caso['id']:2} {caso['categoria']}/{caso['prioridad']:8} "
              f"trad={celda(fila['traditional'])}  gen={celda(fila['generative'])}")

    resumen = {m: resumir(filas, m) for m in MODOS}
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "comparativa.json").write_text(
        json.dumps({"origen": origen, "resumen": resumen, "casos": filas}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    escribir_md(filas, resumen, salida / "comparativa.md", origen)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
