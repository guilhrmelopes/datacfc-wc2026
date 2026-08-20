# Data CFC — Copa do Mundo 2026

**Status: arquivado (demo congelada).** A Copa 2026 acabou; os dados não são mais atualizados. O site permanece no ar como case study.

**Demo:** [datacfc-wc2026.vercel.app](https://datacfc-wc2026.vercel.app) · **Repo:** [guilhrmelopes/datacfc-wc2026](https://github.com/guilhrmelopes/datacfc-wc2026)

Dashboard de análise para quem joga **Cartola FC** na Copa: scouts de seleções e jogadores, classificação, mata-mata e contexto de odds (GA% / SG%) num só lugar.

## O que o produto faz

| Aba | Conteúdo |
|-----|----------|
| **Fase de Grupos** | Classificação dos grupos A–L |
| **Mata-mata** | Chave / bracket até a final |
| **HUB Seleções** | Scouts coletivos (gols, posse, xG, desarmes, etc.) e recorrência |
| **HUB Jogadores** | Rankings por posição (GOL, LAT, ZAG, MEI, ATA), ratings, próximo adversário, odds e cobradores |

## Stack

- **Frontend:** React 19, Vite 6, TypeScript, Tailwind CSS 4, Radix UI
- **Dados:** Python 3.12, Playwright (odds), PowerShell automation
- **Deploy:** GitHub Actions → commit de JSONs → Vercel

## Arquitetura (visão geral)

```mermaid
flowchart LR
  FotMob[FotMob] --> Pipeline[Pipeline Python]
  Cartola[Cartola / Prováveis] --> Pipeline
  Odds[OddsHub Playwright] --> Pipeline
  Pipeline --> JSON[frontend/public/data]
  JSON --> SPA[SPA React]
  SPA --> Vercel[Vercel]
```

Detalhes em [ARCHITECTURE.md](ARCHITECTURE.md).

## Como rodar localmente (dev)

```powershell
cd frontend
npm install
npm run dev
```

Os JSONs já estão em `frontend/public/data/`. O pipeline Python / scrapers ficam no repo para referência histórica; **não há mais agenda automática** (cron desligado).

## Licença / uso

Projeto pessoal / portfólio. Fontes de dados de terceiros (FotMob, Cartola, etc.) sujeitas aos termos de cada provedor.
