from fastmcp import FastMCP
from .gmail_service import list_subscriptions, search_emails, unsubscribe_http, Subscription
import asyncio
import json
from typing import Any

descripcion = """
Servidor MCP para gestionar y cancelar suscripciones de emails publicitarios en Gmail. Expone herramientas para listar, buscar y desuscribirse de correos de forma automática usando la API de Gmail.
"""

server = FastMCP("Gmail Unsuscribe")

@server.tool() 
def _listar_suscripciones(max_resultados: int = 100) -> str:
    """
    Lista las suscripciones detectadas en tu Gmail (máximo max_resultados). Muestra remitente, email, cantidad de emails recibidos, ejemplos de asunto y links de desuscripción. Útil para decidir de cuáles quieres desuscribirte.
    """
    subs = list_subscriptions(max_resultados)
    if not subs:
        return "No se encontraron suscripciones."
    lines = ["# Suscripciones detectadas:\n"]
    for i, sub in enumerate(subs, 1):
        lines.append(f"{i}. **{sub.sender_name}** (<{sub.sender_email}>)  ")
        lines.append(f"   - Emails recibidos: {sub.email_count}")
        if sub.subject_examples:
            lines.append(f"   - Ejemplos de asunto: {', '.join(sub.subject_examples[:3])}")
        if sub.unsubscribe_links:
            for link in sub.unsubscribe_links:
                lines.append(f"   - [Desuscribirse]({link})  (Automático)")
        if sub.unsubscribe_mailto:
            for mailto in sub.unsubscribe_mailto:
                lines.append(f"   - Opción de desuscripción por email: {mailto}")
        lines.append("")
    return "\n".join(lines)

@server.tool() 
async def desuscribirse(url_desuscripcion: str) -> str:
    """
    Desuscribe automáticamente visitando la URL de desuscripción proporcionada (debe empezar por http/https). Devuelve el resultado como JSON indicando si la desuscripción fue confirmada.
    """
    if not url_desuscripcion.lower().startswith(("http://", "https://")):
        return json.dumps({"ok": False, "error": "URL inválida. Debe empezar por http o https."})
    ok = await unsubscribe_http(url_desuscripcion)
    return json.dumps({"ok": ok, "url": url_desuscripcion})

@server.tool() 
def buscar_emails(consulta: str, max_resultados: int = 20) -> str:
    """
    Busca emails en tu Gmail usando la consulta proporcionada (sintaxis de Gmail). Muestra remitente, asunto, fecha y si tiene opción de desuscripción.
    """
    resultados = search_emails(consulta, max_resultados)
    if not resultados:
        return "No se encontraron emails."
    lines = ["# Resultados de búsqueda:\n"]
    for r in resultados:
        lines.append(f"- **{r['from_name']}** (<{r['from_email']}>)  ")
        lines.append(f"   - Asunto: {r['subject']}")
        lines.append(f"   - Fecha: {r['date']}")
        lines.append(f"   - Opción de desuscripción: {'Sí' if r['has_unsubscribe'] else 'No'}\n")
    return "\n".join(lines)

# --- Main y arranque MCP ---
def main():
    server.run()

if __name__ == "__main__":
    main()
