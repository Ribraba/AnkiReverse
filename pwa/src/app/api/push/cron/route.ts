import { NextResponse } from "next/server";
import webpush from "web-push";
import { turso } from "@/lib/turso";

// Appelé par Vercel Cron à 9h (Europe/Paris = UTC+1/+2)
export async function GET(req: Request) {
  // Vérifier le secret Vercel Cron (optionnel mais recommandé)
  const authHeader = req.headers.get("authorization");
  if (process.env.CRON_SECRET && authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const vapidPublic  = process.env.NEXT_PUBLIC_VAPID_KEY ?? "";
  const vapidPrivate = process.env.VAPID_PRIVATE_KEY ?? "";
  const vapidEmail   = process.env.VAPID_EMAIL ?? "mailto:admin@ankireverse.app";

  if (!vapidPublic || !vapidPrivate) {
    return NextResponse.json({ error: "VAPID keys missing" }, { status: 500 });
  }

  webpush.setVapidDetails(vapidEmail, vapidPublic, vapidPrivate);

  // Compter les cartes dues aujourd'hui
  const metaRes = await turso.execute("SELECT value FROM sync_meta WHERE key='today_offset'");
  const today   = metaRes.rows[0] ? Number(metaRes.rows[0].value) : Math.floor(Date.now() / 86400000);
  const now     = Math.floor(Date.now() / 1000);

  const countRes = await turso.execute({
    sql: `SELECT COUNT(*) as n FROM cards
          WHERE (queue=0) OR (queue IN (1,3) AND due<=?) OR (queue=2 AND due<=?)`,
    args: [now, today],
  });
  const total = Number(countRes.rows[0]?.n ?? 0);

  if (total === 0) {
    return NextResponse.json({ sent: 0, reason: "no cards due" });
  }

  // Récupérer toutes les subscriptions
  let subs: { endpoint: string; p256dh: string; auth: string }[] = [];
  try {
    const res = await turso.execute("SELECT endpoint, p256dh, auth FROM push_subscriptions");
    subs = res.rows.map((r) => ({
      endpoint: String(r.endpoint),
      p256dh:   String(r.p256dh),
      auth:     String(r.auth),
    }));
  } catch {
    return NextResponse.json({ error: "No subscriptions table" }, { status: 500 });
  }

  const payload = JSON.stringify({
    title: "AnkiReverse",
    body: `${total} carte${total > 1 ? "s" : ""} à réviser aujourd'hui`,
    icon: "/icon-192.png",
    url: "/review",
  });

  let sent = 0;
  const dead: string[] = [];

  await Promise.allSettled(
    subs.map(async (sub) => {
      try {
        await webpush.sendNotification(
          { endpoint: sub.endpoint, keys: { p256dh: sub.p256dh, auth: sub.auth } },
          payload,
        );
        sent++;
      } catch (err: unknown) {
        // Subscription expirée → supprimer
        if (err && typeof err === "object" && "statusCode" in err &&
            (err.statusCode === 404 || err.statusCode === 410)) {
          dead.push(sub.endpoint);
        }
      }
    })
  );

  // Nettoyer les subscriptions expirées
  for (const ep of dead) {
    await turso.execute({ sql: "DELETE FROM push_subscriptions WHERE endpoint=?", args: [ep] });
  }

  return NextResponse.json({ sent, total, removed: dead.length });
}
