"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, PartyPopper, CheckCircle } from "lucide-react";
import { getDueCards, submitReview, type AnkiCard } from "@/lib/api";
import { getActiveDecks } from "@/app/decks/page";
import { typesetMath } from "@/lib/mathjax";

function renderQuestion(template: string, fields: Record<string, string>): string {
  return template
    .replace(/\{\{([^}]+)\}\}/g, (_, key) => fields[key.trim()] ?? "")
    .trim();
}

function renderAnswer(template: string, fields: Record<string, string>): string {
  // Ne garder que ce qui est APRÈS <hr id=answer> — évite le double énoncé
  const hrMatch = template.match(/<hr\s+id=["']?answer["']?\s*\/?>/i);
  const backPart = hrMatch
    ? template.slice((hrMatch.index ?? 0) + hrMatch[0].length)
    : template.replace(/\{\{FrontSide\}\}/gi, "");

  return backPart
    .replace(/\{\{([^}]+)\}\}/g, (_, key) => fields[key.trim()] ?? "")
    .trim();
}

function formatInterval(days: number): string {
  if (days < 1) return "< 1 j";
  if (days < 30) return `${days} j`;
  if (days < 365) return `${Math.round(days / 30)} mois`;
  return `${(days / 365).toFixed(1)} an`;
}

function sm2Intervals(ivl: number, factor: number): [string, string, string, string] {
  if (ivl === 0) return ["< 10 min", "1 j", "1 j", "4 j"];
  return [
    "< 10 min",
    formatInterval(Math.max(1, Math.round(ivl * 1.2))),
    formatInterval(Math.max(1, Math.round(ivl * factor / 1000))),
    formatInterval(Math.max(1, Math.round(ivl * factor / 1000 * 1.3))),
  ];
}

export default function ReviewPage() {
  return <Suspense fallback={<Screen><p className="text-zinc-400 text-sm">Chargement...</p></Screen>}><ReviewContent /></Suspense>;
}

function ReviewContent() {
  const searchParams = useSearchParams();
  const deckParam = searchParams.get("deck"); // un seul deck si cliqué depuis l'accueil

  const [cards, setCards] = useState<AnkiCard[]>([]);
  const [index, setIndex] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let params: string;
    if (deckParam) {
      params = `?decks=${encodeURIComponent(deckParam)}`;
    } else {
      const active = getActiveDecks();
      params = active ? `?decks=${encodeURIComponent(active.join(","))}` : "";
    }
    getDueCards(50, params)
      .then(setCards)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [deckParam]);

  // Re-render MathJax après chaque changement de carte ou affichage de la réponse
  useEffect(() => {
    typesetMath(contentRef.current ?? undefined);
  }, [index, showAnswer]);

  const card = cards[index];
  const progress = cards.length > 0 ? (index / cards.length) * 100 : 0;

  function next(rating: number) {
    submitReview(card.id, rating).catch(console.error);
    setShowAnswer(false);
    if (index + 1 >= cards.length) setDone(true);
    else setIndex((i) => i + 1);
  }

  if (loading) return <Screen><p className="text-zinc-400 text-sm">Chargement...</p></Screen>;
  if (error)   return <Screen><p className="text-red-400 text-sm">{error}</p></Screen>;
  if (cards.length === 0) return (
    <Screen>
      <div className="text-center space-y-3">
        <CheckCircle size={40} className="text-emerald-400 mx-auto" />
        <p className="font-medium">Rien à réviser !</p>
        <Link href="/" className="text-violet-400 text-sm">← Accueil</Link>
      </div>
    </Screen>
  );

  if (done) return (
    <Screen>
      <div className="text-center space-y-4 px-4">
        <PartyPopper size={48} className="text-violet-400 mx-auto" />
        <p className="font-bold text-xl">Session terminée</p>
        <p className="text-zinc-400 text-sm">{cards.length} cartes révisées</p>
        <Link href="/" className="block bg-violet-600 hover:bg-violet-500 transition-colors rounded-xl py-3 px-6 font-medium text-sm">
          Retour à l&apos;accueil
        </Link>
      </div>
    </Screen>
  );

  const question = renderQuestion(card.question_template, card.fields);
  const answer   = renderAnswer(card.answer_template, card.fields);
  const [t1, t2, t3, t4] = sm2Intervals(card.interval, card.factor);
  const deckShort = card.deck.split("::").pop() ?? card.deck;

  return (
    <main className="h-screen bg-[#09090b] text-white flex flex-col overflow-hidden">
      {/* Header */}
      <header className="shrink-0 border-b border-white/5 px-4 py-3 flex items-center gap-3">
        <Link href="/" className="shrink-0 text-zinc-500 hover:text-white transition-colors">
          <ArrowLeft size={18} />
        </Link>
        <div className="flex-1 bg-white/6 rounded-full h-1.5 overflow-hidden">
          <div className="bg-violet-500 h-full rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }} />
        </div>
        <span className="shrink-0 text-zinc-500 text-xs tabular-nums">{index + 1}/{cards.length}</span>
      </header>

      {/* Deck / tags */}
      <div className="shrink-0 px-4 pt-2 pb-1 flex items-center gap-2 min-w-0">
        <span className="text-xs text-zinc-500 bg-white/5 rounded-md px-2 py-0.5 truncate max-w-[65%]">
          {deckShort}
        </span>
        {card.tags.slice(0, 2).map((t) => (
          <span key={t} className="text-xs text-zinc-600 bg-white/4 rounded-md px-2 py-0.5 truncate max-w-[28%]">{t}</span>
        ))}
      </div>

      {/* Zone de contenu scrollable */}
      <div ref={contentRef} className="flex-1 overflow-y-auto px-5 py-5 space-y-4">
        {card.css && <style dangerouslySetInnerHTML={{ __html: card.css }} />}

        {/* Question */}
        <div className="rounded-3xl border border-white/8 bg-white/4 px-7 py-9">
          <div className="prose prose-invert prose-base max-w-none text-center w-full"
            dangerouslySetInnerHTML={{ __html: question }} />
        </div>

        {/* Réponse — uniquement ce qui est après <hr id=answer> */}
        {showAnswer && answer && (
          <div className="rounded-3xl border border-violet-500/20 bg-violet-500/5 px-7 py-9 animate-fade-in">
            <div className="prose prose-invert prose-base max-w-none text-center w-full"
              dangerouslySetInnerHTML={{ __html: answer }} />
          </div>
        )}
      </div>

      {/* Boutons — collés au bas, respecte la safe area iOS */}
      <div
        className="shrink-0 px-5 pt-3 space-y-2"
        style={{ paddingBottom: "max(32px, env(safe-area-inset-bottom, 32px))" }}
      >
        {!showAnswer ? (
          <button onClick={() => setShowAnswer(true)}
            className="w-full bg-white/8 hover:bg-white/12 active:bg-white/16 border border-white/10 transition-colors rounded-2xl py-4 font-medium">
            Voir la réponse
          </button>
        ) : (
          <div className="grid grid-cols-4 gap-2">
            <RatingBtn label="Raté"   hint={t1} color="bg-red-500/15 hover:bg-red-500/25 text-red-400 border-red-500/20"                 onClick={() => next(1)} />
            <RatingBtn label="Dur"    hint={t2} color="bg-amber-500/15 hover:bg-amber-500/25 text-amber-400 border-amber-500/20"         onClick={() => next(2)} />
            <RatingBtn label="Bien"   hint={t3} color="bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-400 border-emerald-500/20" onClick={() => next(3)} />
            <RatingBtn label="Facile" hint={t4} color="bg-blue-500/15 hover:bg-blue-500/25 text-blue-400 border-blue-500/20"             onClick={() => next(4)} />
          </div>
        )}
      </div>
    </main>
  );
}

function RatingBtn({ label, hint, color, onClick }: {
  label: string; hint: string; color: string; onClick: () => void;
}) {
  return (
    <button onClick={onClick}
      className={`${color} border rounded-xl py-3 flex flex-col items-center gap-0.5 active:scale-95 transition-all`}>
      <span className="text-sm font-medium">{label}</span>
      <span className="text-[10px] opacity-50">{hint}</span>
    </button>
  );
}

function Screen({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-[#09090b] text-white flex items-center justify-center">
      {children}
    </main>
  );
}
