import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { turso } from "@/lib/turso";

export async function GET(req: Request) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { searchParams } = new URL(req.url);
  const limit = Math.min(Number(searchParams.get("limit") ?? 20), 200);
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
    // Mode révisions supplémentaires : cartes dues dans les prochains jours
    sql = `SELECT * FROM cards
           WHERE queue=2 AND due > ? AND due <= ?
           ${whereDecks}
           ORDER BY due ASC LIMIT ?`;
    args = deckFilter && deckFilter.length > 0
      ? [today, today + aheadDays, ...deckFilter, limit]
      : [today, today + aheadDays, limit];
  } else {
    // Mode normal : cartes dues aujourd'hui
    sql = `SELECT * FROM cards
           WHERE ((queue=0) OR (queue IN (1,3) AND due <= ?) OR (queue=2 AND due <= ?))
           ${whereDecks}
           ORDER BY due ASC LIMIT ?`;
    args = deckFilter && deckFilter.length > 0
      ? [now, today, ...deckFilter, limit]
      : [now, today, limit];
  }

  const result = await turso.execute({ sql, args });

  const cards = result.rows.map((row) => ({
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
  }));

  return NextResponse.json(cards);
}

async function getToday(): Promise<number> {
  const r = await turso.execute("SELECT value FROM sync_meta WHERE key='today_offset'");
  return r.rows[0] ? Number(r.rows[0].value) : Math.floor(Date.now() / 86400000);
}
