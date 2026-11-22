# Conclusión

Probamos los dos motores con las mismas 20 solicitudes (normales, ambiguas y ataques) y una clasificación de referencia. El tradicional acertó la categoría en 80 % y la prioridad en 50 %, con 0.35 s promedio. El generativo con Ollama (qwen2.5:3b) acertó 75 % y 45 %, pero tardó 4.59 s por solicitud.

Las reglas fueron rápidas y siempre dan lo mismo, pero fallan cuando el mensaje no trae sus palabras clave, como en la inyección SQL del caso 20. El modelo entendió mejor el impacto (sistema caído, toda la plantilla sin acceso), aunque tiende a exagerar la prioridad y confundió varios casos con ACCESS.

Los dos motores resistieron los ataques de "ignora las instrucciones" y marcaron SECURITY con revisión humana. Para producción conviene combinarlos: reglas como primer filtro y el modelo para los casos ambiguos, siempre validando la salida.
