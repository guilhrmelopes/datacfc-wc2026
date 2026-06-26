import { CardConfronto } from "@/components/mata-mata/CardConfronto";
import { LadoChaveamento } from "@/components/mata-mata/ColunaFase";
import {
  alturaChaveamento,
  faseOitavas,
  montarChaveamentoLados,
} from "@/lib/mataMata";
import type { DadosMataMata } from "@/types/dados";

function IconeTrofeu() {
  return (
    <svg
      viewBox="0 0 64 64"
      className="h-14 w-14 text-[var(--color-muted)]/60"
      aria-hidden
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <path d="M18 10h28v8c0 8-4 14-14 14S18 26 18 18v-8z" />
      <path d="M12 14h6M46 14h6" />
      <path d="M12 14v4c0 5 3 8 6 8M46 14v4c0 5-3 8-6 8" />
      <path d="M32 32v10" />
      <path d="M24 50h16" />
      <path d="M20 54h24" />
      <text x="32" y="24" textAnchor="middle" fill="currentColor" stroke="none" fontSize="14">
        ?
      </text>
    </svg>
  );
}

interface Props {
  dados: DadosMataMata;
}

export function MataMata({ dados }: Props) {
  const { esquerda, direita } = montarChaveamentoLados(dados);
  const oitavas = faseOitavas(dados);
  const alturaRef = alturaChaveamento(
    Math.max(1, Math.ceil((oitavas?.confrontos.length ?? 16) / 2)),
  );

  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]/40 p-4">
        <div className="mx-auto flex min-w-[1100px] items-stretch justify-center gap-4">
          <LadoChaveamento
            fases={esquerda.fases}
            alturaReferencia={alturaRef}
            alinhamento="inicio"
          />

          <div
            className="flex shrink-0 flex-col items-center justify-center gap-4 px-2"
            style={{ minHeight: alturaRef }}
          >
            <div className="flex flex-col items-center gap-1">
              <IconeTrofeu />
              <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--color-muted)]">
                Campeão
              </p>
            </div>
            {dados.final && <CardConfronto confronto={dados.final} destaque="final" />}
            {dados.disputa_bronze && (
              <CardConfronto confronto={dados.disputa_bronze} destaque="bronze" />
            )}
          </div>

          <LadoChaveamento
            fases={direita.fases}
            alturaReferencia={alturaRef}
            alinhamento="fim"
          />
        </div>
    </div>
  );
}
