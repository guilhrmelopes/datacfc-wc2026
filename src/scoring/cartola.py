"""Regras de pontuação Cartola FC Copa — scouts e cedido/conquistado."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Bucket = Literal["GOL", "LAT", "ZAG", "MEI", "ATA"]
BUCKETS: tuple[Bucket, ...] = ("GOL", "LAT", "ZAG", "MEI", "ATA")
BUCKETS_SG: frozenset[Bucket] = frozenset({"GOL", "LAT", "ZAG"})

PONTOS: dict[str, float] = {
    "G": 8.0,
    "A": 5.0,
    "FT": 3.0,
    "FD": 1.2,
    "FF": 0.8,
    "FS": 0.5,
    "PS": 1.0,
    "PP": -4.0,
    "I": -0.1,
    "SG": 5.0,
    "DP": 7.0,
    "DE": 1.3,
    "DS": 1.5,
    "GC": -3.0,
    "CV": -3.0,
    "CA": -1.0,
    "GS": -1.0,
    "FC": -0.3,
    "PC": -1.0,
}


@dataclass
class ScoutsPartida:
    """Contagens brutas de scouts mapeados do FotMob."""

    minutos: int = 0
    G: int = 0
    A: int = 0
    FT: int = 0
    FD: int = 0
    FF: int = 0
    FS: int = 0
    PS: int = 0
    PP: int = 0
    I: int = 0
    SG: int = 0
    DP: int = 0
    DE: int = 0
    DS: int = 0
    GC: int = 0
    CV: int = 0
    CA: int = 0
    GS: int = 0
    FC: int = 0
    PC: int = 0
    INT: int = 0
    C: int = 0
    BR: int = 0
    GE: float = 0.0
    GCC: int = 0


@dataclass
class PerformanceBucket:
    cedido: float | None
    conquistado: float | None


def calcular_medias_copa(
    total_pontos: float,
    jogos: int,
    scouts: ScoutsPartida,
    bucket: Bucket,
) -> tuple[float | None, float | None]:
    """MG e MB por jogo (Cartola): total de pontos / J; MB exclui G, A e SG."""
    if jogos <= 0:
        return None, None
    mg = round(total_pontos / jogos, 2)
    bonus = scouts.G * PONTOS["G"] + scouts.A * PONTOS["A"]
    if bucket in BUCKETS_SG:
        bonus += scouts.SG * PONTOS["SG"]
    mb = round((total_pontos - bonus) / jogos, 2)
    return mg, mb


def calcular_pontos(scouts: ScoutsPartida, bucket: Bucket) -> float:
    total = 0.0
    for chave, peso in PONTOS.items():
        qtd = getattr(scouts, chave, 0) or 0
        if qtd == 0:
            continue
        if chave == "SG" and bucket not in BUCKETS_SG:
            continue
        if chave in ("DE", "DP", "GS") and bucket != "GOL":
            continue
        total += qtd * peso
    return round(total, 2)


def somar_scouts(destino: ScoutsPartida, origem: ScoutsPartida) -> None:
    for campo in ScoutsPartida.__dataclass_fields__:
        setattr(destino, campo, getattr(destino, campo) + getattr(origem, campo))


def cor_performance(valor: float) -> str:
    if valor <= 2.5:
        return "bg-red-500"
    if valor <= 3.99:
        return "bg-orange-500"
    if valor <= 5.5:
        return "bg-yellow-500"
    return "bg-green-500"


def celula_pontuacao(valor: float | None) -> dict:
    if valor is None:
        return {"valor": None, "cor": "bg-gray-300"}
    return {"valor": round(valor, 2), "cor": cor_performance(valor)}


def media_bucket(pontos: list[float], *, padrao_se_vazio: float | None = None) -> float | None:
    if not pontos:
        return padrao_se_vazio
    return round(sum(pontos) / len(pontos), 2)


@dataclass
class AcumuladorCedidoConquistado:
    """Média acumulada por bucket ao longo das partidas."""

    conquistado: dict[Bucket, list[float]] = field(
        default_factory=lambda: {b: [] for b in BUCKETS}
    )
    cedido: dict[Bucket, list[float]] = field(
        default_factory=lambda: {b: [] for b in BUCKETS}
    )

    def registrar_partida(
        self,
        conquistado_partida: dict[Bucket, float | None],
        cedido_partida: dict[Bucket, float | None],
    ) -> None:
        for bucket in BUCKETS:
            c = conquistado_partida.get(bucket)
            d = cedido_partida.get(bucket)
            if c is not None:
                self.conquistado[bucket].append(c)
            if d is not None:
                self.cedido[bucket].append(d)

    def exportar(self) -> dict[str, dict[str, dict]]:
        jogou = any(self.conquistado[b] or self.cedido[b] for b in BUCKETS)
        padrao = 0.0 if jogou else None
        out: dict[str, dict[str, dict]] = {}
        for bucket in BUCKETS:
            out[bucket] = {
                "cedido": celula_pontuacao(
                    media_bucket(self.cedido[bucket], padrao_se_vazio=padrao),
                ),
                "conquistado": celula_pontuacao(
                    media_bucket(self.conquistado[bucket], padrao_se_vazio=padrao),
                ),
            }
        return out


def calcular_cedido_conquistado_partida(
    pontos_por_sigla_bucket: dict[str, dict[Bucket, list[float]]],
    sigla_mandante: str,
    sigla_visitante: str,
) -> tuple[dict[str, dict[Bucket, float | None]], dict[str, dict[Bucket, float | None]]]:
    """
    Retorna (conquistado, cedido) por sigla e bucket para uma partida.
    Conquistado = média dos pontos do próprio time no bucket.
    Cedido = média dos pontos do adversário no mesmo bucket.
    """
    conquistado: dict[str, dict[Bucket, float | None]] = {
        sigla_mandante: {},
        sigla_visitante: {},
    }
    cedido: dict[str, dict[Bucket, float | None]] = {
        sigla_mandante: {},
        sigla_visitante: {},
    }

    avg_m = {b: media_bucket(pontos_por_sigla_bucket[sigla_mandante].get(b, [])) for b in BUCKETS}
    avg_v = {b: media_bucket(pontos_por_sigla_bucket[sigla_visitante].get(b, [])) for b in BUCKETS}

    for bucket in BUCKETS:
        conquistado[sigla_mandante][bucket] = avg_m[bucket]
        conquistado[sigla_visitante][bucket] = avg_v[bucket]
        cedido[sigla_mandante][bucket] = avg_v[bucket]
        cedido[sigla_visitante][bucket] = avg_m[bucket]

    return conquistado, cedido
