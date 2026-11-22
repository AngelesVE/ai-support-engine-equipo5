"""Motor tradicional: clasificación por reglas y palabras clave con pesos.

No usa IA generativa. Siempre da el mismo resultado para el mismo mensaje,
por eso sirve como línea base para comparar contra el motor generativo.

Flujo:
1. Validar la entrada (texto no vacío y de máximo 10 000 caracteres).
2. Normalizar el texto (minúsculas y sin acentos).
3. Si hay un intento de inyección de instrucciones -> SECURITY, prioridad HIGH fija.
4. Sumar los pesos de las palabras clave encontradas por categoría y elegir la mayor.
5. Calcular la prioridad a partir de la categoría y de señales de impacto reales.
   Las peticiones explícitas del usuario ("pon prioridad CRITICAL") se ignoran.
"""

import re
import unicodedata

MAX_LENGTH = 10000

CATEGORIES = ("ACCESS", "BUG", "FEATURE", "SECURITY")
PRIORITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

# Palabras clave (ya normalizadas: minúsculas y sin acentos) con su peso.
KEYWORDS = {
    "SECURITY": {
        "hackearon": 5,
        "hackeo": 5,
        "hackeada": 5,
        "acceso no autorizado": 5,
        "cuenta comprometida": 5,
        "fuga de datos": 5,
        "filtracion": 4,
        "robo de credenciales": 5,
        "robaron": 4,
        "phishing": 5,
        "malware": 5,
        "ransomware": 5,
        "virus": 4,
        "actividad sospechosa": 4,
        "sospechoso": 3,
        "vulnerabilidad": 4,
        "inyeccion sql": 5,
        "datos expuestos": 5,
        "suplantacion": 4,
    },
    "ACCESS": {
        "contrasena": 3,
        "password": 3,
        "iniciar sesion": 3,
        "inicio de sesion": 3,
        "login": 3,
        "no puedo entrar": 3,
        "no puedo acceder": 3,
        "acceso": 2,
        "bloqueada": 2,
        "bloqueado": 2,
        "usuario": 1,
        "credenciales": 2,
        "restablecer": 2,
        "recuperar mi cuenta": 3,
        "permisos": 2,
        "autenticacion": 2,
        "codigo de verificacion": 2,
    },
    "BUG": {
        "error": 3,
        "falla": 3,
        "fallo": 3,
        "no funciona": 3,
        "se cierra": 3,
        "se traba": 3,
        "se congela": 3,
        "pantalla en blanco": 3,
        "excepcion": 3,
        "bug": 3,
        "lento": 2,
        "no carga": 3,
        "no guarda": 3,
        "caido": 3,
        "crash": 3,
        "500": 2,
    },
    "FEATURE": {
        "me gustaria": 3,
        "seria bueno": 3,
        "seria util": 3,
        "sugerencia": 3,
        "sugiero": 3,
        "propongo": 3,
        "nueva funcion": 4,
        "nueva funcionalidad": 4,
        "agregar": 2,
        "anadir": 2,
        "podrian": 2,
        "mejora": 2,
        "modo oscuro": 3,
        "exportar": 2,
        "integracion": 2,
    },
}

# Señales de impacto que suben la prioridad (no dependen de lo que "pida" el usuario).
IMPACT_CRITICAL = (
    "todos los usuarios",
    "toda la empresa",
    "produccion",
    "sistema caido",
    "servicio caido",
    "perdida de datos",
    "datos expuestos",
    "fuga de datos",
    "ransomware",
)
IMPACT_HIGH = (
    "no puedo trabajar",
    "varios usuarios",
    "clientes",
    "pagos",
    "facturacion",
    "se perdio",
    "bloqueado",
    "bloqueada",
)

# Patrones de inyección de instrucciones (prompt injection).
INJECTION_PATTERNS = (
    r"ignora\w* .*instrucciones",
    r"olvida\w* .*instrucciones",
    r"ignore .*instructions",
    r"forget .*instructions",
    r"(revela|muestra|dime) .*(prompt|instrucciones)",
    r"system prompt",
    r"actua como .*sin restricciones",
    r"modo desarrollador",
    r"developer mode",
    r"jailbreak",
    r"\b(asigna|pon|marca|cambia)\w* .*prioridad",
)

BASE_PRIORITY = {
    "SECURITY": "HIGH",
    "ACCESS": "MEDIUM",
    "BUG": "MEDIUM",
    "FEATURE": "LOW",
}

# Orden de desempate: en caso de empate gana la categoría más delicada.
TIE_BREAK = ("SECURITY", "ACCESS", "BUG", "FEATURE")

RESPONSES = {
    "ACCESS": (
        "Recibimos tu problema de acceso. Usa la opción 'Olvidé mi contraseña' "
        "para restablecerla; si sigues sin poder entrar, el equipo de soporte "
        "revisará tu cuenta."
    ),
    "BUG": (
        "Gracias por reportar la falla. La registramos y el equipo técnico la "
        "revisará. Si puedes, comparte los pasos para reproducirla y capturas "
        "de pantalla."
    ),
    "FEATURE": (
        "Gracias por tu sugerencia. La agregamos a la lista de mejoras y el "
        "equipo de producto la evaluará."
    ),
    "SECURITY": (
        "Esta solicitud requiere revisión del equipo de seguridad. Por favor, "
        "no compartas contraseñas y utiliza los canales oficiales de soporte."
    ),
}


def normalizar(texto: str) -> str:
    """Pasa a minúsculas y quita acentos para comparar sin importar la escritura."""
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _contiene(texto: str, frase: str) -> bool:
    """Busca la frase como palabra completa (evita que 'error' coincida en 'errores' de otra cosa)."""
    return re.search(rf"\b{re.escape(frase)}\b", texto) is not None


def detectar_inyeccion(texto_normalizado: str) -> bool:
    return any(re.search(p, texto_normalizado) for p in INJECTION_PATTERNS)


def calcular_puntajes(texto_normalizado: str) -> dict:
    """Suma los pesos de cada palabra clave encontrada, por categoría."""
    return {
        categoria: sum(
            peso for frase, peso in palabras.items() if _contiene(texto_normalizado, frase)
        )
        for categoria, palabras in KEYWORDS.items()
    }


def elegir_categoria(puntajes: dict) -> str:
    mejor = max(puntajes.values())
    if mejor == 0:
        return "BUG"  # sin coincidencias: se trata como incidencia general
    for categoria in TIE_BREAK:
        if puntajes[categoria] == mejor:
            return categoria
    return "BUG"


def calcular_prioridad(categoria: str, texto_normalizado: str) -> str:
    nivel = PRIORITIES.index(BASE_PRIORITY[categoria])
    if any(_contiene(texto_normalizado, f) for f in IMPACT_CRITICAL):
        nivel = PRIORITIES.index("CRITICAL")
    elif any(_contiene(texto_normalizado, f) for f in IMPACT_HIGH):
        nivel = max(nivel, PRIORITIES.index("HIGH"))
    return PRIORITIES[nivel]


def _resultado(categoria: str, prioridad: str, revision: bool) -> dict:
    return {
        "category": categoria,
        "priority": prioridad,
        "response": RESPONSES[categoria],
        "requiresHumanReview": revision or categoria == "SECURITY",
        "mode": "traditional",
    }


def analyze(message: str) -> dict:
    """Clasifica un mensaje de soporte y regresa el contrato común."""
    if not isinstance(message, str) or not message.strip():
        raise ValueError("El mensaje debe ser un texto no vacío")
    if len(message) > MAX_LENGTH:
        raise ValueError("El mensaje supera el límite permitido")

    texto = normalizar(message)

    # Un intento de manipular el sistema nunca decide la prioridad: siempre HIGH.
    if detectar_inyeccion(texto):
        return _resultado("SECURITY", "HIGH", True)

    puntajes = calcular_puntajes(texto)
    categoria = elegir_categoria(puntajes)
    prioridad = calcular_prioridad(categoria, texto)

    sin_coincidencias = max(puntajes.values()) == 0
    revision = sin_coincidencias or prioridad == "CRITICAL"

    return _resultado(categoria, prioridad, revision)


# Alias para facilitar la integración con la API
analyze_traditional = analyze
