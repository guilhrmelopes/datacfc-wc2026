export function Cabecalho() {
  return (
    <header className="mb-6 border-b border-[var(--color-border)] pb-4">
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
    </header>
  );
}
