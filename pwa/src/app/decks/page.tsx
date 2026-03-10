"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Check } from "lucide-react";

interface Deck { name: string; total: number; }

const STORAGE_KEY = "ankireverse_active_decks";

export function getActiveDecks(): string[] | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export default function DecksPage() {
  const [decks, setDecks] = useState<Deck[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/decks")
      .then((r) => r.json())
      .then((data: Deck[]) => {
        setDecks(data);
        const saved = getActiveDecks();
        setSelected(saved ? new Set(saved) : new Set(data.map((d) => d.name)));
      })
      .finally(() => setLoading(false));
  }, []);

  function toggle(name: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...next]));
      return next;
    });
  }

  function selectAll() {
    const all = new Set(decks.map((d) => d.name));
    setSelected(all);
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...all]));
  }

  function selectNone() {
    setSelected(new Set());
    localStorage.setItem(STORAGE_KEY, JSON.stringify([]));
  }

  const selectedCount = selected.size;

  return (
    <main className="min-h-screen bg-[#09090b] text-white">
      <header className="border-b border-white/5 bg-[#09090b]/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-lg mx-auto px-4 py-4 flex items-center gap-3">
          <Link href="/" className="text-zinc-500 hover:text-white transition-colors">
            <ArrowLeft size={18} />
          </Link>
          <h1 className="font-semibold flex-1">Mes decks</h1>
          <span className="text-zinc-500 text-xs">{selectedCount}/{decks.length} actifs</span>
        </div>
      </header>

      <div className="max-w-lg mx-auto px-4 py-4 space-y-3">

        <div className="flex gap-2">
          <button onClick={selectAll}
            className="text-xs bg-white/6 hover:bg-white/10 border border-white/10 rounded-lg px-3 py-1.5 transition-colors">
            Tout sélectionner
          </button>
          <button onClick={selectNone}
            className="text-xs bg-white/6 hover:bg-white/10 border border-white/10 rounded-lg px-3 py-1.5 transition-colors">
            Tout désélectionner
          </button>
        </div>

        {loading && (
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-14 bg-white/4 rounded-xl animate-pulse" />
            ))}
          </div>
        )}

        <div className="space-y-2">
          {decks.map((deck) => {
            const active = selected.has(deck.name);
            return (
              <button key={deck.name} onClick={() => toggle(deck.name)}
                className={`w-full flex items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all active:scale-[0.98]
                  ${active
                    ? "border-violet-500/40 bg-violet-500/10"
                    : "border-white/8 bg-white/4 opacity-50"}`}>
                <div className={`w-5 h-5 rounded-md border flex items-center justify-center shrink-0 transition-colors
                  ${active ? "bg-violet-500 border-violet-500" : "border-white/20"}`}>
                  {active && <Check size={12} strokeWidth={3} />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{deck.name}</p>
                </div>
                <span className="text-xs text-zinc-500 shrink-0">{deck.total} cartes</span>
              </button>
            );
          })}
        </div>

        {selectedCount > 0 && (
          <Link href="/"
            className="block w-full text-center bg-violet-600 hover:bg-violet-500 transition-colors rounded-xl py-3 font-medium text-sm">
            Confirmer ({selectedCount} deck{selectedCount > 1 ? "s" : ""})
          </Link>
        )}
      </div>
    </main>
  );
}
