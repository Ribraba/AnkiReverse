import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { turso } from "@/lib/turso";

export async function POST(req: Request) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const sub = await req.json();
  const endpoint = sub.endpoint as string;
  const p256dh  = sub.keys?.p256dh as string;
  const auth    = sub.keys?.auth as string;

  if (!endpoint || !p256dh || !auth) {
    return NextResponse.json({ error: "Invalid subscription" }, { status: 400 });
  }

  // Créer la table si elle n'existe pas encore
  await turso.execute(`
    CREATE TABLE IF NOT EXISTS push_subscriptions (
      endpoint TEXT PRIMARY KEY,
      p256dh   TEXT NOT NULL,
      auth     TEXT NOT NULL,
      created_at INTEGER DEFAULT (strftime('%s','now'))
    )
  `);

  await turso.execute({
    sql: `INSERT OR REPLACE INTO push_subscriptions (endpoint, p256dh, auth)
          VALUES (?, ?, ?)`,
    args: [endpoint, p256dh, auth],
  });

  return NextResponse.json({ ok: true });
}
