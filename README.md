# Data CFC — Copa do Mundo 2026

Dashboard de análise de seleções e jogadores para a Copa do Mundo 2026.

## Funcionalidades

- **HUB Seleções** — scouts coletivos por seleção (gols, posse, xG, desarmes e muito mais) com formatação condicional por faixa de desempenho
- **Fase de Grupos** — classificação ao vivo dos grupos A–L
- **HUB Jogadores** — ranking de jogadores por posição (GOL, LAT, ZAG, MEI, ATA) com métricas de performance e próximo adversário

## Tecnologias

- [React 19](https://react.dev/) + [Vite 6](https://vitejs.dev/)
- [TypeScript](https://www.typescriptlang.org/)
- [Tailwind CSS 4](https://tailwindcss.com/)
- [Radix UI](https://www.radix-ui.com/)

## Atualização automática de dados

Todo o fluxo (Copa, scouts, pontuações, odds e deploy) pode rodar **localmente** ou **na nuvem** (GitHub Actions).

### O que é atualizado

| Etapa | Fonte | Arquivos |
|-------|--------|----------|
| Copa (classificação, hub, cedido/conquistado) | FotMob API | `copa_estado.json`, `grupos_wc2026.json`, `classificacao_grupos.json`, `pontuacao_cedida.json`, `selecoes.json`, `jogadores_mercado.json` |
| Status e fotos | Prováveis do Cartola | `jogadores_mercado.json` |
| Odds GA% / SG% | Playwright (local) | `odds_jogadores.json`, `eventos_odds_rodada1.json` |

O **deploy** ocorre automaticamente via **push → Vercel** quando há mudanças nos JSONs.

### Setup (uma vez)

```powershell
cd C:\caminho\para\datacfc_wc2026
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-odds.txt
playwright install chromium
```

### Atualizar tudo manualmente (recomendado)

```powershell
powershell -ExecutionPolicy Bypass -File automation\atualizar_tudo.ps1
```

Sem odds (só Copa + status):

```powershell
powershell -ExecutionPolicy Bypass -File automation\atualizar_tudo.ps1 -SkipOdds
```

Sem push (testar localmente):

```powershell
powershell -ExecutionPolicy Bypass -File automation\atualizar_tudo.ps1 -SkipPush
```

### Agendar automaticamente (Windows)

Registra **Copa a cada 30 min** + **atualização completa 6×/dia**:

```powershell
powershell -ExecutionPolicy Bypass -File automation\registrar_agenda_completa.ps1
```

Horários completos (hora local): 06h, 09h, 12h, 15h, 18h, 21h.

Logs: `logs/atualizar_tudo/` e `logs/atualizar_copa/`.

### GitHub Actions (nuvem)

| Workflow | Frequência | Conteúdo |
|----------|------------|----------|
| `update-copa.yml` | A cada 30 min | Copa + status → push → Vercel |
| `update-status.yml` | 3×/dia | Status e fotos |
| `update-odds.yml` | Manual | Odds (emergência — Cloudflare no runner) |

Odds continuam sendo raspadas **localmente** (Playwright + Chromium) — o runner do GitHub costuma ser bloqueado.

### Scripts individuais

```powershell
powershell -ExecutionPolicy Bypass -File automation\atualizar_copa.ps1
powershell -ExecutionPolicy Bypass -File automation\atualizar_odds.ps1
```

