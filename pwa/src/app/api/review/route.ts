import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { turso } from "@/lib/turso";
import { cookies } from "next/headers";

export async function POST(req: Request) {
  const cookieStore = await cookies();
  if (cookieStore.get("ankireverse_demo")?.value === "1") {
    return NextResponse.json({ ok: true });
  }

  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { card_id, rating } = await req.json();

  if (!card_id || ![1, 2, 3, 4].includes(rating)) {
    return NextResponse.json({ error: "card_id et rating (1-4) requis" }, { status: 400 });
  }

  const now = Math.floor(Date.now() / 1000);

  await turso.execute({
    sql: "INSERT INTO review_log (card_id, rating, reviewed_at) VALUES (?, ?, ?)",
    args: [card_id, rating, now],
  });

  return NextResponse.json({ ok: true });
}
