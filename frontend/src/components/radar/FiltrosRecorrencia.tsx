import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { GRUPOS_FILTRO } from "./FiltrosScouts";
import { formatarDataCurta, OPCOES_FILTRO_RODADA } from "@/lib/recorrenciaHelpers";

/** Largura conforme o texto — sobrescreve min-w-[180px] padrão do SelectTrigger. */
const CLASSE_SELECT = "h-9 w-auto min-w-0 whitespace-nowrap px-3 text-sm";

interface Props {
  rodadaFiltro: string;
  diaAtual: string;
  datasDisponiveis: string[];
  grupo: string;
  busca: string;
  onRodadaChange: (id: string) => void;
  onDiaChange: (d: string) => void;
  onGrupoChange: (g: string) => void;
  onBuscaChange: (q: string) => void;
}

function labelGrupo(valor: string): string {
  if (valor === "TODOS") return "Todos os grupos";
  return `Grupo ${valor}`;
}

export function FiltrosRecorrencia({
  rodadaFiltro,
  diaAtual,
  datasDisponiveis,
  grupo,
  busca,
  onRodadaChange,
  onDiaChange,
  onGrupoChange,
  onBuscaChange,
}: Props) {
  return (
    <div className="flex w-fit max-w-full flex-wrap items-end gap-x-4 gap-y-3">
      <div className="flex flex-col gap-1">
        <span className="text-xs text-[var(--color-muted)]">Rodada</span>
        <Select value={rodadaFiltro} onValueChange={onRodadaChange}>
          <SelectTrigger className={CLASSE_SELECT}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {OPCOES_FILTRO_RODADA.map((op) => (
              <SelectItem key={op.id} value={op.id}>
                {op.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-xs text-[var(--color-muted)]">Data</span>
        <Select value={diaAtual || undefined} onValueChange={onDiaChange} disabled={!datasDisponiveis.length}>
          <SelectTrigger className={CLASSE_SELECT}>
            <SelectValue placeholder="—" />
          </SelectTrigger>
          <SelectContent>
            {datasDisponiveis.map((d) => (
              <SelectItem key={d} value={d}>
                {formatarDataCurta(d)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-xs text-[var(--color-muted)]">Grupo</span>
        <Select value={grupo} onValueChange={onGrupoChange}>
          <SelectTrigger className={CLASSE_SELECT}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {GRUPOS_FILTRO.map((g) => (
              <SelectItem key={g} value={g}>
                {labelGrupo(g)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-xs text-[var(--color-muted)]">Buscar seleção</span>
        <input
          type="search"
          value={busca}
          onChange={(e) => onBuscaChange(e.target.value)}
          placeholder="Nome ou sigla…"
          className="h-9 w-[10.5rem] rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 text-sm"
        />
      </div>
    </div>
  );
}
