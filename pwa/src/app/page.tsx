"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Brain, BookOpen, Bell, BellOff, ArrowRight, ChevronRight } from "lucide-react";
import { getDueCounts, type DueCounts } from "@/lib/api";
import { isPushSupported, requestNotificationPermission, registerPushSubscription } from "@/lib/push";
import { getActiveDecks } from "@/app/decks/page";

export default function Home() {
  const [counts, setCounts] = useState<DueCounts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notifStatus, setNotifStatus] = useState<"idle" | "loading" | "ok" | "denied">("idle");

  useEffect(() => {
    const active = getActiveDecks();
    const params = active ? `?decks=${encodeURIComponent(active.join(","))}` : "";
    getDueCounts(params)
      .then(setCounts)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function enableNotifications() {
    setNotifStatus("loading");
    const granted = await requestNotificationPermission();
    if (!granted) { setNotifStatus("denied"); return; }
    const ok = await registerPushSubscription();
    setNotifStatus(ok ? "ok" : "denied");
  }

  return (
    <main className="min-h-screen bg-[#09090b] text-white">
      {/* Header */}
      <header className="border-b border-white/5 bg-[#09090b]/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-lg mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center">
              <Brain size={14} className="text-white" />
            </div>
            <span className="font-semibold tracking-tight">AnkiReverse</span>
          </div>
          <Link href="/review" className="flex items-center gap-1 text-xs text-zinc-400 hover:text-white transition-colors">
            Réviser <ArrowRight size={12} />
          </Link>
        </div>
      </header>

      <div className="max-w-lg mx-auto px-4 py-8 space-y-4">

        {/* Hero */}
        <div className="animate-fade-up" style={{ animationDelay: "0ms" }}>
          <h1 className="text-3xl font-bold tracking-tight">Bonjour Ibrahim</h1>
          <p className="text-zinc-400 mt-1 text-sm">
            {new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" })}
          </p>
        </div>

        {/* Stats card */}
        <div className="animate-fade-up rounded-2xl border border-white/8 bg-white/4 backdrop-blur-sm p-5 space-y-4"
          style={{ animationDelay: "80ms" }}>

          {loading && (
            <div className="space-y-3">
              <div className="h-3 w-24 bg-white/8 rounded-full animate-pulse" />
              <div className="h-9 w-20 bg-white/8 rounded-lg animate-pulse" />
            </div>
          )}

          {error && (
            <p className="text-red-400 text-sm">Impossible de charger les cartes. L&apos;API est-elle lancée ?</p>
          )}

          {counts && (
            <>
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-bold">{counts.total}</span>
                <span className="text-zinc-400 text-sm">cartes à réviser</span>
              </div>

              <div className="flex gap-2">
                <Pill label="Nouvelles" value={counts.new} color="bg-blue-500/10 text-blue-400 border-blue-500/20" />
                <Pill label="Révisions" value={counts.review} color="bg-emerald-500/10 text-emerald-400 border-emerald-500/20" />
                <Pill label="En cours" value={counts.learning} color="bg-amber-500/10 text-amber-400 border-amber-500/20" />
              </div>

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
            </>
          )}
        </div>

        {/* Notifications */}
        {isPushSupported() && notifStatus !== "ok" && (
          <div className="animate-fade-up rounded-2xl border border-white/8 bg-white/4 backdrop-blur-sm p-5"
            style={{ animationDelay: "160ms" }}>
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-white/6 flex items-center justify-center">
                  {notifStatus === "denied" ? <BellOff size={15} className="text-red-400" /> : <Bell size={15} className="text-zinc-300" />}
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
          </div>
        )}

        {/* Navigation */}
        <div className="animate-fade-up grid grid-cols-2 gap-3" style={{ animationDelay: "240ms" }}>
          <NavCard href="/review" icon={<Brain size={18} />} label="Réviser" sub="Session du jour" />
          <NavCard href="/decks" icon={<BookOpen size={18} />} label="Mes decks" sub="Voir la collection" />
        </div>

      </div>
    </main>
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

function NavCard({ href, icon, label, sub }: { href: string; icon: React.ReactNode; label: string; sub: string }) {
  return (
    <Link href={href}
      className="rounded-2xl border border-white/8 bg-white/4 hover:bg-white/8 active:scale-[0.98] transition-all p-4 block">
      <div className="w-8 h-8 rounded-lg bg-white/6 flex items-center justify-center mb-3 text-zinc-300">
        {icon}
      </div>
      <div className="font-medium text-sm">{label}</div>
      <div className="text-zinc-500 text-xs mt-0.5">{sub}</div>
    </Link>
  );
}
