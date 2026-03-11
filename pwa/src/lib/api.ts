// Les routes API sont intégrées dans Next.js — URLs relatives, pas de serveur externe
export interface DueCounts {
  new: number;
  learning: number;
  review: number;
  total: number;
}

export interface AnkiCard {
  id: number;
  deck: string;
  model: string;
  fields: Record<string, string>;
  question_template: string;
  answer_template: string;
  css: string;
  tags: string[];
  type: number;
  queue: number;
  interval: number;
  factor: number;
  due: number;
  reps: number;
  lapses: number;
}

export async function getDueCounts(params = ""): Promise<DueCounts> {
  const res = await fetch(`/api/counts${params}`);
  if (!res.ok) throw new Error("Impossible de récupérer les compteurs");
  return res.json();
}

export async function getDueCards(limit = 20, params = ""): Promise<AnkiCard[]> {
  const sep = params ? "&" : "?";
  const res = await fetch(`/api/cards${params}${sep}limit=${limit}`);
  if (!res.ok) throw new Error("Impossible de récupérer les cartes");
  return res.json();
}

export async function getExtraCards(aheadDays = 7, limit = 50, params = ""): Promise<AnkiCard[]> {
  const sep = params ? "&" : "?";
  const res = await fetch(`/api/cards${params}${sep}ahead=${aheadDays}&limit=${limit}`);
  if (!res.ok) throw new Error("Impossible de récupérer les cartes supplémentaires");
  return res.json();
}

export async function submitReview(card_id: number, rating: number): Promise<void> {
  const res = await fetch("/api/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ card_id, rating }),
  });
  if (!res.ok) throw new Error("Erreur lors de la soumission de la révision");
}

export async function subscribeToPush(subscription: PushSubscription): Promise<void> {
  const res = await fetch("/api/push/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(subscription.toJSON()),
  });
  if (!res.ok) throw new Error("Erreur lors de l'abonnement aux notifications");
}
