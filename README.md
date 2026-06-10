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

## Atualização automática de odds (GA% / SG%)

As odds dos jogadores são raspadas **localmente** (Playwright + Chromium) e commitadas no repositório. O GitHub Actions não roda mais em cron — evita falhas por Cloudflare no runner headless.

### Setup (uma vez)

```powershell
cd C:\caminho\para\datacfc_wc2026
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-odds.txt
playwright install chromium
```

### Testar manualmente

```powershell
powershell -ExecutionPolicy Bypass -File automation\atualizar_odds.ps1
```

### Agendar 6×/dia (Agendador de Tarefas)

Execute **como Administrador**:

```powershell
powershell -ExecutionPolicy Bypass -File automation\registrar_tarefa_odds.ps1
```

Horários padrão (hora local): 06h, 09h, 12h, 15h, 18h, 21h.

Logs em `logs/atualizar_odds/`.
