import { traduzirSelecao } from "@/lib/traducoes";
import {
  calcularZonaPorSelecao,
  classeColunaZona,
  type ClassificacaoGruposParseada,
} from "@/lib/classificacaoGrupos";

interface Props {
  grupo: string;
  classificacao: ClassificacaoGruposParseada;
  selecoesDestaque?: Set<string>;
}

export function MiniClassificacaoGrupo({ grupo, classificacao, selecoesDestaque }: Props) {
  const linhas = classificacao.grupos[grupo] ?? [];
  if (linhas.length === 0) return null;

  const zonas = calcularZonaPorSelecao(classificacao.grupos, classificacao.melhoresTerceiros);

  return (
    <div className="overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-background)]/50">
      <div className="bg-[var(--color-accent)] px-3 py-1.5 text-center text-xs font-bold">
        Classificação — Grupo {grupo}
      </div>
      <table className="w-full text-center text-[11px]">
        <thead>
          <tr className="text-[var(--color-muted)]">
            <th className="px-1 py-1.5">#</th>
            <th className="px-1 py-1.5 text-left">Seleção</th>
            <th className="px-1 py-1.5">P</th>
            <th className="px-1 py-1.5">J</th>
            <th className="px-1 py-1.5">SALDO</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((linha) => {
            const zona = zonas.get(linha.selecao) ?? "neutro";
            const destaque = selecoesDestaque?.has(linha.selecao);
            return (
              <tr
                key={linha.selecao}
                className={`border-t border-[var(--color-border)] ${destaque ? "ring-1 ring-inset ring-sky-400/60" : ""}`}
              >
                <td className={`px-1 py-1.5 ${classeColunaZona(zona)}`}>{linha.posicao}</td>
                <td className={`px-1 py-1.5 text-left ${classeColunaZona(zona)}`}>
                  <div className="flex items-center gap-1">
                    {linha.url_escudo && (
                      <img src={linha.url_escudo} alt={linha.sigla} className="h-4 w-4" />
                    )}
                    <span className="truncate">{traduzirSelecao(linha.selecao)}</span>
                  </div>
                </td>
                <td className={`px-1 py-1.5 font-semibold ${classeColunaZona(zona)}`}>
                  {linha.P}
                </td>
                <td className={`px-1 py-1.5 ${classeColunaZona(zona)}`}>{linha.J}</td>
                <td className={`px-1 py-1.5 ${classeColunaZona(zona)}`}>{linha.SG}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
