import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { turso } from "@/lib/turso";

export async function GET(req: Request) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { searchParams } = new URL(req.url);
  const limit = Math.min(Number(searchParams.get("limit") ?? 20), 100);
  const decksParam = searchParams.get("decks");
  const deckFilter = decksParam ? decksParam.split(",").map((d) => d.trim()).filter(Boolean) : null;

  const now = Math.floor(Date.now() / 1000);
  const today = await getToday();

  const whereDecks = deckFilter && deckFilter.length > 0
    ? `AND deck IN (${deckFilter.map(() => "?").join(",")})`
    : "";

  const result = await turso.execute({
    sql: `SELECT * FROM cards
          WHERE ((queue=0) OR (queue IN (1,3) AND due <= ?) OR (queue=2 AND due <= ?))
          ${whereDecks}
          ORDER BY due ASC LIMIT ?`,
    args: deckFilter && deckFilter.length > 0
      ? [now, today, ...deckFilter, limit]
      : [now, today, limit],
  });

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
    reps: Number(row.reps),
    lapses: Number(row.lapses),
  }));

  return NextResponse.json(cards);
}

async function getToday(): Promise<number> {
  const r = await turso.execute("SELECT value FROM sync_meta WHERE key='today_offset'");
  return r.rows[0] ? Number(r.rows[0].value) : Math.floor(Date.now() / 86400000);
}
