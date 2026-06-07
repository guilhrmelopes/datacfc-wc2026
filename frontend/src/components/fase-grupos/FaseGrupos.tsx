import { traduzirSelecao } from "@/lib/traducoes";
import type { ClassificacaoGrupos } from "@/types/dados";

const GRUPOS = "ABCDEFGHIJKL".split("");

interface Props {
  classificacao: ClassificacaoGrupos;
}

export function FaseGrupos({ classificacao }: Props) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {GRUPOS.map((grupo) => {
        const linhas = classificacao[grupo] ?? [];
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
                  <th className="px-1 py-2">P</th>
                  <th className="px-1 py-2">J</th>
                  <th className="px-1 py-2">V</th>
                  <th className="px-1 py-2">E</th>
                  <th className="px-1 py-2">D</th>
                  <th className="px-1 py-2">GM</th>
                  <th className="px-1 py-2">GS</th>
                  <th className="px-1 py-2">SG</th>
                  <th className="px-1 py-2">%</th>
                </tr>
              </thead>
              <tbody>
                {linhas.map((linha) => (
                  <tr
                    key={linha.selecao}
                    className="border-t border-[var(--color-border)]"
                  >
                    <td className="px-1 py-2">{linha.posicao}</td>
                    <td className="px-1 py-2 text-left">
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
                    <td className="px-1 py-2">{linha.P}</td>
                    <td className="px-1 py-2">{linha.J}</td>
                    <td className="px-1 py-2">{linha.V}</td>
                    <td className="px-1 py-2">{linha.E}</td>
                    <td className="px-1 py-2">{linha.D}</td>
                    <td className="px-1 py-2">{linha.GM}</td>
                    <td className="px-1 py-2">{linha.GS}</td>
                    <td className="px-1 py-2">{linha.SG}</td>
                    <td className="px-1 py-2">{linha.aprov}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
