import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { turso } from "@/lib/turso";

export async function GET(req: Request) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { searchParams } = new URL(req.url);
  const decksParam = searchParams.get("decks"); // "deck1,deck2"
  const deckFilter = decksParam ? decksParam.split(",").map((d) => d.trim()).filter(Boolean) : null;

  const now = Math.floor(Date.now() / 1000);
  const today = await getToday();

  const whereDecks = deckFilter && deckFilter.length > 0
    ? `AND deck IN (${deckFilter.map(() => "?").join(",")})`
    : "";

  const args = (extra: number[]) =>
    deckFilter && deckFilter.length > 0 ? [...extra, ...deckFilter] : extra;

  const [newR, learnR, reviewR] = await Promise.all([
    turso.execute({ sql: `SELECT COUNT(*) as c FROM cards WHERE queue=0 ${whereDecks}`, args: args([]) }),
    turso.execute({ sql: `SELECT COUNT(*) as c FROM cards WHERE queue IN (1,3) AND due <= ? ${whereDecks}`, args: args([now]) }),
    turso.execute({ sql: `SELECT COUNT(*) as c FROM cards WHERE queue=2 AND due <= ? ${whereDecks}`, args: args([today]) }),
  ]);

  const newCount = Number(newR.rows[0]?.c ?? 0);
  const learningCount = Number(learnR.rows[0]?.c ?? 0);
  const reviewCount = Number(reviewR.rows[0]?.c ?? 0);

  return NextResponse.json({
    new: newCount,
    learning: learningCount,
    review: reviewCount,
    total: newCount + learningCount + reviewCount,
  });
}

async function getToday(): Promise<number> {
  const r = await turso.execute("SELECT value FROM sync_meta WHERE key='today_offset'");
  return r.rows[0] ? Number(r.rows[0].value) : Math.floor(Date.now() / 86400000);
}
