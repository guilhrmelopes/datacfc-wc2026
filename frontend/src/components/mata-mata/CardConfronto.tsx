import { traduzirSelecao } from "@/lib/traducoes";
import type { ConfrontoMataMata, ParticipanteMataMata } from "@/types/dados";

function EscudoPlaceholder() {
  return (
    <span
      className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-dashed border-[var(--color-muted)]/50 bg-[var(--color-background)] text-[9px] text-[var(--color-muted)]"
      aria-hidden
    >
      ?
    </span>
  );
}

function LinhaTime({
  participante,
  placar,
  venceu,
}: {
  participante: ParticipanteMataMata;
  placar: number | null;
  venceu: boolean;
}) {
  const nome =
    participante.selecao != null
      ? traduzirSelecao(participante.selecao)
      : participante.rotulo;
  const temEscudo = Boolean(participante.url_escudo);
  const indefinido = participante.tbd && !temEscudo;

  return (
    <div
      className={`flex items-center gap-1.5 px-2 py-1 ${
        venceu ? "border-l-2 border-emerald-400 bg-emerald-500/10" : ""
      }`}
    >
      {temEscudo ? (
        <img
          src={participante.url_escudo!}
          alt={participante.sigla ?? participante.rotulo}
          className="h-5 w-5 shrink-0 object-contain"
        />
      ) : (
        <EscudoPlaceholder />
      )}
      <span
        className={`min-w-0 flex-1 truncate text-[11px] font-medium ${
          indefinido ? "italic text-[var(--color-muted)]" : ""
        }`}
        title={nome}
      >
        {participante.sigla ?? participante.rotulo}
      </span>
      {placar != null && (
        <span className="w-4 shrink-0 text-right text-[11px] font-semibold tabular-nums">
          {placar}
        </span>
      )}
    </div>
  );
}

interface Props {
  confronto: ConfrontoMataMata;
  destaque?: "final" | "bronze" | null;
}

export function CardConfronto({ confronto, destaque = null }: Props) {
  const mostrarPlacar = confronto.finalizada || confronto.em_andamento;

  return (
    <article
      className={`w-[148px] shrink-0 overflow-hidden rounded-lg border bg-[var(--color-card)] ${
        confronto.em_andamento
          ? "border-sky-500/50 ring-1 ring-sky-500/20"
          : "border-[var(--color-border)]"
      }`}
    >
      <div className="divide-y divide-[var(--color-border)]">
        <LinhaTime
          participante={confronto.mandante}
          placar={mostrarPlacar ? confronto.placar_mandante : null}
          venceu={confronto.mandante_venceu}
        />
        <LinhaTime
          participante={confronto.visitante}
          placar={mostrarPlacar ? confronto.placar_visitante : null}
          venceu={confronto.visitante_venceu}
        />
      </div>
      <footer className="border-t border-[var(--color-border)] px-2 py-1 text-center">
        {destaque === "final" && (
          <span className="mb-0.5 inline-block rounded bg-amber-400/90 px-1.5 py-px text-[9px] font-bold uppercase tracking-wide text-black">
            Final
          </span>
        )}
        {destaque === "bronze" && (
          <span className="mb-0.5 inline-block rounded bg-sky-600 px-1.5 py-px text-[9px] font-bold uppercase tracking-wide text-white">
            3º lugar
          </span>
        )}
        <p className="text-[10px] text-[var(--color-muted)]">
          {confronto.data
            ? new Date(`${confronto.data}T12:00:00`).toLocaleDateString("pt-BR", {
                day: "numeric",
                month: "short",
              })
            : "—"}
        </p>
      </footer>
    </article>
  );
}
