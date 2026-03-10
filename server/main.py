"""
API principale - sert le PWA et gère les notifications.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.anki_db import find_collection, get_due_cards, get_due_counts, get_decks
from api.push import save_subscription, send_notification_to_all

ANKI_DATA_PATH = os.getenv("ANKI_DATA_PATH", "/anki_data")
scheduler = AsyncIOScheduler()


async def send_daily_notification():
    """Cron job : envoie la notification quotidienne des cartes dues."""
    db_path = find_collection(ANKI_DATA_PATH)
    if not db_path:
        print("Collection Anki introuvable")
        return

    counts = await get_due_counts(db_path)
    total = counts["total"]

    if total == 0:
        return

    parts = []
    if counts["new"]:
        parts.append(f"{counts['new']} nouvelles")
    if counts["review"]:
        parts.append(f"{counts['review']} révisions")
    if counts["learning"]:
        parts.append(f"{counts['learning']} en cours")

    body = " · ".join(parts)
    await send_notification_to_all(
        title=f"📚 {total} carte{'s' if total > 1 else ''} à réviser",
        body=body,
        data={"url": "/review"},
    )
    print(f"Notification envoyée : {total} cartes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Notification chaque matin à 9h
    scheduler.add_job(send_daily_notification, "cron", hour=9, minute=0)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="AnkiReverse API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En prod : mettre le domaine exact du PWA
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db_path() -> Path:
    db_path = find_collection(ANKI_DATA_PATH)
    if not db_path:
        raise HTTPException(status_code=503, detail="Collection Anki introuvable. Avez-vous synchronisé Anki Desktop ?")
    return db_path


# --- Endpoints cartes ---

@app.get("/api/counts")
async def due_counts():
    """Nombre de cartes dues par catégorie."""
    return await get_due_counts(get_db_path())


@app.get("/api/cards")
async def due_cards(limit: int = 20):
    """Liste des cartes dues (pour la session de révision)."""
    return await get_due_cards(get_db_path(), limit=limit)


@app.get("/api/decks")
async def decks():
    """Liste des decks."""
    return await get_decks(get_db_path())


# --- Endpoints notifications ---

class PushSubscription(BaseModel):
    endpoint: str
    keys: dict
    expirationTime: float | None = None


@app.post("/api/push/subscribe")
async def subscribe(subscription: PushSubscription):
    """Enregistre une subscription Web Push."""
    save_subscription(subscription.model_dump())
    return {"ok": True}


@app.post("/api/push/test")
async def test_notification():
    """Envoie une notification de test."""
    result = await send_notification_to_all(
        title="Test AnkiReverse",
        body="Les notifications fonctionnent !",
    )
    return result


@app.get("/api/health")
async def health():
    db_path = find_collection(ANKI_DATA_PATH)
    return {
        "status": "ok",
        "collection_found": db_path is not None,
        "collection_path": str(db_path) if db_path else None,
    }
