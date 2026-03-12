import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { turso } from "@/lib/turso";

export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const now = Math.floor(Date.now() / 1000);

  // today_offset stocké par l'add-on à chaque sync
  const metaRes = await turso.execute("SELECT value FROM sync_meta WHERE key='today_offset'");
  const today = metaRes.rows[0] ? Number(metaRes.rows[0].value) : Math.floor(Date.now() / 86400000);

  const result = await turso.execute({
    sql: `SELECT
            deck,
            COUNT(*) FILTER (WHERE queue=0) AS due_new,
            COUNT(*) FILTER (WHERE queue IN (1,3) AND due <= ?) AS due_learning,
            COUNT(*) FILTER (WHERE queue=2 AND due <= ?) AS due_review
          FROM cards
          GROUP BY deck
          ORDER BY deck ASC`,
    args: [now, today],
  });

  const decks = result.rows
    .map((row) => ({
      name: String(row.deck),
      new: Number(row.due_new),
      learning: Number(row.due_learning),
      review: Number(row.due_review),
      total: Number(row.due_new) + Number(row.due_learning) + Number(row.due_review),
    }))
    .filter((d) => d.total > 0 || true); // garder tous les decks même à 0

  return NextResponse.json(decks);
}
