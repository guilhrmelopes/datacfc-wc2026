/** Pageviews por aba — gtag carregado em index.html. */

const MEASUREMENT_ID = import.meta.env.VITE_GA_MEASUREMENT_ID?.trim();

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
  }
}

const ROTULOS_ABA: Record<string, string> = {
  fase: "Fase de Grupos",
  radar: "HUB Seleções",
  mercado: "HUB Jogadores",
};

export function registrarVisualizacao(aba: string): void {
  if (!MEASUREMENT_ID || !window.gtag) return;
  const path = `/${aba}`;
  const title = ROTULOS_ABA[aba] ?? aba;
  window.gtag("event", "page_view", {
    page_path: path,
    page_title: title,
    page_location: `${window.location.origin}${path}`,
  });
}
