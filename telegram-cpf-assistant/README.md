# telegram-cpf-assistant

Assistente pessoal via Telegram para organização de pessoa física (tarefas, notas, compras, finanças, casa, casamento, saúde e revisão semanal).

- **Single-user** (autenticado por `TELEGRAM_CHAT_ID`)
- **Local-first** (SQLite em `data/`, sem cloud)
- **Sem LLM**, sem webhook público, sem integrações externas

> Estado atual: Fase 0 + Fase 1 do plano de implementação (ver `../.../voc-um-arquiteto-eventual-wind.md`). Apenas `/start`, `/help` e `/ping` estão funcionais.

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
   - `TELEGRAM_CHAT_ID` — seu chat id pessoal. Descubra com [@userinfobot](https://t.me/userinfobot).
   - `TIMEZONE` — padrão `America/Sao_Paulo`.
   - `DATABASE_PATH` — caminho do SQLite (criado nas próximas fases).
   - `LOG_LEVEL` — `INFO`, `DEBUG`, `WARNING` ou `ERROR`.

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

## Roadmap

Implementação em fases (ver plano de design completo):

- **Fase 0** ✅ Setup do projeto.
- **Fase 1** ✅ Bot mínimo com gate de segurança.
- **Fase 2** SQLite + repositórios base.
- **Fase 3** Tarefas e notas.
- **Fase 4** Compras e finanças.
- **Fase 5** Check-in e fechamento manuais.
- **Fase 6** Scheduler (mensagens automáticas).
- **Fase 7** Revisão semanal, casamento, saúde estendida.
- **Fase 8** Exportação Excel + backup.
- **Fase 9** Testes e hardening.

## Licença

Uso pessoal.
