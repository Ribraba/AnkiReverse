"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { Bell, BellOff, ArrowRight, ChevronRight, Zap } from "lucide-react";
import { getDueCounts, type DueCounts } from "@/lib/api";
import { isPushSupported, requestNotificationPermission, registerPushSubscription } from "@/lib/push";
import { getActiveDecks } from "@/app/decks/page";

interface DeckRow {
  name: string;
  new: number;
  learning: number;
  review: number;
  total: number;
}

export default function Home() {
  const [counts, setCounts] = useState<DueCounts | null>(null);
  const [decks, setDecks] = useState<DeckRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [notifStatus, setNotifStatus] = useState<"idle" | "loading" | "ok" | "denied">("idle");

  useEffect(() => {
    const active = getActiveDecks();
    const params = active ? `?decks=${encodeURIComponent(active.join(","))}` : "";

    Promise.all([
      getDueCounts(params),
      fetch("/api/decks").then((r) => r.json()),
    ])
      .then(([c, d]) => { setCounts(c); setDecks(d); })
      .finally(() => setLoading(false));
  }, []);

  async function enableNotifications() {
    setNotifStatus("loading");
    const granted = await requestNotificationPermission();
    if (!granted) { setNotifStatus("denied"); return; }
    const ok = await registerPushSubscription();
    setNotifStatus(ok ? "ok" : "denied");
  }

  // Filtrer les decks actifs
  const active = getActiveDecks();
  const visibleDecks = active
    ? decks.filter((d) => active.includes(d.name))
    : decks;
  const dueDecks = visibleDecks.filter((d) => d.total > 0);

  return (
    <main className="min-h-screen bg-[#09090b] text-white">
      {/* Header */}
      <header className="border-b border-white/5 bg-[#09090b]/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-lg mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Image src="/icon-192.png" width={28} height={28} alt="AnkiReverse" className="rounded-lg" />
            <span className="font-semibold tracking-tight">AnkiReverse</span>
          </div>
          <Link href="/review" className="flex items-center gap-1 text-xs text-zinc-400 hover:text-white transition-colors">
            Tout réviser <ArrowRight size={12} />
          </Link>
        </div>
      </header>

      <div className="max-w-lg mx-auto px-4 py-6 space-y-4">

        {/* Hero */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Bonjour Ibrahim</h1>
          <p className="text-zinc-400 mt-1 text-sm">
            {new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" })}
          </p>
        </div>

        {/* Résumé global */}
        <MacWindow title="session.anki">
          {loading ? (
            <div className="space-y-3">
              <div className="h-3 w-24 bg-white/8 rounded-full animate-pulse" />
              <div className="h-9 w-20 bg-white/8 rounded-lg animate-pulse" />
            </div>
          ) : counts && (
            <>
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-bold">{counts.total}</span>
                <span className="text-zinc-400 text-sm">cartes à réviser</span>
              </div>
              <div className="flex gap-2 mt-3">
                <Pill label="Nouvelles"  value={counts.new}      color="bg-blue-500/10 text-blue-400 border-blue-500/20" />
                <Pill label="Révisions"  value={counts.review}   color="bg-emerald-500/10 text-emerald-400 border-emerald-500/20" />
                <Pill label="En cours"   value={counts.learning} color="bg-amber-500/10 text-amber-400 border-amber-500/20" />
              </div>
              <div className="mt-4">
                {counts.total > 0 ? (
                  <Link href="/review"
                    className="flex items-center justify-between w-full bg-violet-600 hover:bg-violet-500 active:scale-[0.98] transition-all rounded-xl px-4 py-3 font-medium text-sm">
                    <span>Commencer la session</span>
                    <ChevronRight size={16} className="opacity-70" />
                  </Link>
                ) : (
                  <p className="text-emerald-400 text-sm flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
                    Tout à jour — revenez demain
                  </p>
                )}
              </div>
            </>
          )}
        </MacWindow>

        {/* Liste des decks */}
        <MacWindow title="decks">
          {loading ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-12 bg-white/4 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : dueDecks.length === 0 ? (
            <p className="text-zinc-500 text-sm">Aucun deck avec des cartes dues.</p>
          ) : (
            <div className="space-y-2">
              {dueDecks.map((deck) => {
                const short = deck.name.split("::").pop() ?? deck.name;
                const parent = deck.name.includes("::") ? deck.name.split("::").slice(0, -1).join("::") : null;
                return (
                  <Link
                    key={deck.name}
                    href={`/review?deck=${encodeURIComponent(deck.name)}`}
                    className="flex items-center gap-3 rounded-xl border border-white/8 bg-white/4 hover:bg-white/8 active:scale-[0.99] transition-all px-4 py-3"
                  >
                    <div className="flex-1 min-w-0">
                      {parent && (
                        <p className="text-[10px] text-zinc-600 truncate">{parent}</p>
                      )}
                      <p className="text-sm font-medium truncate">{short}</p>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {deck.new > 0 && (
                        <span className="text-[11px] font-semibold text-blue-400 bg-blue-500/10 rounded-md px-1.5 py-0.5">{deck.new}</span>
                      )}
                      {deck.learning > 0 && (
                        <span className="text-[11px] font-semibold text-amber-400 bg-amber-500/10 rounded-md px-1.5 py-0.5">{deck.learning}</span>
                      )}
                      {deck.review > 0 && (
                        <span className="text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 rounded-md px-1.5 py-0.5">{deck.review}</span>
                      )}
                      <ChevronRight size={14} className="text-zinc-600 ml-1" />
                    </div>
                  </Link>
                );
              })}
              <Link href="/decks"
                className="block text-center text-xs text-zinc-500 hover:text-zinc-300 transition-colors pt-1">
                Gérer les decks →
              </Link>
            </div>
          )}
        </MacWindow>

        {/* Révision bonus */}
        <MacWindow title="bonus">
          <Link href="/extra"
            className="flex items-center gap-3 rounded-xl border border-amber-500/15 bg-amber-500/5 hover:bg-amber-500/10 active:scale-[0.98] transition-all px-4 py-3">
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center shrink-0">
              <Zap size={16} className="text-amber-400" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium">Révision bonus</p>
              <p className="text-xs text-zinc-500">Cartes des 7 prochains jours</p>
            </div>
            <ChevronRight size={14} className="text-zinc-600" />
          </Link>
        </MacWindow>

        {/* Notifications */}
        {isPushSupported() && notifStatus !== "ok" && (
          <MacWindow title="notifications">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-white/6 flex items-center justify-center">
                  {notifStatus === "denied"
                    ? <BellOff size={15} className="text-red-400" />
                    : <Bell size={15} className="text-zinc-300" />}
                </div>
                <div>
                  <p className="font-medium text-sm">Notifications</p>
                  <p className="text-zinc-500 text-xs">Rappel quotidien à 9h</p>
                </div>
              </div>
              {notifStatus === "denied" ? (
                <span className="text-red-400 text-xs">Refusé</span>
              ) : (
                <button onClick={enableNotifications} disabled={notifStatus === "loading"}
                  className="shrink-0 text-xs bg-white/6 hover:bg-white/10 border border-white/10 rounded-lg px-3 py-1.5 transition-colors disabled:opacity-40">
                  {notifStatus === "loading" ? "..." : "Activer"}
                </button>
              )}
            </div>
          </MacWindow>
        )}

      </div>
    </main>
  );
}

function MacWindow({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/8 overflow-hidden bg-[#141416]">
      <div className="flex items-center gap-1.5 px-3 py-2.5 bg-[#1f1f21] border-b border-white/6">
        <div className="w-3 h-3 rounded-full bg-[#FF5F57]" />
        <div className="w-3 h-3 rounded-full bg-[#FFBD2E]" />
        <div className="w-3 h-3 rounded-full bg-[#28C840]" />
        {title && <span className="ml-2 text-xs text-zinc-600 select-none">{title}</span>}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function Pill({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className={`rounded-lg border px-2.5 py-1.5 ${color}`}>
      <div className="text-sm font-semibold">{value}</div>
      <div className="text-xs opacity-60">{label}</div>
    </div>
  );
}
