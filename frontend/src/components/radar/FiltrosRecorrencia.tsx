import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { GRUPOS_FILTRO } from "./FiltrosScouts";

const CLASSE_SELECT = "h-8 min-w-[110px] text-sm";

interface Props {
  rodada: number;
  rodadasDisponiveis: number[];
  diaAtual: string;
  datasDisponiveis: string[];
  grupo: string;
  somenteJogosDia: boolean;
  busca: string;
  onRodadaChange: (r: number) => void;
  onDiaChange: (d: string) => void;
  onGrupoChange: (g: string) => void;
  onSomenteJogosDiaChange: (v: boolean) => void;
  onBuscaChange: (q: string) => void;
}

function formatarDataCurta(data: string): string {
  if (!data) return "";
  const [, mes, dia] = data.split("-");
  return `${dia}/${mes}`;
}

export function FiltrosRecorrencia({
  rodada,
  rodadasDisponiveis,
  diaAtual,
  datasDisponiveis,
  grupo,
  somenteJogosDia,
  busca,
  onRodadaChange,
  onDiaChange,
  onGrupoChange,
  onSomenteJogosDiaChange,
  onBuscaChange,
}: Props) {
  const idxDia = datasDisponiveis.indexOf(diaAtual);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select value={String(rodada)} onValueChange={(v) => onRodadaChange(Number(v))}>
        <SelectTrigger className={CLASSE_SELECT}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {rodadasDisponiveis.map((r) => (
            <SelectItem key={r} value={String(r)}>
              Rodada {r}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <div className="flex items-center rounded-lg border border-[var(--color-border)]">
        <button
          type="button"
          onClick={() => onDiaChange(datasDisponiveis[idxDia - 1])}
          disabled={idxDia <= 0}
          className="px-2 py-1.5 text-sm disabled:opacity-30"
          aria-label="Dia anterior"
        >
          ‹
        </button>
        <Select value={diaAtual} onValueChange={onDiaChange}>
          <SelectTrigger className="h-8 min-w-[100px] border-0 text-sm shadow-none">
            <SelectValue placeholder="Data" />
          </SelectTrigger>
          <SelectContent>
            {datasDisponiveis.map((d) => (
              <SelectItem key={d} value={d}>
                {formatarDataCurta(d)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <button
          type="button"
          onClick={() => onDiaChange(datasDisponiveis[idxDia + 1])}
          disabled={idxDia >= datasDisponiveis.length - 1}
          className="px-2 py-1.5 text-sm disabled:opacity-30"
          aria-label="Próximo dia"
        >
          ›
        </button>
      </div>

      <Select value={grupo} onValueChange={onGrupoChange}>
        <SelectTrigger className={`${CLASSE_SELECT} min-w-[90px]`}>
          <SelectValue placeholder="Grupo" />
        </SelectTrigger>
        <SelectContent>
          {GRUPOS_FILTRO.map((g) => (
            <SelectItem key={g} value={g}>
              {g === "TODOS" ? "Todos" : `Grupo ${g}`}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <label className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--color-border)] px-2.5 py-1.5 text-xs">
        <input
          type="checkbox"
          checked={somenteJogosDia}
          onChange={(e) => onSomenteJogosDiaChange(e.target.checked)}
          className="rounded"
        />
        Somente jogos do dia
      </label>

      <input
        type="search"
        value={busca}
        onChange={(e) => onBuscaChange(e.target.value)}
        placeholder="Buscar seleção…"
        className="h-8 min-w-[140px] rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-2.5 text-sm"
      />
    </div>
  );
}
