import { traduzirSelecao } from "@/lib/traducoes";
import {
  calcularZonaPorSelecao,
  classeColunaZona,
  type ClassificacaoGruposParseada,
} from "@/lib/classificacaoGrupos";

const GRUPOS = "ABCDEFGHIJKL".split("");
const COLS_STATS = ["P", "J", "V", "E", "D", "GM", "GS", "SG", "%"] as const;

interface Props {
  classificacao: ClassificacaoGruposParseada;
}

export function FaseGrupos({ classificacao }: Props) {
  const { grupos, melhoresTerceiros } = classificacao;
  const zonas = calcularZonaPorSelecao(grupos, melhoresTerceiros);

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {GRUPOS.map((grupo) => {
        const linhas = grupos[grupo] ?? [];
        return (
          <div
            key={grupo}
            className="overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-card)]"
          >
            <div className="bg-[var(--color-accent)] px-3 py-2 text-center text-sm font-bold">
              Grupo {grupo}
            </div>
            <table className="w-full text-center text-xs">
              <thead>
                <tr className="text-[var(--color-muted)]">
                  <th className="px-1 py-2">#</th>
                  <th className="px-1 py-2 text-left">Seleção</th>
                  {COLS_STATS.map((c) => (
                    <th key={c} className="px-1 py-2">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {linhas.map((linha) => {
                  const zona = zonas.get(linha.selecao) ?? "neutro";
                  const classeZona = classeColunaZona(zona);
                  return (
                    <tr
                      key={linha.selecao}
                      className="border-t border-[var(--color-border)]"
                    >
                      <td className={`px-1 py-2 ${classeZona}`}>{linha.posicao}</td>
                      <td className={`px-1 py-2 text-left ${classeZona}`}>
                        <div className="flex items-center gap-1">
                          {linha.url_escudo && (
                            <img
                              src={linha.url_escudo}
                              alt={linha.sigla}
                              className="h-5 w-5"
                            />
                          )}
                          <span className="truncate text-[11px]">
                            {traduzirSelecao(linha.selecao)}
                          </span>
                        </div>
                      </td>
                      <td className={`px-1 py-2 ${classeZona}`}>{linha.P}</td>
                      <td className={`px-1 py-2 ${classeZona}`}>{linha.J}</td>
                      <td className={`px-1 py-2 ${classeZona}`}>{linha.V}</td>
                      <td className={`px-1 py-2 ${classeZona}`}>{linha.E}</td>
                      <td className={`px-1 py-2 ${classeZona}`}>{linha.D}</td>
                      <td className={`px-1 py-2 ${classeZona}`}>{linha.GM}</td>
                      <td className={`px-1 py-2 ${classeZona}`}>{linha.GS}</td>
                      <td className={`px-1 py-2 ${classeZona}`}>{linha.SG}</td>
                      <td className={`px-1 py-2 ${classeZona}`}>{linha.aprov}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        );
      })}

      <div className="col-span-full flex flex-wrap justify-center gap-4 text-xs text-[var(--color-muted)]">
        <span className="inline-flex items-center gap-2">
          <span className="inline-block h-3 w-8 rounded bg-green-500/25" />
          1º e 2º — classificados
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="inline-block h-3 w-8 rounded bg-sky-500/30" />
          3º — melhores terceiros colocados
        </span>
      </div>
    </div>
  );
}
