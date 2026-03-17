const CSS = `
.card { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 18px; text-align: center; color: white; background: transparent; padding: 8px; }
b, strong { color: #a78bfa; }
code { background: rgba(255,255,255,0.1); border-radius: 4px; padding: 2px 6px; font-size: 0.9em; }
`.trim();

function card(
  id: number,
  deck: string,
  front: string,
  back: string,
  queue: number,
  interval: number,
  factor: number,
  reps: number,
  tags: string[] = []
) {
  return {
    id,
    deck,
    model: "Basique",
    fields: { Recto: front, Verso: back },
    question_template: "{{Recto}}",
    answer_template: "{{FrontSide}}<hr id=answer>{{Verso}}",
    css: CSS,
    tags,
    type: queue === 0 ? 0 : queue === 1 ? 1 : 2,
    queue,
    interval,
    factor,
    due: queue === 0 ? 0 : queue === 1 ? Math.floor(Date.now() / 1000) - 60 : Math.floor(Date.now() / 86400000) - 1,
    reps,
    lapses: 0,
  };
}

export const DEMO_CARDS = [
  // Anglais::Vocabulaire — révisions
  card(1001, "Anglais::Vocabulaire", "Serendipity", "Sérendipité — la faculté de faire des <b>découvertes heureuses</b> par hasard", 2, 14, 2500, 8, ["vocab", "b2"]),
  card(1002, "Anglais::Vocabulaire", "Ephemeral", "Éphémère — qui ne dure qu'un <b>très court moment</b>", 2, 7, 2300, 5, ["vocab"]),
  card(1003, "Anglais::Vocabulaire", "Ubiquitous", "Omniprésent — qui se trouve <b>partout à la fois</b>", 2, 21, 2700, 12, ["vocab", "c1"]),
  card(1004, "Anglais::Vocabulaire", "Pragmatic", "Pragmatique — orienté vers <b>l'action concrète</b> plutôt que la théorie", 2, 5, 2200, 4, ["vocab"]),
  card(1005, "Anglais::Vocabulaire", "Meticulous", "Méticuleux — qui fait attention aux <b>détails</b> avec grand soin", 1, 0, 2500, 1, ["vocab"]),
  // Nouvelles
  card(1006, "Anglais::Vocabulaire", "Eloquent", "Éloquent — qui s'exprime avec <b>facilité et persuasion</b>", 0, 0, 2500, 0, ["vocab", "b2"]),
  card(1007, "Anglais::Vocabulaire", "Resilient", "Résilient — capable de <b>surmonter les épreuves</b> et de rebondir", 0, 0, 2500, 0, ["vocab"]),

  // Histoire::Révolution Française — révisions
  card(2001, "Histoire::Révolution Française", "Prise de la Bastille", "<b>14 juillet 1789</b> — Symbole du début de la Révolution française", 2, 30, 2600, 15, ["dates"]),
  card(2002, "Histoire::Révolution Française", "Déclaration des droits de l'Homme", "<b>26 août 1789</b> — Texte fondateur des droits civiques", 2, 12, 2400, 9, ["dates"]),
  card(2003, "Histoire::Révolution Française", "Exécution de Louis XVI", "<b>21 janvier 1793</b> — Place de la Révolution, Paris", 1, 0, 2500, 2, ["dates"]),
  card(2004, "Histoire::Révolution Française", "Début du Directoire", "<b>26 octobre 1795</b> — Fin de la Convention, début d'un gouvernement de 5 directeurs", 2, 8, 2300, 6, ["dates"]),

  // Informatique::Algorithmes — révisions
  card(3001, "Informatique::Algorithmes", "Complexité du <b>QuickSort</b> (cas moyen)", "<code>O(n log n)</code> — pivot aléatoire, récursion sur deux sous-listes", 2, 10, 2500, 7, ["complexity"]),
  card(3002, "Informatique::Algorithmes", "Complexité du <b>tri par insertion</b> (pire cas)", "<code>O(n²)</code> — tableau trié en sens inverse", 2, 3, 2100, 3, ["complexity"]),
  // Nouvelles
  card(3003, "Informatique::Algorithmes", "Quelle structure de données utilise <b>FIFO</b> ?", "La <b>file</b> (Queue) — premier entré, premier sorti", 0, 0, 2500, 0, ["structures"]),
  card(3004, "Informatique::Algorithmes", "Quelle structure de données utilise <b>LIFO</b> ?", "La <b>pile</b> (Stack) — dernier entré, premier sorti", 0, 0, 2500, 0, ["structures"]),
  card(3005, "Informatique::Algorithmes", "Complexité spatiale de la <b>DFS récursive</b>", "<code>O(h)</code> où <em>h</em> est la hauteur de l'arbre d'appels", 0, 0, 2500, 0, ["complexity"]),
];

export const DEMO_COUNTS = {
  new: 5,   // 1006, 1007, 3003, 3004, 3005
  learning: 2, // 1005, 2003
  review: 9,   // les autres
  total: 16,
};

export const DEMO_DECKS = [
  { name: "Anglais::Vocabulaire",         new: 2, learning: 1, review: 4, total: 7  },
  { name: "Histoire::Révolution Française", new: 0, learning: 1, review: 3, total: 4  },
  { name: "Informatique::Algorithmes",    new: 3, learning: 0, review: 2, total: 5  },
];
