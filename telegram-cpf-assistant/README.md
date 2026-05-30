# telegram-cpf-assistant

Assistente pessoal via Telegram para organização de pessoa física (tarefas, notas, compras, finanças, casa, casamento, saúde e revisão semanal).

- **Single-user** (autenticado por `TELEGRAM_CHAT_ID`)
- **Local-first** (SQLite em `data/`, sem cloud)
- **Sem LLM**, sem webhook público, sem integrações externas

> Estado atual: Fases 0, 1, 2 e 1.5 (fusão com o `garmin-dashboard`). Além de
> `/start`, `/help` e `/ping`, o domínio **Garmin** está portado: comandos
> `/garmin*`, SQLite com tabelas `garmin_*`, scheduler com jobs de sync,
> relatórios matinal/vespertino/semanal e alertas reativos.

## Requisitos

- Python 3.11+
- Conta no Telegram + bot criado via [@BotFather](https://t.me/BotFather)
- Windows 10/11 (alvo principal) ou Linux/macOS

## Setup (Windows)

1. Clone o projeto e entre na pasta:
   ```cmd
   git clone <repo-url>
   cd telegram-cpf-assistant
   ```

2. Crie e ative o virtualenv:
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Instale as dependências:
   ```cmd
   pip install -r requirements.txt
   ```

4. Copie o `.env.example` para `.env` e preencha:
   ```cmd
   copy .env.example .env
   notepad .env
   ```

   Variáveis:
   - `TELEGRAM_BOT_TOKEN` — token recebido do [@BotFather](https://t.me/BotFather) ao criar o bot.
     **Use o MESMO token que o `garmin-dashboard` usa hoje** (ver "Cutover" abaixo).
   - `TELEGRAM_CHAT_ID` — seu chat id pessoal. Descubra com [@userinfobot](https://t.me/userinfobot).
   - `TIMEZONE` — padrão `America/Sao_Paulo`.
   - `DATABASE_PATH` — caminho do SQLite.
   - `LOG_LEVEL` — `INFO`, `DEBUG`, `WARNING` ou `ERROR`.
   - `GARMIN_TOKEN_DIR` — diretório do cache de token do Garmin (padrão
     `./data/garmin_session`). Copie o conteúdo de `~/.garminconnect/` para cá
     para reaproveitar a sessão sem refazer 2FA.
   - `GARMIN_EMAIL` / `GARMIN_PASSWORD` — só preencher se não houver cache de
     token (login fresco no Garmin Connect).

5b. Inicialize o banco (cria/atualiza o schema SQLite):
   ```cmd
   python -m app.database --init
   ```

5. Garanta UTF-8 no terminal (acentos e emojis):
   ```cmd
   chcp 65001
   ```

6. Rode o bot:
   ```cmd
   python -m app.main
   ```

7. No Telegram, abra a conversa com o seu bot e mande `/start`. Deve responder. `/ping` retorna o uptime.

## Setup (Linux/macOS)

Mesmos passos, com `python3 -m venv .venv` e `source .venv/bin/activate`.

## Como descobrir seu `TELEGRAM_CHAT_ID`

1. Abra o Telegram, busque por `@userinfobot` e inicie a conversa.
2. Ele responde com o seu user id (número inteiro). É esse o valor.
3. Cole no `.env` em `TELEGRAM_CHAT_ID=`.

> Observação: o bot só responde ao chat id configurado. Qualquer mensagem de outro chat é descartada silenciosamente (com `WARNING` no log).

## Comandos disponíveis (Fase 1)

| Comando | Comportamento |
|---|---|
| `/start` | Confirma que o bot está online. |
| `/help` | Lista comandos atuais e os planejados para as próximas fases. |
| `/ping` | Responde `pong — uptime XhYYm`. |

### Comandos Garmin (Fase 1.5)

| Comando | Comportamento |
|---|---|
| `/garmin` | Resumo de hoje: sono, body battery, readiness, passos, último treino. |
| `/garmin_sono` | Detalhe do sono da última noite (fases, score, HRV). |
| `/garmin_hrv` | Tendência de HRV dos últimos 7 dias. |
| `/garmin_treino [id]` | Último treino completo (ou um específico por id). |
| `/garmin_treinos [n]` | Lista dos últimos N treinos (padrão 7). |
| `/garmin_corpo` | Última composição corporal + variação de peso. |
| `/garmin_peso <valor>` | Registra peso manual (`source = manual`). |
| `/garmin_status` | Training status + readiness + carga aguda/crônica. |
| `/garmin_semana` | Resumo Garmin da semana. |
| `/garmin_sync` | Força sincronização imediata com o Garmin Connect. |

Os comandos `/garmin*` leem sempre do SQLite local; a sincronização com a API
do Garmin acontece nos jobs agendados (e via `/garmin_sync`).

**Jobs Garmin no scheduler** (fuso `America/Sao_Paulo`):

| Job | Horário | Conteúdo |
|---|---|---|
| `garmin_sync_morning` | 06:30 diário | Puxa dados (noite + dia) para o SQLite. Sem envio. |
| `garmin_morning_report` | 07:30 diário | Relatório matinal (sono, body battery, readiness). |
| `garmin_evening_report` | 19:00 diário | Recap do dia (passos, kcal, stress, treino). |
| `garmin_alerts` | 08/14/20h | Alertas reativos (HRV em queda, sono curto, body battery baixa). Só envia se disparar. |
| `garmin_weekly` | Domingo 17:55 | Bloco semanal Garmin. |

Comandos das próximas fases (tarefas, notas, compras, finanças, casamento, saúde, revisão semanal) estão documentados no plano de design e serão habilitados conforme cada fase for implementada.

## Estrutura do projeto

```
telegram-cpf-assistant/
├── app/
│   ├── main.py           # entrypoint
│   ├── config.py         # Settings via python-dotenv
│   ├── bot.py            # handlers /start /help /ping
│   ├── security.py       # @authorized_only
│   ├── logger.py         # logging rotativo
│   ├── handlers/         # (próximas fases) handlers por domínio
│   ├── services/         # (próximas fases) regras de negócio
│   ├── repositories/     # (próximas fases) acesso ao SQLite
│   ├── jobs/             # (próximas fases) mensagens agendadas
│   └── exporters/        # (fase 8) Excel
├── data/                 # SQLite + backups (gitignored)
├── logs/                 # app.log rotativo (gitignored)
├── migrations/           # SQL versionado (próxima fase)
├── tests/                # pytest
├── .env.example
├── requirements.txt
└── README.md
```

## Rodar no startup do Windows (opcional)

1. Crie um `.bat` em `scripts/run.bat` com:
   ```bat
   @echo off
   cd /d C:\caminho\para\telegram-cpf-assistant
   call .venv\Scripts\activate
   python -m app.main
   ```
2. Abra o Agendador de Tarefas (`taskschd.msc`), crie uma tarefa que executa o `.bat` no logon.

> Atenção: o bot só dispara mensagens agendadas (próximas fases) enquanto o PC estiver ligado e o processo rodando.

## Logs

- Arquivo: `logs/app.log` (rotação 5MB × 5 arquivos).
- Nível controlado por `LOG_LEVEL` no `.env`.
- Nunca logamos token; o resumo de configuração em log mostra `TOKEN[:4]...[-4:]` mascarado.

## Segurança

- `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` vivem **apenas** no `.env`, nunca commitado (`.gitignore` cobre).
- Bot ignora qualquer update cujo `chat_id` não bate com `TELEGRAM_CHAT_ID`.
- Logs de configuração usam `.redacted()` — token nunca aparece em texto pleno.
- Nenhuma integração externa nesta versão (sem chamadas a APIs de terceiros, sem webhook público).
- SQLite e backups ficam apenas no disco local.

## Troubleshooting

| Sintoma | Causa provável | Ação |
|---|---|---|
| `Missing required environment variables` na inicialização | `.env` não preenchido | Copiar `.env.example` para `.env` e preencher. |
| `Conflict: terminated by other getUpdates` | Outra instância do bot rodando | Encerrar o processo anterior (Task Manager / `pkill -f app.main`). |
| Bot online mas não responde | `TELEGRAM_CHAT_ID` errado | Conferir com `@userinfobot` e checar `logs/app.log` por `unauthorized chat_id=...`. |
| Acentos quebrados no terminal | Code page do Windows | `chcp 65001` antes de rodar. |
| Mensagem de erro `pong — uptime ...` não chega | Token inválido ou bot bloqueado | Verificar token no `.env` e abrir a conversa com o bot. |

## Cutover do garmin-dashboard

O `telegram-cpf-assistant` absorve o domínio Garmin que hoje roda no
`joaopdavila/garmin-dashboard` (briefings matinal/vespertino + alertas via
GitHub Actions). A migração é manual e **não apaga nada** do garmin-dashboard —
a aposentadoria é decisão sua, após validar a paridade.

### Token único

O bot unificado usa o **mesmo `TELEGRAM_BOT_TOKEN`** do garmin-dashboard. Dois
processos diferentes com o mesmo token brigam pelo polling
(`Conflict: terminated by other getUpdates`), então **só um pode estar ativo
por vez**.

> Se quiser rodar os dois em paralelo durante a validação, use um **bot/token de
> teste separado** (outro bot do @BotFather) no cpf-assistant; não aponte os
> dois para o mesmo token ao mesmo tempo.

### Reaproveitar a sessão Garmin (evitar 2FA)

1. Localize o cache de token usado hoje pelo garmin-dashboard: `~/.garminconnect/`.
2. Copie o conteúdo para o `GARMIN_TOKEN_DIR` do cpf-assistant
   (padrão `./data/garmin_session/`):
   ```cmd
   xcopy /E /I "%USERPROFILE%\.garminconnect" "data\garmin_session"
   ```
   (Linux/macOS: `cp -r ~/.garminconnect/. data/garmin_session/`.)
3. Se não houver cache, preencha `GARMIN_EMAIL`/`GARMIN_PASSWORD` no `.env` — o
   primeiro start faz login fresco e salva o cache em `GARMIN_TOKEN_DIR`.

### Importar dados históricos de peso/composição

```cmd
python migrations/scripts/import_garmin_legacy.py --source-dir ..\garmin-dashboard
```

Lê `inbody_data.csv`, `relaxmedic_data.csv` e `apple_health_weight.json` do
checkout do garmin-dashboard e popula `garmin_body_composition`. Tolerante a
falhas (linhas com erro vão para `data/garmin_import_errors.log`). Use
`--dry-run` para conferir antes.

### Passos do cutover

1. **Parar o garmin-dashboard.** Desabilite os workflows agendados em
   `garmin-dashboard/.github/workflows/` (`daily-briefing.yml`, `alerts.yml`)
   ou pause o repositório. Isso evita o conflito de polling e mensagens duplicadas.
2. (Opcional) **1 semana de overlap em teste.** Com um token de teste, rode o
   cpf-assistant em paralelo por ~1 semana e compare as mensagens com as do
   garmin-dashboard antes de desligar o original.
3. **Iniciar o cpf-assistant** com o token de produção:
   ```cmd
   python -m app.database --init
   python -m app.main
   ```
4. **Validar paridade** com o checklist abaixo.
5. Só então aposente o garmin-dashboard de vez (manter o repo para histórico).

### Checklist de paridade

- [ ] Mensagem **matinal** (`garmin_morning_report`, 07:30) chega com sono,
      body battery e readiness.
- [ ] Mensagem **vespertina** (`garmin_evening_report`, 19:00) chega com passos,
      kcal, stress e treino do dia.
- [ ] Bloco **semanal** (`garmin_weekly`, domingo) chega com sono médio, HRV,
      treinos, distância e peso.
- [ ] **Alertas** (`garmin_alerts`) disparam só quando HRV cai 3 noites, sono
      < 6h por 2 noites, ou body battery < 30.
- [ ] `/garmin` e demais `/garmin*` respondem com dados reais.
- [ ] `/garmin_sync` atualiza as tabelas `garmin_*`.

> Diferença esperada: as mensagens do cpf-assistant são em **PT-BR seco, sem
> emoji** (convenção do projeto), enquanto o garmin-dashboard usava emoji +
> Markdown. O conteúdo é equivalente.

## Roadmap

Implementação em fases (ver plano de design completo):

- **Fase 0** ✅ Setup do projeto.
- **Fase 1** ✅ Bot mínimo com gate de segurança.
- **Fase 1.5** ✅ Fusão com o garmin-dashboard (domínio Garmin).
- **Fase 2** ✅ SQLite + repositórios base.
- **Fase 6** ✅ Scheduler (jobs Garmin; demais jobs nas próximas fases).
- **Fase 3** Tarefas e notas.
- **Fase 4** Compras e finanças.
- **Fase 5** Check-in e fechamento manuais.
- **Fase 6** Scheduler (mensagens automáticas).
- **Fase 7** Revisão semanal, casamento, saúde estendida.
- **Fase 8** Exportação Excel + backup.
- **Fase 9** Testes e hardening.

## Licença

Uso pessoal.
