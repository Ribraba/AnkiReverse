import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { turso } from "@/lib/turso";

export async function GET(req: Request) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { searchParams } = new URL(req.url);
  const limit = Math.min(Number(searchParams.get("limit") ?? 50), 200);
  const decksParam = searchParams.get("decks");
  const aheadDays = Number(searchParams.get("ahead") ?? 0);
  const deckFilter = decksParam ? decksParam.split(",").map((d) => d.trim()).filter(Boolean) : null;

  const now = Math.floor(Date.now() / 1000);
  const today = await getToday();

  const whereDecks = deckFilter && deckFilter.length > 0
    ? `AND deck IN (${deckFilter.map(() => "?").join(",")})`
    : "";

  let sql: string;
  let args: (number | string)[];

  if (aheadDays > 0) {
    sql = `SELECT * FROM cards
           WHERE queue=2 AND due > ? AND due <= ?
           ${whereDecks}
           ORDER BY due ASC LIMIT ?`;
    args = deckFilter && deckFilter.length > 0
      ? [today, today + aheadDays, ...deckFilter, limit]
      : [today, today + aheadDays, limit];

    const result = await turso.execute({ sql, args });
    return NextResponse.json(result.rows.map(mapCard));
  }

  // Mode normal : cartes dues — on récupère les non-nouvelles d'abord
  const reviewSql = `SELECT * FROM cards
     WHERE (queue IN (1,3) AND due <= ?) OR (queue=2 AND due <= ?)
     ${whereDecks}
     ORDER BY due ASC LIMIT ?`;
  const reviewArgs: (number | string)[] = deckFilter?.length
    ? [now, today, ...deckFilter, limit]
    : [now, today, limit];

  const reviewResult = await turso.execute({ sql: reviewSql, args: reviewArgs });
  const reviewCards = reviewResult.rows.map(mapCard);

  // Nouvelles cartes : respecter la limite par deck configurée dans Anki
  const newLimits = await getNewPerDayLimits();
  const newCards: ReturnType<typeof mapCard>[] = [];
  const newCountByDeck: Record<string, number> = {};

  const newSql = `SELECT * FROM cards
     WHERE queue=0
     ${whereDecks}
     ORDER BY due ASC LIMIT ?`;
  const newArgs: (number | string)[] = deckFilter?.length
    ? [...deckFilter, limit]
    : [limit];

  const newResult = await turso.execute({ sql: newSql, args: newArgs });
  for (const row of newResult.rows) {
    const card = mapCard(row);
    const deck = String(card.deck);
    const seen = newCountByDeck[deck] ?? 0;
    const maxNew = newLimits[deck] ?? 20;
    if (seen < maxNew) {
      newCards.push(card);
      newCountByDeck[deck] = seen + 1;
    }
  }

  // Mélanger : alterner révisions et nouvelles pour un meilleur flow
  const all = [...reviewCards];
  let ni = 0;
  const step = Math.max(1, Math.floor(reviewCards.length / (newCards.length + 1)));
  for (let i = 0; i < newCards.length; i++) {
    all.splice(Math.min((i + 1) * step + i, all.length), 0, newCards[ni++]);
  }

  return NextResponse.json(all.slice(0, limit));
}

function mapCard(row: Record<string, unknown>) {
  return {
    id: Number(row.id),
    deck: row.deck,
    model: row.model,
    fields: JSON.parse(String(row.fields)),
    question_template: row.q_template,
    answer_template: row.a_template,
    css: row.css ?? "",
    tags: String(row.tags ?? "").trim().split(" ").filter(Boolean),
    type: Number(row.type),
    queue: Number(row.queue),
    interval: Number(row.interval),
    factor: Number(row.factor),
    due: Number(row.due),
    reps: Number(row.reps),
    lapses: Number(row.lapses),
  };
}

async function getToday(): Promise<number> {
  const r = await turso.execute("SELECT value FROM sync_meta WHERE key='today_offset'");
  return r.rows[0] ? Number(r.rows[0].value) : Math.floor(Date.now() / 86400000);
}

async function getNewPerDayLimits(): Promise<Record<string, number>> {
  try {
    const r = await turso.execute(
      "SELECT key, value FROM sync_meta WHERE key LIKE 'new_per_day::%'"
    );
    const limits: Record<string, number> = {};
    for (const row of r.rows) {
      const deck = String(row.key).replace("new_per_day::", "");
      limits[deck] = Number(row.value);
    }
    return limits;
  } catch {
    return {};
  }
}
