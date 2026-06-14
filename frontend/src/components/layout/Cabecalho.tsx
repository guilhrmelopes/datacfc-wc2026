import { useCallback, useEffect, useState } from "react";
import {
  buscarTimestampDashboard,
  formatarTimestampDashboard,
  INTERVALO_POLL_MS,
} from "@/lib/atualizacaoDashboard";

const PERFIL_X = "https://x.com/DataCartola";

function IconeX({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={className}
      fill="currentColor"
    >
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

export function Cabecalho() {
  const [atualizadoEm, setAtualizadoEm] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  const atualizar = useCallback(async () => {
    const iso = await buscarTimestampDashboard();
    if (iso) setAtualizadoEm(iso);
    setCarregando(false);
  }, []);

  useEffect(() => {
    void atualizar();

    const intervalo = window.setInterval(() => void atualizar(), INTERVALO_POLL_MS);

    function aoFocar() {
      void atualizar();
    }
    window.addEventListener("focus", aoFocar);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") void atualizar();
    });

    return () => {
      window.clearInterval(intervalo);
      window.removeEventListener("focus", aoFocar);
    };
  }, [atualizar]);

  return (
    <header className="mb-6 border-b border-[var(--color-border)] pb-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <img
            src="/assets/logo.png"
            alt="Data CFC"
            className="h-10 w-10 object-contain"
            onError={(evento) => {
              const alvo = evento.currentTarget;
              alvo.onerror = null;
              alvo.src = "/assets/logo.svg";
            }}
          />
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Data CFC — Copa do Mundo 2026</h1>
            <p className="text-sm text-[var(--color-muted)]">
              Análise de seleções, jogadores e confrontos
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2.5">
          <p
            className="text-right text-xs text-[var(--color-muted)]"
            title="Horário de Brasília — atualiza automaticamente após cada rotina"
          >
            {carregando && !atualizadoEm
              ? "Verificando atualização…"
              : atualizadoEm
                ? `Atualizado em ${formatarTimestampDashboard(atualizadoEm)}`
                : "Atualização indisponível"}
          </p>
          <a
            href={PERFIL_X}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Data CFC no X (@DataCartola)"
            title="Siga @DataCartola no X"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[var(--color-border)] text-[var(--color-muted)] transition hover:border-sky-500/50 hover:bg-[var(--color-card)] hover:text-white"
          >
            <IconeX className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>
    </header>
  );
}
