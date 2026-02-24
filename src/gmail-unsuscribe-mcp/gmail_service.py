import re
from dataclasses import dataclass, field
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .gmail_auth import get_gmail_service


@dataclass
class Subscription:
    """Representa una suscripción detectada en un correo electrónico."""
    sender_email: str
    sender_name: str
    subject_examples: list[str] = field(default_factory=list)
    message_ids: list[str] = field(default_factory=list)
    unsubscribe_links: list[str] = field(default_factory=list)
    unsubscribe_mailto: list[str] = field(default_factory=list)
    email_count: int = 0


def _parse_unsubscribe_header(header_value: str) -> tuple[list[str], list[str]]:
    """
    Parsea la cabecera List-Unsubscribe y extrae links HTTP y mailto.
    """
    links: list[str] = []
    mailtos: list[str] = []

    matches = re.findall(r"<([^>]+)>", header_value)
    for match in matches:
        if match.startswith(("http://", "https://")):
            links.append(match)
        elif match.startswith("mailto:"):
            mailtos.append(match)

    return links, mailtos


def _extract_sender_info(headers: list[dict]) -> tuple[str, str]:
    """
    Extrae nombre y email del header From.
    """
    from_header = ""

    for header in headers:
        if header["name"].lower() == "from":
            from_header = header["value"]
            break

    match = re.match(r"^(.+?)\s*<(.+?)>$", from_header)
    if match:
        name = match.group(1).strip().strip('"')
        address = match.group(2).strip()
        return name, address

    return from_header.strip(), from_header.strip()


def _get_header_value(headers: list[dict], header_name: str) -> Optional[str]:
    """
    Devuelve el valor de una cabecera específica (case-insensitive).
    """
    for header in headers:
        if header["name"].lower() == header_name.lower():
            return header["value"]
    return None


def list_subscriptions(max_results: int = 100) -> list[Subscription]:
    """
    Busca emails con cabecera List-Unsubscribe en promociones/updates y agrupa por remitente.
    """
    service = get_gmail_service()
    user_id = "me"
    query = "category:promotions OR category:updates"

    subscriptions: dict[str, Subscription] = {}
    processed = 0
    next_page_token = None

    while processed < max_results:
        batch_size = min(100, max_results - processed)

        response = service.users().messages().list(
            userId=user_id,
            q=query,
            maxResults=batch_size,
            pageToken=next_page_token,
        ).execute()

        messages = response.get("messages", [])
        if not messages:
            break

        for msg in messages:
            msg_id = msg["id"]

            msg_meta = service.users().messages().get(
                userId=user_id,
                id=msg_id,
                format="metadata",
                metadataHeaders=["From", "Subject", "List-Unsubscribe"],
            ).execute()

            headers = msg_meta["payload"].get("headers", [])

            list_unsub = _get_header_value(headers, "List-Unsubscribe")
            if not list_unsub:
                continue

            from_name, from_email = _extract_sender_info(headers)
            subject = _get_header_value(headers, "Subject") or ""

            http_links, mailto_links = _parse_unsubscribe_header(list_unsub)

            key = from_email.lower()
            if key not in subscriptions:
                subscriptions[key] = Subscription(
                    sender_email=from_email,
                    sender_name=from_name,
                )

            sub = subscriptions[key]
            sub.subject_examples.append(subject)
            sub.message_ids.append(msg_id)
            sub.unsubscribe_links.extend(http_links)
            sub.unsubscribe_mailto.extend(mailto_links)
            sub.email_count += 1

            processed += 1
            if processed >= max_results:
                break

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return sorted(subscriptions.values(), key=lambda s: s.email_count, reverse=True)


async def unsubscribe_http(url: str) -> bool:
    """
    Visita una URL de desuscripción y detecta confirmación buscando keywords.
    """
    keywords = [
        "unsubscribed",
        "removed",
        "successfully unsubscribed",
        "you have been unsubscribed",
        "has been removed",
        "opted out",
    ]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        )
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url, headers=headers)

            soup = BeautifulSoup(resp.text, "html.parser")
            visible_text = soup.get_text(separator=" ").lower()
            raw_text = resp.text.lower()

            return any(kw in visible_text or kw in raw_text for kw in keywords)

    except Exception:
        return False


def search_emails(query: str, max_results: int = 50) -> list[dict]:
    """
    Busca emails usando query Gmail y devuelve metadatos.
    """
    service = get_gmail_service()
    user_id = "me"

    results = []
    processed = 0
    next_page_token = None

    while processed < max_results:
        batch_size = min(100, max_results - processed)

        response = service.users().messages().list(
            userId=user_id,
            q=query,
            maxResults=batch_size,
            pageToken=next_page_token,
        ).execute()

        messages = response.get("messages", [])
        if not messages:
            break

        for msg in messages:
            msg_id = msg["id"]

            msg_meta = service.users().messages().get(
                userId=user_id,
                id=msg_id,
                format="metadata",
                metadataHeaders=["From", "Subject", "Date", "List-Unsubscribe"],
            ).execute()

            headers = msg_meta["payload"].get("headers", [])

            from_name, from_email = _extract_sender_info(headers)
            subject = _get_header_value(headers, "Subject") or ""
            date = _get_header_value(headers, "Date") or ""
            has_unsubscribe = _get_header_value(headers, "List-Unsubscribe") is not None

            results.append(
                {
                    "id": msg_id,
                    "from_name": from_name,
                    "from_email": from_email,
                    "subject": subject,
                    "date": date,
                    "has_unsubscribe": has_unsubscribe,
                }
            )

            processed += 1
            if processed >= max_results:
                break

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return results