from pathlib import Path


def obter_raiz_projeto() -> Path:
    return Path(__file__).resolve().parents[2]


def obter_pasta_dados_brutos() -> Path:
    return obter_raiz_projeto() / "data" / "raw"


def obter_pasta_logs() -> Path:
    return obter_raiz_projeto() / "logs"
