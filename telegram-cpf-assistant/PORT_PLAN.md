# Port plan — garmin-dashboard → telegram-cpf-assistant (Fase 1.5)

> Levantamento read-only do repo `joaopdavila/garmin-dashboard` e mapeamento
> para os módulos planejados na `### Fase 1.5` do `DESIGN.md`. A arquitetura
> não foi redesenhada — este documento só registra o que existe hoje e como
> cada peça é portada.

## a) Auth no Garmin Connect

- **Lib:** [`garminconnect`](https://pypi.org/project/garminconnect/) (`>=0.2.25`),
  que por baixo usa `garth` (OAuth). **Não** é `garth` puro nem `requests`
  manual.
- **Persistência de token:** cache OAuth em `~/.garminconnect/` (`Path.home() / ".garminconnect"`,
  constante `TOKENSTORE` em `garmin_client.py`). O fluxo é:
  1. Se o cache existe, `Garmin().login(str(TOKENSTORE))` resume a sessão (sem 2FA).
  2. Se falha/expira, faz login fresco com `GARMIN_EMAIL`/`GARMIN_PASSWORD` e
     tenta re-salvar o cache via `garth.dump` / `dump_tokens` / `dump` / `garth.save`
     (best-effort, tolerante a mudança de API entre versões).
- **Bootstrap manual:** `auth.py` roda uma vez para criar o cache.
- **Consequência para o port:** reaproveitar o cache existente para **evitar
  re-2FA**. No cpf-assistant o diretório de tokens passa a ser configurável via
  `GARMIN_TOKEN_DIR` (default `./data/garmin_session`); o usuário copia o
  conteúdo de `~/.garminconnect/` para lá no cutover. `GARMIN_EMAIL`/`GARMIN_PASSWORD`
  ficam opcionais (só usados se o cache faltar/expirar).

## b) Envio de mensagens no Telegram (hoje)

- **Lib:** `requests` puro — `POST https://api.telegram.org/bot<token>/sendMessage`
  (funções `send_telegram()` idênticas em `daily_summary.py` e `alerts.py`).
- **Token / chat:** `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` lidos do ambiente
  (secrets do GitHub Actions). **Esse é o token que passa a ser o único do bot
  unificado.**
- **Formato:** `parse_mode=Markdown`, `disable_web_page_preview=True`, emoji-rich.
  - **Decisão (usuário):** no port as mensagens viram **PT-BR seco, sem emoji e
    sem Markdown** (texto puro via `bot.send_message`), alinhado à convenção do
    cpf-assistant. Conteúdo/semântica preservados; só o visual muda.

## c) Scheduler atual

- **Não há scheduler no processo.** Tudo roda como **GitHub Actions cron**:
  - `.github/workflows/daily-briefing.yml`:
    - `0 10 * * *` (07:00 BRT) → `daily_summary.py --mode=morning`
    - `0 22 * * *` (19:00 BRT nominal; na prática 22–23h por delay do GH Actions)
      → `daily_summary.py --mode=evening`
  - `.github/workflows/alerts.yml`:
    - `0 11,17,23 * * *` (08:00 / 14:00 / 20:00 BRT) → `alerts.py`
- **Consequência:** no cpf-assistant esses crons viram jobs APScheduler no
  scheduler único (`app/scheduler.py`, Fase 6), com horários **exatos** em
  `America/Sao_Paulo` (sem o delay do GH Actions).

## d) Onde os dados ficam

- **Não há SQLite nem banco local.** A **fonte de verdade é o próprio Garmin
  Connect** (API live). Peso/composição histórica é *enviada* ao Garmin via
  `import_weight.py` / `import_inbody.py`.
- Exports pontuais de JSON vão para `./data/garmin_export_*.json` (gitignored);
  o `health_mcp.py` lê esses exports. `health_mcp.py` é o servidor MCP
  `health-data` (consumido pela skill `garmin-coach`) — **fora do escopo deste
  port**.
- **Dados legados em arquivo** (candidatos a migração para `garmin_body_composition`):
  - `inbody_data.csv` — 21 medições InBody/balança 2016–2025
    (`date,weight_kg,fat_pct,muscle_kg,fat_kg,source`).
  - `relaxmedic_data.csv` — bioimpedância Relaxmedic
    (`date,time,weight_kg,fat_pct,muscle_kg,bone_kg,hydration_pct,visceral_fat_rating,metabolic_age,bmi`).
  - `apple_health_weight.json` — export Apple Health (peso + gordura%).
- **Consequência:** no cpf-assistant os dados Garmin passam a ser **persistidos
  em SQLite** (tabelas `garmin_*`) pelos jobs de sync; os handlers leem do
  SQLite (sem chamar a API no caminho síncrono, conforme critério de aceite da
  Fase 1.5). Os arquivos legados acima são importados uma vez para
  `garmin_body_composition` via `migrations/scripts/import_garmin_legacy.py`.

## e) Mensagens / jobs existentes

| Origem | Trigger (BRT) | Conteúdo | Envio |
|---|---|---|---|
| `daily_summary.py --mode=morning` | 07:00 diário | Readiness, HRV, sono (fases+score), daily summary (BB, passos, stress, RHR), atividade de ontem; cada métrica com delta vs média 7d | Sempre |
| `daily_summary.py --mode=evening` | 19:00 diário | Recap do dia (passos, kcal ativas, stress médio, BB), atividade de hoje, alvo de sono / hora de dormir | Sempre |
| `alerts.py` | 08:00 / 14:00 / 20:00 | HRV em queda 3 noites + < baseline low; sono < 6h em 2 noites; body battery < 30 | **Só se alguma condição disparar** (silêncio = tudo normal) |

## f) Mapeamento arquivo → módulo planejado (Fase 1.5)

| garmin-dashboard | telegram-cpf-assistant | Observação |
|---|---|---|
| `garmin_client.py` (classe `GarminClient`, auth + endpoints) | `app/clients/garmin_client.py` | Porta a auth com cache; `TOKENSTORE` → `GARMIN_TOKEN_DIR`. Métodos finos preservados. |
| `auth.py` (bootstrap) | doc no README (`python -m app.clients.garmin_client --auth` opcional) | Bootstrap manual de token. |
| `daily_summary.py` builders + collectors (readiness/HRV/sono/summary/atividade, delta 7d) | `app/services/garmin_service.py` + `app/jobs/garmin_morning_report.py` / `garmin_evening_report.py` | Lógica de parse/formatação migra para o service (lendo do SQLite). |
| `daily_summary.py` `send_telegram()` | `context.bot.send_message(...)` nos jobs | Passa a usar o `Application` único. |
| `alerts.py` (3 checks reativos) | `app/jobs/garmin_alerts.py` | **Portado como 5º job** (decisão do usuário). |
| `import_weight.py` / `import_inbody.py` (upload p/ Garmin) | `migrations/scripts/import_garmin_legacy.py` | Reaproveita os parsers de CSV/JSON, mas **escreve no SQLite** local em vez de enviar ao Garmin. |
| `inbody_data.csv`, `relaxmedic_data.csv`, `apple_health_weight.json` | entrada do importador legado | Dados históricos de composição corporal. |
| `health_mcp.py`, `generate_dashboard.py`, `generate_body_chart.py`, `*.html`, `render.yaml`, `Dockerfile`, `setup.py` | — | **Fora de escopo.** MCP `health-data` e dashboards HTML continuam no garmin-dashboard. |

Novos módulos (sem origem direta, conforme Fase 1.5):
`app/repositories/garmin_repo.py`, `app/handlers/garmin.py`,
`app/jobs/garmin_sync_morning.py`, `app/jobs/garmin_weekly.py`,
`migrations/00X_garmin.sql`.

## g) Decisões necessárias

| # | Decisão | Resolução |
|---|---|---|
| 1 | Lib de auth | Manter `garminconnect` (já em uso). Sem mudança. |
| 2 | Reuso de sessão / token dir | `GARMIN_TOKEN_DIR=./data/garmin_session`; copiar `~/.garminconnect/` no cutover para evitar 2FA. `GARMIN_EMAIL`/`GARMIN_PASSWORD` opcionais. |
| 3 | Post-workout polling (`garmin_sync_postworkout`) | **Não portar** — o garmin-dashboard atual não faz polling pós-treino (só briefings + alertas). DESIGN marca como opcional "só se já fazia". |
| 4 | **Formato das mensagens** (emoji/Markdown vs seco) | **[usuário] PT-BR seco, sem emoji, sem Markdown.** |
| 5 | **Alertas reativos (`alerts.py`)** | **[usuário] Portar como 5º job** (`garmin_alerts`, 3x/dia). |
| 6 | Leitura nos handlers | Handlers leem do SQLite; sync fica nos jobs (critério de aceite Fase 1.5). |

## Ordem de execução

1. (este doc) `docs: garmin-dashboard port plan`
2. Fase 2 — SQLite: `app/database.py`, `migrations/001_init.sql`, `app/repositories/base.py`
3. `app/clients/garmin_client.py` (port da auth + endpoints)
4. `migrations/002_garmin.sql` (6 tabelas + `raw_json`)
5. `app/repositories/garmin_repo.py`, `app/services/garmin_service.py`,
   `app/handlers/garmin.py`, `app/scheduler.py`, jobs `garmin_*`
6. `migrations/scripts/import_garmin_legacy.py`
7. Token único + seção de cutover no README/DESIGN
8. Verificação + atualização do PR #1
