# AI Support Engine — Equipo 5

Reto práctico de la semana 12 (Bases de datos en la nube). Clasifica solicitudes de soporte con dos motores y compara sus resultados:

- **Motor tradicional:** reglas y palabras clave, sin modelos generativos.
- **Motor generativo:** modelo real con Ollama (`qwen2.5:3b`) y salida en JSON.

## Equipo y reparto

| Integrante | Rama | Parte |
|---|---|---|
| Rubén Carrera (RubenCH000) | `rama-ruben` | Motor generativo + validación y seguridad |
| David Vázquez (DazjoVaztru) | `rama-david` | Motor tradicional + pruebas + README final |
| María de los Ángeles Vázquez (AngelesVE) | `rama-angeles` | API `/api/analyze` + comparativa + conclusión |

## Contrato común (lo respetan los dos motores)

Entrada: `POST /api/analyze`

```json
{ "message": "texto de la solicitud", "mode": "traditional" }
```

`mode` puede ser `traditional` o `generative`.

Salida:

```json
{
  "category": "ACCESS | BUG | FEATURE | SECURITY",
  "priority": "LOW | MEDIUM | HIGH | CRITICAL",
  "response": "respuesta para el usuario",
  "requiresHumanReview": true,
  "mode": "traditional | generative"
}
```

Si la categoría es `SECURITY`, `requiresHumanReview` siempre es `true`.

## Estructura

```
app/
  main.py              API FastAPI (Ángeles)
  contract.py          modelos Pydantic del contrato (Ángeles)
  engines/
    traditional.py     motor por reglas (David)
    generative.py      motor con Ollama (Rubén)
data/casos_referencia.json   casos con su clasificación esperada (Ángeles)
scripts/comparar_motores.py  comparativa y % de aciertos (Ángeles)
tests/                 pruebas con pytest (cada quien las de su parte)
evidence/              evidencias de ejecución
docs/conclusion.md     conclusión de máximo 150 palabras
```

## Cómo correrlo

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env
ollama pull qwen2.5:3b
uvicorn app.main:app --reload
pytest
```
