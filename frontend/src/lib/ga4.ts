/** Coleta privada via Google Analytics 4 — só ativa com VITE_GA_MEASUREMENT_ID. */

const MEASUREMENT_ID = import.meta.env.VITE_GA_MEASUREMENT_ID?.trim();

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
  }
}

let inicializado = false;

export function initGA4(): void {
  if (inicializado || !MEASUREMENT_ID || typeof window === "undefined") return;

  window.dataLayer = window.dataLayer ?? [];
  window.gtag = function gtag(...args: unknown[]) {
    window.dataLayer!.push(args);
  };
  window.gtag("js", new Date());
  window.gtag("config", MEASUREMENT_ID, { send_page_view: false });

  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${MEASUREMENT_ID}`;
  document.head.appendChild(script);

  inicializado = true;
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
