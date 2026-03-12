"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Zap, CheckCircle } from "lucide-react";
import { getExtraCards, submitReview, type AnkiCard } from "@/lib/api";
import { getActiveDecks } from "@/app/decks/page";
import { typesetMath, preprocessLatex } from "@/lib/mathjax";

function renderQuestion(template: string, fields: Record<string, string>): string {
  return preprocessLatex(
    template.replace(/\{\{([^}]+)\}\}/g, (_, key) => fields[key.trim()] ?? "").trim()
  );
}

function renderFullAnswer(qTemplate: string, aTemplate: string, fields: Record<string, string>): string {
  const front = renderQuestion(qTemplate, fields);
  return preprocessLatex(
    aTemplate
      .replace(/\{\{FrontSide\}\}/gi, front)
      .replace(/\{\{([^}]+)\}\}/g, (_, key) => fields[key.trim()] ?? "")
      .replace(
        /<hr\s+id=["']?answer["']?\s*\/?>/gi,
        '<hr style="border:none;border-top:1px solid rgba(255,255,255,0.1);margin:20px 0"/>'
      )
      .trim()
  );
}

function daysUntil(due: number): string {
  const today = Math.floor(Date.now() / 86400000);
  const diff = due - today;
  if (diff <= 0) return "aujourd'hui";
  if (diff === 1) return "demain";
  return `dans ${diff} jours`;
}

export default function ExtraReviewPage() {
  const [cards, setCards] = useState<AnkiCard[]>([]);
  const [index, setIndex] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const active = getActiveDecks();
    const params = active ? `?decks=${encodeURIComponent(active.join(","))}` : "";
    getExtraCards(7, 50, params)
      .then(setCards)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

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
  if (error) return <Screen><p className="text-red-400 text-sm">{error}</p></Screen>;
  if (cards.length === 0) return (
    <Screen>
      <div className="text-center space-y-3">
        <CheckCircle size={40} className="text-emerald-400 mx-auto" />
        <p className="font-medium">Aucune carte à venir</p>
        <p className="text-zinc-500 text-sm">Toutes vos cartes sont déjà dues.</p>
        <Link href="/" className="text-violet-400 text-sm">← Accueil</Link>
      </div>
    </Screen>
  );

  if (done) return (
    <Screen>
      <div className="text-center space-y-4 px-4">
        <Zap size={48} className="text-amber-400 mx-auto" />
        <p className="font-bold text-xl">Session bonus terminée</p>
        <p className="text-zinc-400 text-sm">{cards.length} cartes révisées en avance</p>
        <Link href="/" className="block bg-violet-600 hover:bg-violet-500 transition-colors rounded-xl py-3 px-6 font-medium text-sm">
          Retour à l&apos;accueil
        </Link>
      </div>
    </Screen>
  );

  const question   = renderQuestion(card.question_template, card.fields);
  const fullAnswer = renderFullAnswer(card.question_template, card.answer_template, card.fields);

  return (
    <main className="min-h-screen bg-[#09090b] text-white flex flex-col">
      {/* Header */}
      <header className="border-b border-white/5 px-4 py-3 flex items-center gap-3">
        <Link href="/" className="text-zinc-500 hover:text-white transition-colors"><ArrowLeft size={18} /></Link>
        <div className="flex-1 bg-white/6 rounded-full h-1.5 overflow-hidden">
          <div className="bg-amber-500 h-full rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }} />
        </div>
        <span className="text-zinc-500 text-xs tabular-nums">{index + 1}/{cards.length}</span>
      </header>

      {/* Deck / due date */}
      <div className="px-4 pt-3 pb-1 flex items-center gap-2 flex-wrap">
        <span className="text-xs text-zinc-500 bg-white/5 rounded-md px-2 py-0.5">{card.deck}</span>
        <span className="text-xs text-amber-500/70 bg-amber-500/10 rounded-md px-2 py-0.5">
          Due {daysUntil(card.due)}
        </span>
        {card.tags.slice(0, 2).map((t) => (
          <span key={t} className="text-xs text-zinc-600 bg-white/4 rounded-md px-2 py-0.5">{t}</span>
        ))}
      </div>

      {/* Carte */}
      <div ref={contentRef} className="flex-1 overflow-y-auto px-5 py-5">
        {card.css && <style dangerouslySetInnerHTML={{ __html: card.css }} />}

        {!showAnswer && (
          <div className="rounded-3xl border border-white/8 bg-white/4 px-7 py-9">
            <div className="prose prose-invert prose-base max-w-none text-center w-full"
              dangerouslySetInnerHTML={{ __html: question }} />
          </div>
        )}

        {showAnswer && (
          <div className="rounded-3xl border border-amber-500/20 bg-amber-500/5 px-7 py-9 animate-fade-in">
            <div className="prose prose-invert prose-base max-w-none text-center w-full"
              dangerouslySetInnerHTML={{ __html: fullAnswer }} />
          </div>
        )}
      </div>

      {/* Boutons */}
      <div className="px-4 pb-8 pt-2 space-y-2">
        {!showAnswer ? (
          <button onClick={() => setShowAnswer(true)}
            className="w-full bg-white/8 hover:bg-white/12 active:bg-white/16 border border-white/10 transition-colors rounded-2xl py-4 font-medium">
            Voir la réponse
          </button>
        ) : (
          <div className="grid grid-cols-4 gap-2">
            <RatingBtn label="Raté"   color="bg-red-500/15 hover:bg-red-500/25 text-red-400 border-red-500/20"       onClick={() => next(1)} />
            <RatingBtn label="Dur"    color="bg-amber-500/15 hover:bg-amber-500/25 text-amber-400 border-amber-500/20" onClick={() => next(2)} />
            <RatingBtn label="Bien"   color="bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-400 border-emerald-500/20" onClick={() => next(3)} />
            <RatingBtn label="Facile" color="bg-blue-500/15 hover:bg-blue-500/25 text-blue-400 border-blue-500/20"   onClick={() => next(4)} />
          </div>
        )}
      </div>
    </main>
  );
}

function RatingBtn({ label, color, onClick }: { label: string; color: string; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className={`${color} border rounded-xl py-3.5 text-sm font-medium active:scale-95 transition-all`}>
      {label}
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
