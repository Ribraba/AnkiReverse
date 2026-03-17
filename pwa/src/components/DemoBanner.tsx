import { cookies } from "next/headers";

export async function DemoBanner() {
  const cookieStore = await cookies();
  if (cookieStore.get("ankireverse_demo")?.value !== "1") return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-between gap-3 bg-violet-600/95 backdrop-blur-sm px-4 py-2.5 text-sm font-medium">
      <span>Mode démo — les données sont fictives</span>
      <a
        href="/api/demo/exit"
        className="shrink-0 text-xs bg-white/15 hover:bg-white/25 border border-white/20 rounded-lg px-3 py-1 transition-colors"
      >
        Quitter
      </a>
    </div>
  );
}
