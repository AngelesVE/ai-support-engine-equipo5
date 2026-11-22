# Prueba real de POST /api/analyze (uvicorn + Ollama qwen2.5:3b)

Fecha: 2026-11-22 15:07. Servidor: `uvicorn app.main:app`.

## mode=generative

Entrada: `{"message": "Me gustaría que la aplicación tuviera modo oscuro", "mode": "generative"}`

HTTP 200 (20.1 s)

```json
{
  "category": "FEATURE",
  "priority": "MEDIUM",
  "response": "Gracias por tu sugerencia. Un modo oscuro es una funcionalidad que valoramos. ¿Podrías proporcionar más detalles sobre cómo te gustaría que fuera este modo?",
  "requiresHumanReview": false,
  "mode": "generative"
}
```

## mode=generative

Entrada: `{"message": "La aplicación se cierra sola al guardar el formulario de pedidos", "mode": "generative"}`

HTTP 200 (6.8 s)

```json
{
  "category": "ACCESS",
  "priority": "MEDIUM",
  "response": "El problema podría estar relacionado con la aplicación que se cierra al guardar el formulario de pedidos. Es posible que haya un problema con la conexión o con los datos que se guardan. Por favor, intenta guardar el formulario de nuevo.",
  "requiresHumanReview": false,
  "mode": "generative"
}
```

## mode=generative

Entrada: `{"message": "Detecté un acceso no autorizado a mi cuenta", "mode": "generative"}`

HTTP 200 (0.4 s)

```json
{
  "category": "SECURITY",
  "priority": "HIGH",
  "response": "Esta solicitud requiere revisión del equipo de seguridad. Por favor, utiliza los canales oficiales de soporte.",
  "requiresHumanReview": true,
  "mode": "generative"
}
```

## mode=generative

Entrada: `{"message": "No puedo entrar a mi cuenta, olvidé la contraseña", "mode": "generative"}`

HTTP 200 (6.9 s)

```json
{
  "category": "ACCESS",
  "priority": "HIGH",
  "response": "Gracias por contactarnos. Parece que olvidaste tu contraseña. Necesitaré que me proporciones tu correo electrónico para restablecer tu contraseña. Por favor, proporciona el correo electrónico que usaste al crear tu cuenta.",
  "requiresHumanReview": false,
  "mode": "generative"
}
```

## mode=traditional

Entrada: `{"message": "Hola", "mode": "traditional"}`

HTTP 503 (0.5 s)

```json
{
  "error": "El motor 'traditional' no está disponible por ahora."
}
```

## mode=generative

Entrada: `{"message": "", "mode": "generative"}`

HTTP 422 (0.3 s)

```json
{
  "error": "Entrada inválida en: message. Se requiere message (texto no vacío) y mode ('traditional' o 'generative')."
}
```

## GET /health

```json
{"status":"ok","motores":["generative"]}
```
