import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { turso } from "@/lib/turso";

export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const result = await turso.execute(
    "SELECT deck, COUNT(*) as total FROM cards GROUP BY deck ORDER BY deck ASC"
  );

  const decks = result.rows.map((row) => ({
    name: String(row.deck),
    total: Number(row.total),
  }));

  return NextResponse.json(decks);
}
