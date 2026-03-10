"""
Gestion des Web Push notifications (VAPID).
Fonctionne avec iOS 16.4+ (Safari Web Push).
"""
import json
import os
from pathlib import Path
from pywebpush import webpush, WebPushException

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_EMAIL = os.getenv("VAPID_EMAIL", "mailto:admin@example.com")

# Stockage des subscriptions (en prod : utiliser une vraie DB)
SUBSCRIPTIONS_FILE = Path("/data/subscriptions.json")


def load_subscriptions() -> list[dict]:
    if not SUBSCRIPTIONS_FILE.exists():
        return []
    with open(SUBSCRIPTIONS_FILE) as f:
        return json.load(f)


def save_subscription(subscription: dict) -> None:
    subs = load_subscriptions()
    # Évite les doublons par endpoint
    subs = [s for s in subs if s.get("endpoint") != subscription.get("endpoint")]
    subs.append(subscription)
    SUBSCRIPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SUBSCRIPTIONS_FILE, "w") as f:
        json.dump(subs, f)


def remove_subscription(endpoint: str) -> None:
    subs = load_subscriptions()
    subs = [s for s in subs if s.get("endpoint") != endpoint]
    with open(SUBSCRIPTIONS_FILE, "w") as f:
        json.dump(subs, f)


async def send_notification_to_all(title: str, body: str, data: dict = None) -> dict:
    """Envoie une notification push à tous les abonnés."""
    subscriptions = load_subscriptions()
    payload = json.dumps({"title": title, "body": body, "data": data or {}})

    results = {"sent": 0, "failed": 0, "removed": 0}
    to_remove = []

    for sub in subscriptions:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_EMAIL},
            )
            results["sent"] += 1
        except WebPushException as e:
            if e.response and e.response.status_code in (404, 410):
                # Subscription expirée
                to_remove.append(sub["endpoint"])
                results["removed"] += 1
            else:
                results["failed"] += 1

    for endpoint in to_remove:
        remove_subscription(endpoint)

    return results
