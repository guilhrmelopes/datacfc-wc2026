import {
  classificarFaixaCartolaSelecao,
  classeCelulaMetricaSelecao,
  classeCelulaNeutra,
} from "@/lib/formatacaoMetricas";
import { formatarValorMetrica } from "@/lib/exibirValor";
import { TOOLTIPS_METRICAS } from "@/lib/traducoes";
import type { PerformancePorSigla } from "@/types/dados";

const BUCKETS = ["GOL", "LAT", "ZAG", "MEI", "ATA"] as const;

// Exibe valores quando há pontuação cedida/conquistada (Copa em andamento).
const DADOS_CONGELADOS = false;

interface Props {
  titulo: string;
  sigla: string;
  escudo?: string | null;
  performance?: PerformancePorSigla | null;
}

export function TabelaPerformanceCruzada({ titulo, sigla, escudo, performance }: Props) {
  const siglaExibicao = sigla.trim().toUpperCase();

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)]/50 p-3">
      <div className="mb-2 flex items-center gap-2">
        {escudo && (
          <img src={escudo} alt={siglaExibicao} className="h-7 w-7 object-contain" />
        )}
        <div>
          <p className="text-xs font-semibold uppercase text-[var(--color-muted)]">{titulo}</p>
          <p className="text-sm font-bold">{siglaExibicao}</p>
        </div>
      </div>

      <table className="w-full border-collapse text-center text-xs">
        <thead>
          <tr>
            <th className="border border-[var(--color-border)] px-1 py-1.5" />
            {BUCKETS.map((b) => (
              <th key={b} className="border border-[var(--color-border)] px-1 py-1.5 font-semibold">
                {b}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(["CEDIDO", "CONQUISTADO"] as const).map((linha) => (
            <tr key={linha}>
              <td
                className="border border-[var(--color-border)] px-1 py-1.5 text-left text-[10px] font-semibold"
                title={
                  linha === "CEDIDO"
                    ? TOOLTIPS_METRICAS.CEDIDO
                    : TOOLTIPS_METRICAS.CONQUISTADO
                }
              >
                {linha}
              </td>
              {BUCKETS.map((bucket) => {
                if (DADOS_CONGELADOS) {
                  return (
                    <td
                      key={bucket}
                      className="border border-[var(--color-border)] bg-gray-300 px-1 py-1.5 text-gray-500"
                    >
                      N/A
                    </td>
                  );
                }

                const cel = performance?.[bucket];
                const metrica = linha === "CEDIDO" ? cel?.cedido : cel?.conquistado;
                const valor = metrica?.valor;

                if (valor === null || valor === undefined) {
                  return (
                    <td
                      key={bucket}
                      className={`border border-[var(--color-border)] px-1 py-1.5 ${classeCelulaNeutra()}`}
                    >
                      N/A
                    </td>
                  );
                }

                const invertido = linha === "CEDIDO";
                const classeCor = classeCelulaMetricaSelecao(
                  classificarFaixaCartolaSelecao(valor, invertido),
                );

                return (
                  <td
                    key={bucket}
                    className={`border border-[var(--color-border)] px-1 py-1.5 ${classeCor}`}
                  >
                    {formatarValorMetrica(valor)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
