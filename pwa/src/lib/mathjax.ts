declare global {
  interface Window {
    MathJax?: {
      typesetPromise: (elements?: HTMLElement[]) => Promise<void>;
      startup?: { promise: Promise<void> };
    };
  }
}

export async function typesetMath(el?: HTMLElement | null) {
  if (typeof window === "undefined" || !window.MathJax) return;
  try {
    // Attendre que MathJax soit prêt si nécessaire
    if (window.MathJax.startup?.promise) {
      await window.MathJax.startup.promise;
    }
    await window.MathJax.typesetPromise(el ? [el] : undefined);
  } catch {
    // Ignorer les erreurs MathJax (ex: typesetting en cours)
  }
}
