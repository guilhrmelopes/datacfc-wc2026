import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { COMPETICOES_FILTRO } from "@/lib/traducoes";

export const GRUPOS_FILTRO = [
  "TODOS",
  "A",
  "B",
  "C",
  "D",
  "E",
  "F",
  "G",
  "H",
  "I",
  "J",
  "K",
  "L",
] as const;

const CLASSE_SELECT_COMPACTO = "h-8 min-w-[130px] text-sm";

interface Props {
  competicao: string;
  grupo: string;
  onCompeticaoChange: (valor: string) => void;
  onGrupoChange: (valor: string) => void;
}

export function FiltrosScouts({
  competicao,
  grupo,
  onCompeticaoChange,
  onGrupoChange,
}: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select value={competicao} onValueChange={onCompeticaoChange}>
        <SelectTrigger className={CLASSE_SELECT_COMPACTO}>
          <SelectValue placeholder="Competição" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="TODAS">Todas</SelectItem>
          {COMPETICOES_FILTRO.map((c) => (
            <SelectItem key={c} value={c}>
              {c}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={grupo} onValueChange={onGrupoChange}>
        <SelectTrigger className={`${CLASSE_SELECT_COMPACTO} min-w-[90px]`}>
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
    </div>
  );
}
