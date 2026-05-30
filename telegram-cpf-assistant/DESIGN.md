# telegram-cpf-assistant — Design & Plano de Implementação

> **Atualização de sessão (2026-05-30)** — antes de ler o restante:
>
> **Já feito:**
> - Fase 0 (scaffold) e Fase 1 (bot mínimo com gate de segurança) commitadas em `telegram-cpf-assistant/` na branch `claude/telegram-cpf-assistant-design-t31ZQ`.
> - PR draft #1 aberto em `joaopdavila/joaopdavila`.
> - Comandos `/start`, `/help`, `/ping` funcionais. SQLite e scheduler ainda não — vêm nas fases 2+.
>
> **Nova direção (decidida com o usuário, ainda não implementada):**
> - Unir o repo `joaopdavila/garmin-dashboard` (que já manda mensagens no Telegram) com este projeto. **Estratégia: migrar o conteúdo do `garmin-dashboard` para dentro do `telegram-cpf-assistant`** como mais um domínio (`app/handlers/garmin.py`, `app/services/garmin_service.py`, `app/jobs/garmin_*.py`, tabelas SQLite extras).
> - **Bot único, mesmo `TELEGRAM_BOT_TOKEN`** — o token usado hoje pelo Garmin passa a alimentar a central completa. O processo do Garmin é aposentado depois da fusão.
>
> **Bloqueio pendente:** a sessão atual só tem permissão GitHub para `joaopdavila/joaopdavila`. Para a próxima sessão ler o código do `garmin-dashboard`, o usuário precisa adicionar esse repo à whitelist do ambiente Claude Code on the web e iniciar uma sessão nova (a whitelist é fixada no boot do container).
>
> **Status da Fase 1.5 (arquitetura):** desenhada nesta sessão — ver seção `### Fase 1.5 — Fusão com garmin-dashboard (arquitetura)` em "Plano de implementação". Estão definidos: módulos novos (`app/handlers/garmin.py`, `app/services/garmin_service.py`, `app/clients/garmin_client.py`, `app/repositories/garmin_repo.py`, `app/jobs/garmin_*.py`), 6 tabelas SQLite (`garmin_daily`, `garmin_sleep`, `garmin_training`, `garmin_workouts`, `garmin_body_composition`, `garmin_sync_log`), ~10 comandos novos, 4–5 jobs no scheduler unificado, e como `/checkin`, `/fechamento`, `/semana` ganham contexto Garmin.
>
> **Próximo prompt sugerido para a sessão nova (após whitelist incluir `joaopdavila/garmin-dashboard`):**
> > Continue de onde paramos. A branch `claude/telegram-cpf-assistant-design-t31ZQ` (PR draft #1) tem o `telegram-cpf-assistant` com Fase 0+1 prontos e a arquitetura da Fase 1.5 desenhada em `telegram-cpf-assistant/DESIGN.md`. Sua tarefa: ler `joaopdavila/garmin-dashboard` e **portar** o código existente para dentro das casquinhas planejadas na Fase 1.5 — `app/clients/garmin_client.py` (auth + sessão), `app/services/garmin_service.py` (queries de dados), `app/jobs/garmin_*.py` (jobs já existentes). Mantenha o `TELEGRAM_BOT_TOKEN` atual do Garmin como único token. Antes de codar, abra um sub-plano em `DESIGN.md` mapeando: (1) lib de auth usada, (2) tabela/arquivos de dados atuais, (3) jobs existentes vs planejados, (4) plano de migração de dados históricos, (5) estratégia de cutover (1 semana de overlap antes de aposentar o garmin-dashboard).

---

## Context

Você quer um assistente pessoal no Telegram para organizar a sua vida de pessoa física (tarefas, finanças, casa, casamento, saúde, compras e revisão semanal). O bot precisa rodar **localmente no Windows**, ser **simples, seguro e modular**, sem dependências externas pesadas, e servir como uma interface rápida via chat — substituindo a fricção de abrir múltiplos apps.

Este documento entrega o desenho de produto, arquitetura, modelo de dados, comandos, agendamentos e plano incremental para que a implementação aconteça em fases pequenas e auditáveis. **Nenhum código é escrito nesta etapa.**

Premissas-chave levantadas:
- Repositório alvo: novo diretório/repo `telegram-cpf-assistant` (independente do `joaopdavila/joaopdavila` atual, que é o profile README).
- Usuário único (você), autenticado apenas pelo `TELEGRAM_CHAT_ID`.
- Sem LLM, sem cloud, sem integrações bancárias na v1.
- Stack fixa: Python + `python-telegram-bot` + APScheduler + SQLite + `python-dotenv`.

---

## 1. Visão geral do produto

### O que é
Um bot de Telegram pessoal, single-user, que funciona como **capture layer + lembrete inteligente + diário estruturado**. Você fala com ele em linguagem de comando (`/tarefa`, `/gasto`, `/comprar`), ele grava no SQLite local e devolve confirmações curtas. Em horários fixos, ele te empurra check-ins, fechamentos e a revisão semanal.

### Problema que resolve
- Fricção para registrar coisas pequenas (uma tarefa, um gasto, uma ideia) em apps separados.
- Falta de **rotina forçada** de check-in/fechamento diário e revisão semanal.
- Dispersão de dados pessoais entre WhatsApp, Notas, planilhas e cabeça.
- Necessidade de uma **única fonte de verdade local** (SQLite), exportável depois.

### O que **não** é (v1)
- Não é um app multi-usuário.
- Não é um sistema financeiro (não bate com banco/cartão, não concilia, não categoriza com IA).
- Não tem interface web nem dashboard gráfico.
- Não usa LLM para interpretar mensagens livres — comandos são estruturados.
- Não roda na cloud nem expõe webhook público — polling local.

### Princípios de design
1. **Capture > organize**: a prioridade é ser rápido para registrar.
2. **Comando explícito > NLP**: sem ambiguidade, sem alucinação.
3. **Local-first**: tudo num SQLite em `data/`.
4. **Idempotência**: comandos podem ser repetidos sem corromper estado.
5. **Confirmação curta**: respostas do bot em 1–3 linhas, com ID para ações futuras.

---

## 2. Proposta de MVP

### MVP obrigatório (Fase 1 → 6)
Suficiente para usar diariamente:
- Bot rodando localmente, validado por `TELEGRAM_CHAT_ID`.
- `/start`, `/help`, `/ping`.
- **Tarefas**: `/tarefa`, `/tarefas`, `/feito`, `/pendente`, `/tarefas_hoje`.
- **Notas**: `/nota`, `/notas`, `/buscar`.
- **Compras**: `/comprar`, `/compras`, `/comprado`, `/limpar_compras`.
- **Finanças básicas**: `/gasto`, `/conta`, `/contas`, `/pago`, `/financas_semana`.
- **Check-in / Fechamento**: `/checkin`, `/fechamento` manuais + jobs 08:00 e 19:30.
- **Revisão semanal**: `/semana` + job Domingo 18:00.
- Logging estruturado, SQLite persistente.

### Pós-MVP (Fase 7 → 9)
- Casamento (`/casamento`, `/casamento_pendencias`, `/casamento_pago`, `/casamento_fornecedor`).
- Saúde estendida (`/peso`, `/treino`, `/sono`, `/saude_semana`).
- `/financas_mes`, `/tarefas_semana`.
- Exportação Excel (`/export`).
- Backup automático do `.db`.

### Fora de escopo na v1
- LLM, NLP livre, classificação automática.
- Integração com Google Calendar, Outlook, Obsidian, Notion, bancos.
- Interface web / Streamlit.
- Multi-usuário.
- Deploy cloud / webhook público.
- OCR de notas fiscais.

---

## 3. Arquitetura sugerida

### Estrutura de pastas
```
telegram-cpf-assistant/
├── app/
│   ├── __init__.py
│   ├── main.py              # entrypoint: bootstrap config, db, bot, scheduler
│   ├── config.py            # carrega .env, expõe Settings (dataclass)
│   ├── bot.py               # Application do python-telegram-bot, registra handlers
│   ├── scheduler.py         # APScheduler, registra jobs em jobs/
│   ├── database.py          # conexão SQLite, migrations, factory de sessão
│   ├── security.py          # decorator @authorized_only, sanitização
│   ├── logger.py            # setup de logging (file rotativo + console)
│   ├── handlers/            # 1 arquivo por domínio
│   │   ├── __init__.py
│   │   ├── core.py          # /start, /help, /ping
│   │   ├── tasks.py
│   │   ├── notes.py
│   │   ├── shopping.py
│   │   ├── finance.py
│   │   ├── wedding.py
│   │   ├── health.py
│   │   └── review.py        # /semana
│   ├── services/            # regras de negócio (puro Python, sem Telegram)
│   │   ├── tasks_service.py
│   │   ├── notes_service.py
│   │   ├── shopping_service.py
│   │   ├── finance_service.py
│   │   ├── wedding_service.py
│   │   ├── health_service.py
│   │   └── review_service.py
│   ├── repositories/        # acesso ao SQLite (SQL cru, sem ORM)
│   │   ├── base.py
│   │   ├── tasks_repo.py
│   │   ├── notes_repo.py
│   │   └── ...
│   ├── jobs/                # 1 função por mensagem agendada
│   │   ├── morning_checkin.py
│   │   ├── midday_reminder.py
│   │   ├── evening_closing.py
│   │   ├── weekly_review.py
│   │   ├── monday_priorities.py
│   │   └── friday_finance.py
│   ├── exporters/           # Fase 8: Excel/CSV
│   │   └── excel_exporter.py
│   └── formatters.py        # helpers de formatação de respostas
├── data/
│   ├── cpf_assistant.db     # SQLite (gitignored)
│   └── backups/             # backups automáticos (gitignored)
├── logs/                    # logs rotativos (gitignored)
├── migrations/              # .sql versionados (001_init.sql, 002_xxx.sql)
├── tests/
│   ├── test_services/
│   └── test_repositories/
├── .env.example
├── .gitignore
├── requirements.txt
├── pyproject.toml           # opcional, para black/ruff
└── README.md
```

### Responsabilidades de cada módulo

| Módulo | Responsabilidade | Não faz |
|---|---|---|
| `main.py` | Bootstrap: lê config, abre DB, instancia bot e scheduler, inicia polling. | Lógica de negócio. |
| `config.py` | Lê `.env` via `python-dotenv`, expõe `Settings` tipado. Valida obrigatórios. | I/O de DB ou Telegram. |
| `bot.py` | Cria `Application`, registra handlers de `handlers/`, define error handler. | SQL ou regras de negócio. |
| `scheduler.py` | Configura APScheduler com timezone, registra jobs de `jobs/`. | Conteúdo das mensagens. |
| `database.py` | Conexão SQLite, aplica migrations de `migrations/` em ordem. | Queries de domínio. |
| `security.py` | `@authorized_only` decorator que rejeita `update.effective_chat.id != TELEGRAM_CHAT_ID`. | Outras autenticações. |
| `handlers/` | Recebe `Update`, parseia args, chama `services/`, formata resposta. **Fino.** | SQL direto. |
| `services/` | Regras de negócio. Recebe dados primitivos, chama `repositories/`. | Conhecer Telegram. |
| `repositories/` | SQL cru parametrizado. Retorna dataclasses. | Regras de negócio. |
| `jobs/` | Função `async def run(context)` que monta mensagem e envia via `context.bot`. | Receber input. |
| `formatters.py` | Funções puras: formata lista de tarefas, resumo financeiro, etc. | I/O. |

**Por que sem ORM?** SQLAlchemy é overengineering para esse volume. SQL parametrizado + dataclasses é mais simples, mais rápido e mais auditável.

---

## 4. Modelo de dados SQLite

Convenções:
- Toda tabela tem `id INTEGER PRIMARY KEY AUTOINCREMENT`, `created_at TEXT DEFAULT CURRENT_TIMESTAMP`, `updated_at TEXT`.
- Datas em ISO 8601 (`YYYY-MM-DD HH:MM:SS`), timezone `America/Sao_Paulo` (gravada como naive local).
- Status como `TEXT` com `CHECK` constraint.
- Valores monetários em `REAL` (centavos seria mais correto, mas REAL é suficiente para uso pessoal).

### `tasks`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| description | TEXT NOT NULL | |
| status | TEXT NOT NULL DEFAULT 'pending' | CHECK in ('pending','done','cancelled') |
| due_date | TEXT NULL | data alvo opcional |
| completed_at | TEXT NULL | |
| created_at | TEXT | |
| updated_at | TEXT | |

### `notes`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| content | TEXT NOT NULL | |
| tags | TEXT NULL | csv simples opcional |
| created_at | TEXT | |

Índice: `CREATE INDEX idx_notes_content ON notes(content);` (busca usa `LIKE`).

### `shopping_items`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| item | TEXT NOT NULL | |
| status | TEXT NOT NULL DEFAULT 'pending' | CHECK in ('pending','bought','removed') |
| bought_at | TEXT NULL | |
| created_at | TEXT | |

### `expenses`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| amount | REAL NOT NULL | |
| category | TEXT NOT NULL | casa/alimentação/mercado/transporte/lazer/casamento/saúde/outros |
| description | TEXT | |
| expense_date | TEXT NOT NULL DEFAULT (date('now','localtime')) | |
| created_at | TEXT | |

### `bills`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| description | TEXT NOT NULL | |
| amount | REAL NULL | opcional ao cadastrar |
| due_date | TEXT NOT NULL | |
| status | TEXT NOT NULL DEFAULT 'pending' | CHECK in ('pending','paid','overdue') |
| paid_at | TEXT NULL | |
| paid_amount | REAL NULL | |
| created_at | TEXT | |
| updated_at | TEXT | |

### `wedding_items`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| kind | TEXT NOT NULL | CHECK in ('pendencia','pagamento','fornecedor','decisao') |
| description | TEXT NOT NULL | |
| vendor | TEXT NULL | |
| amount | REAL NULL | |
| status | TEXT NOT NULL DEFAULT 'open' | CHECK in ('open','done','cancelled') |
| created_at | TEXT | |
| updated_at | TEXT | |

### `health_checkins`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| checkin_date | TEXT NOT NULL | YYYY-MM-DD |
| weight_kg | REAL NULL | |
| workout | TEXT NULL | |
| sleep_hours | REAL NULL | |
| sleep_note | TEXT NULL | |
| priority | TEXT NULL | resposta do bullet 1 do check-in |
| raw_response | TEXT NULL | mensagem livre opcional |
| created_at | TEXT | |

Índice único: `UNIQUE(checkin_date)` → um check-in por dia, atualizável.

### `daily_closings`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| closing_date | TEXT NOT NULL UNIQUE | |
| main_task_done | INTEGER | 0/1/NULL |
| had_relevant_expense | INTEGER | 0/1/NULL |
| health_done | INTEGER | 0/1/NULL |
| tomorrow_pending | TEXT NULL | |
| raw_response | TEXT NULL | |
| created_at | TEXT | |

### `scheduled_messages`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| job_name | TEXT NOT NULL | ex: 'morning_checkin' |
| sent_at | TEXT NOT NULL | |
| status | TEXT NOT NULL DEFAULT 'sent' | CHECK in ('sent','failed') |
| error | TEXT NULL | |

### `bot_interactions`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| direction | TEXT NOT NULL | CHECK in ('in','out') |
| command | TEXT NULL | |
| payload_preview | TEXT NULL | **truncado em 200 chars**, sem PII sensível |
| chat_id | TEXT | |
| created_at | TEXT | |

Tabela útil para auditoria, debug e exportação futura. **Nunca logar tokens nem valores monetários completos em texto livre.**

---

## 5. Comandos do Telegram

Convenções:
- `<arg>` obrigatório, `[arg]` opcional.
- Toda resposta inclui o `id` da entidade criada quando aplicável, para uso em comandos seguintes.
- Erros respondem com motivo curto + exemplo de uso correto.
- Comando desconhecido → "Comando não reconhecido. /help"

### Núcleo
| Comando | Sintaxe | Exemplo | Comportamento | Resposta |
|---|---|---|---|---|
| `/start` | `/start` | `/start` | Apresenta o bot, valida chat. | "Olá. Pronto. /help para ver comandos." |
| `/help` | `/help` | `/help` | Lista comandos por categoria. | Texto agrupado. |
| `/ping` | `/ping` | `/ping` | Healthcheck. | "pong — uptime Xh, db OK" |

### Tarefas
| Comando | Sintaxe | Exemplo | Comportamento | Validação |
|---|---|---|---|---|
| `/tarefa` | `/tarefa <texto>` | `/tarefa Renovar CNH` | Cria tarefa pending. | texto não vazio |
| `/tarefas` | `/tarefas` | — | Lista pending, ordenado por created_at desc, max 20. | — |
| `/tarefas_hoje` | `/tarefas_hoje` | — | Lista pending com `due_date = hoje` ou sem due_date marcadas como prioridade. | — |
| `/tarefas_semana` | `/tarefas_semana` | — | Pending da semana corrente. | — |
| `/feito` | `/feito <id>` ou `/feito <texto>` | `/feito 12` | Marca done. Se texto, busca por LIKE — se >1 match, lista e pede id. | id numérico válido ou match único |
| `/pendente` | `/pendente <id>` | `/pendente 12` | Reabre tarefa. | id válido |

### Notas
| Comando | Sintaxe | Exemplo | Comportamento |
|---|---|---|---|
| `/nota` | `/nota <texto>` | `/nota ideia: assinar revista X` | Cria nota. |
| `/notas` | `/notas [n]` | `/notas 10` | Últimas N notas (default 10). |
| `/buscar` | `/buscar <termo>` | `/buscar revista` | LIKE %termo% em content, max 20 resultados. |

### Compras
| Comando | Sintaxe | Exemplo | Comportamento |
|---|---|---|---|
| `/comprar` | `/comprar <item>` | `/comprar leite` | Adiciona pending. Se item já existe pending, não duplica e avisa. |
| `/compras` | `/compras` | — | Lista pending. |
| `/comprado` | `/comprado <id ou item>` | `/comprado leite` | Marca bought. |
| `/limpar_compras` | `/limpar_compras` | — | Marca todos bought como removed. **Pede confirmação**. |

### Finanças
| Comando | Sintaxe | Exemplo | Comportamento |
|---|---|---|---|
| `/gasto` | `/gasto <valor> <categoria> <descrição>` | `/gasto 47.90 mercado pão e leite` | Cria expense. |
| `/conta` | `/conta <descrição> <vencimento> [valor]` | `/conta luz 2026-06-10 320` | Cria bill pending. |
| `/contas` | `/contas` | — | Lista pending ordenado por due_date asc. Destaca vencidas. |
| `/pago` | `/pago <descrição ou id> [valor]` | `/pago luz 318.50` | Marca bill paid. |
| `/financas_semana` | `/financas_semana` | — | Total gasto semana corrente por categoria + contas a vencer próx 7d. |
| `/financas_mes` | `/financas_mes` | — | Idem para mês corrente (pós-MVP). |

Validações:
- valor: regex `^\d+([.,]\d{1,2})?$`, vírgula convertida em ponto.
- categoria: deve estar na lista canônica; se não, aceita mas avisa.
- vencimento: aceita `YYYY-MM-DD`, `DD/MM`, `DD/MM/YYYY`.

### Casamento
| Comando | Sintaxe | Exemplo |
|---|---|---|
| `/casamento` | `/casamento <texto>` | `/casamento confirmar buffet até sexta` |
| `/casamento_pendencias` | `/casamento_pendencias` | — |
| `/casamento_pago` | `/casamento_pago <descrição> [valor]` | `/casamento_pago entrada decoração 2500` |
| `/casamento_fornecedor` | `/casamento_fornecedor <nome> <status/obs>` | `/casamento_fornecedor Buffet X contrato assinado` |

### Saúde
| Comando | Sintaxe | Exemplo |
|---|---|---|
| `/checkin` | `/checkin` | Dispara template manual. Próxima mensagem livre é salva em `raw_response` do dia. |
| `/fechamento` | `/fechamento` | Idem para `daily_closings`. |
| `/peso` | `/peso <valor>` | `/peso 84.2` |
| `/treino` | `/treino <texto>` | `/treino corrida 6km` |
| `/sono` | `/sono <horas ou texto>` | `/sono 7.5` |
| `/saude_semana` | `/saude_semana` | Resumo: peso médio, treinos, sono médio, dias com check-in. |

### Revisão
| Comando | Sintaxe | Comportamento |
|---|---|---|
| `/semana` | `/semana` | Gera o relatório semanal sob demanda (mesmo conteúdo do job de domingo). |

### Operacional
| Comando | Sintaxe | Comportamento |
|---|---|---|
| `/export` | `/export [dominio]` | (Fase 8) Gera xlsx e envia como documento. |
| `/backup` | `/backup` | (Fase 8) Copia db para `data/backups/` com timestamp. |

---

## 6. Fluxos conversacionais principais

### 6.1 Criar tarefa
```
Usuário: /tarefa Renovar CNH até sexta
Bot:     ✓ Tarefa #14 criada: "Renovar CNH até sexta"
```
Caminho: `handlers/tasks.create()` → valida texto → `services/tasks_service.create_task()` → `repositories/tasks_repo.insert()` → retorna id → formata resposta.

### 6.2 Concluir tarefa
```
Usuário: /feito 14
Bot:     ✓ Concluída: "Renovar CNH até sexta"
```
Variante por texto:
```
Usuário: /feito renovar
Bot:     2 tarefas encontradas:
         #14 Renovar CNH até sexta
         #08 Renovar plano celular
         Use /feito <id>.
```

### 6.3 Registrar gasto
```
Usuário: /gasto 47,90 mercado pão e leite
Bot:     ✓ Gasto #102 — R$ 47,90 [mercado] "pão e leite"
         Mês corrente: R$ 1.234,56 (mercado: R$ 480,00)
```

### 6.4 Adicionar compra (com dedupe)
```
Usuário: /comprar leite
Bot:     ✓ Adicionado #33: leite. Total pending: 7

Usuário: /comprar leite
Bot:     "leite" já está na lista (#33). Nada a fazer.
```

### 6.5 Check-in matinal (job 08:00)
```
Bot 08:00: Bom dia. Check-in rápido:
           1. Prioridade pessoal de hoje:
           2. Treino planejado:
           3. Alguma pendência crítica?
           4. Algum pagamento ou tarefa da casa?

Usuário:   1. fechar deck Q2
           2. corrida 5km
           3. pagar luz
           4. -

Bot:       ✓ Check-in 27/05 registrado. Prioridade: "fechar deck Q2".
           Sugestão: /conta luz 2026-05-30 se ainda não criado.
```
Implementação: o job envia a mensagem e marca o `chat_id` como aguardando resposta de check-in (estado em memória `pending_checkin_until = now + 2h`). Próxima mensagem **não-comando** dentro da janela é parseada como `raw_response` e salva. Os bullets 1–4 são extraídos por regex simples (linha começando com `1.`/`2.` etc.). Se não houver formato, salva tudo em `raw_response`.

### 6.6 Fechamento (job 19:30)
Análogo ao check-in, com template de fechamento e tabela `daily_closings`. Janela de captura: 2h.

### 6.7 Revisão semanal (job domingo 18:00 e `/semana`)
Job monta texto único agregando:
- Tarefas: # pending, top 5 mais antigas, # concluídas na semana.
- Compras: pending count + lista.
- Finanças: total semana por categoria, contas a vencer próx 7d, contas vencidas.
- Casamento: pendências abertas.
- Saúde: dias com check-in (X/7), peso início vs fim, treinos.
- Próxima semana: convite para responder com plano (capturado em nota com tag `plano-semana`).

### 6.8 Pendência de casamento
```
Usuário: /casamento confirmar buffet até sexta
Bot:     ✓ Casamento #21 (pendência): "confirmar buffet até sexta"

Usuário: /casamento_pago entrada decoração 2500
Bot:     ✓ Pagamento registrado: "entrada decoração" R$ 2.500,00
```

---

## 7. Agendamentos (APScheduler)

Timezone: `America/Sao_Paulo`. Todos os jobs registram em `scheduled_messages` antes de enviar (audit trail).

| Job | Horário | Frequência | Mensagem (resumo) | Ação esperada | Onde salva |
|---|---|---|---|---|---|
| `morning_checkin` | 08:00 | Diário | Template check-in 4 bullets | Usuário responde texto livre nas próximas 2h | `health_checkins` (upsert por data) |
| `midday_reminder` | 12:30 | Diário | "Água + almoço leve. Tudo no rumo?" | Resposta opcional, salva em `notes` se houver | `notes` (tag `midday`) |
| `evening_closing` | 19:30 | Diário | Template fechamento 4 bullets | Usuário responde nas próximas 2h | `daily_closings` (upsert) |
| `weekly_review` | 18:00 | Domingo | Relatório semanal completo | Leitura + resposta opcional com plano | `notes` (tag `plano-semana`) |
| `monday_priorities` | 08:00 | Segunda | "Prioridades da semana? Top 3:" (após o checkin) | Responde 3 itens → cria 3 tarefas | `tasks` |
| `friday_finance` | 17:30 | Sexta | Fechamento financeiro: total semana, contas próx 7d | Leitura, possível `/pago` | — (apenas leitura) |

Configuração técnica:
- `BackgroundScheduler` com `MemoryJobStore` (jobs declarados em código, não persistidos).
- `misfire_grace_time=600` (10 min): se PC dormiu, perdoa atraso curto.
- Cada job é `async def run(application)` e usa `application.bot.send_message(chat_id=settings.TELEGRAM_CHAT_ID, ...)`.
- Falha de envio → log `ERROR` + insert em `scheduled_messages` com `status='failed'`.

---

## 8. Estratégia de simplicidade

Regras duras para a v1, para evitar overengineering:

| Não fazer | Por quê |
|---|---|
| Sem LLM / sem NLP | Comandos estruturados resolvem 100% do escopo. |
| Sem cloud / sem webhook | Polling local é suficiente, sem porta exposta. |
| Sem ORM | SQL parametrizado + dataclasses é mais simples e rápido. |
| Sem migrations framework (Alembic) | Arquivos `.sql` numerados executados em ordem com tabela `schema_version`. |
| Sem interface web | Telegram já é a UI. |
| Sem multi-usuário | Decorator `@authorized_only` checa um único `chat_id`. |
| Sem autenticação adicional | `TELEGRAM_CHAT_ID` no `.env` é o único gate. |
| Sem integração bancária / OCR | Fora de escopo até v2. |
| Sem Docker na v1 | Roda direto com `python -m app.main`. Docker fica para evolução. |
| Sem testes E2E com Telegram real | Testa `services/` e `repositories/` com SQLite em memória; handlers mockam `Update`. |
| Sem state machine complexa | Estado de "aguardando check-in" é dict em memória com expiração — simples. |
| Sem fila / sem Redis | Tudo síncrono no event loop do bot. |

Linhas mestras de qualidade:
- `ruff` + `black` opcionais, sem CI obrigatório na v1.
- Logging com `RotatingFileHandler` em `logs/app.log` (5MB × 5 arquivos).
- `.env` nunca commitado; `.env.example` com chaves vazias.
- `data/*.db` no `.gitignore`.

---

## 9. Estratégia de evolução

Roadmap pós-MVP, sem compromisso de prazo:

| Fase | Item | Esforço | Pré-requisito |
|---|---|---|---|
| v1.1 | Exportação Excel (`/export tarefas`, `/export gastos`) com `openpyxl` | S | MVP estável |
| v1.2 | Backup automático diário do `.db` (cron interno) + `/backup` manual | S | — |
| v1.3 | Dashboard local Streamlit read-only sobre o `.db` | M | Excel maduro |
| v2.0 | Integração Google Calendar (criar evento a partir de `/tarefa <texto> @amanhã 14h`) | M | OAuth local |
| v2.1 | Integração Obsidian (export de notas semanais como `.md` na vault) | S | — |
| v2.2 | Sincronizar revisão semanal em planilha Google Sheets | M | — |
| v2.3 | Classificação automática de notas/gastos com LLM local (Ollama) | L | — |
| v2.4 | Relatórios mensais em PDF (matplotlib + reportlab) | M | Excel |
| v3.0 | Deploy em servidor local (Raspberry / Mini PC) com systemd | M | Docker |
| v3.1 | Deploy cloud (Fly.io / Render) com webhook + HTTPS | M | Docker + secrets |
| v3.2 | Modo multi-usuário (você + futuro cônjuge) com isolamento por `chat_id` | L | Refatoração de schema |

---

## 10. Plano de implementação incremental

### Fase 0 — Setup do projeto
**Objetivo:** repositório vazio mas operacional.
**Cria/altera:**
- `telegram-cpf-assistant/` (novo repo ou subdiretório).
- `.gitignore` (Python + `data/`, `logs/`, `.env`).
- `.env.example` com todas as chaves esperadas vazias.
- `requirements.txt` com versões pinadas: `python-telegram-bot==21.*`, `APScheduler==3.*`, `python-dotenv==1.*`, `pandas`, `openpyxl`.
- `README.md` esqueleto.
- `app/__init__.py`, `app/config.py` (apenas leitura de `.env` + Settings dataclass).
**Critério de aceite:** `python -c "from app.config import settings; print(settings)"` imprime sem erro com `.env` preenchido.
**Teste manual:** rodar import; conferir que falta de variável obrigatória levanta exceção clara.
**Riscos:** baixo. Atenção a encoding no Windows (`utf-8` explícito em `open()`).

### Fase 1 — Bot mínimo com `/start`, `/ping` e gate de segurança
**Objetivo:** bot conectado ao Telegram, respondendo só ao chat autorizado.
**Cria/altera:**
- `app/security.py` com `authorized_only` decorator.
- `app/bot.py` com `Application.builder().token(...).build()` e handlers `/start`, `/ping`, `/help` (placeholder).
- `app/logger.py` com setup de logging rotativo.
- `app/main.py` que inicia polling.
**Critério de aceite:**
- `/start` do chat autorizado responde.
- Mensagem de chat NÃO autorizado é silenciosamente ignorada (com log `WARNING`).
- `/ping` responde "pong" e uptime.
**Teste manual:** abrir Telegram, mandar `/start` do seu chat e de outro (peça a alguém ou use outro bot/conta) — segundo não deve receber resposta.
**Riscos:** vazamento de token em log se mal-configurado. **Mitigação:** logger nunca loga `settings` direto; loga `settings.redacted()`.

### Fase 1.5 — Fusão com `garmin-dashboard` (arquitetura)

> **Status:** desenho pronto; portabilidade do código existente do `joaopdavila/garmin-dashboard` será feita na próxima sessão (após whitelist atualizada).

**Objetivo:** absorver o bot Garmin atual como mais um domínio do `telegram-cpf-assistant`, sob um único `TELEGRAM_BOT_TOKEN`, mantendo as mensagens automáticas que já existem hoje (sono, readiness, body battery, treinos) e habilitando consulta sob demanda.

**Cria/altera:**

- `app/handlers/garmin.py` — handlers de comando.
- `app/services/garmin_service.py` — orquestra busca + persistência + formatação.
- `app/clients/garmin_client.py` — wrapper sobre a lib usada hoje no `garmin-dashboard` (`garth` ou `garminconnect` — confirmar na próxima sessão). Tokens de sessão Garmin ficam em `data/garmin_session/` (gitignored).
- `app/repositories/garmin_repo.py` — SQL para as tabelas abaixo.
- `app/jobs/garmin_morning.py` — relatório matinal (07:30, antes do `/checkin`).
- `app/jobs/garmin_evening.py` — métricas do dia (19:00, antes do `/fechamento`).
- `app/jobs/garmin_weekly.py` — bloco Garmin agregado à revisão de domingo.
- `migrations/00X_garmin.sql` — tabelas.
- `.env.example` ganha: `GARMIN_EMAIL`, `GARMIN_PASSWORD` (opcionais — só preencher se usar Garmin Connect direto; se a auth atual usa OAuth via `garth`, basta apontar para o diretório de tokens).

**Tabelas SQLite novas:**

| Tabela | Campos principais | Granularidade |
|---|---|---|
| `garmin_daily` | id, date UNIQUE, steps, calories_total, calories_active, distance_km, resting_hr, body_battery_max, body_battery_min, stress_avg, raw_json | 1 linha/dia |
| `garmin_sleep` | id, date UNIQUE, total_hours, deep_min, light_min, rem_min, awake_min, score, hrv_avg, raw_json | 1 linha/noite |
| `garmin_training` | id, date UNIQUE, readiness_score, training_status, vo2max, acute_load_7d, chronic_load_28d, raw_json | 1 linha/dia |
| `garmin_workouts` | id, activity_id UNIQUE, start_at, type, duration_min, distance_km, avg_hr, max_hr, calories, training_effect_aerobic, training_effect_anaerobic, raw_json | 1 linha/treino |
| `garmin_body_composition` | id, date UNIQUE, weight_kg, body_fat_pct, muscle_kg, water_pct, bmi, source, raw_json | 1 linha/medição |
| `garmin_sync_log` | id, ran_at, scope, ok, error | auditoria de sync |

Convenção `raw_json TEXT`: preserva payload bruto para auditoria/replays sem ter que re-chamar a API.

**Comandos novos:**

| Comando | Comportamento |
|---|---|
| `/garmin` | Resumo de hoje em uma mensagem: sono da última noite, body battery atual, readiness, passos, calorias, último treino. |
| `/garmin_sono` | Detalhe do sono da última noite (fases, score, HRV). |
| `/garmin_hrv` | Tendência de HRV últimos 7d. |
| `/garmin_treino [id]` | Último treino completo; com id, treino específico. |
| `/garmin_treinos [n]` | Lista dos últimos N treinos (default 7). |
| `/garmin_corpo` | Última medição de composição corporal + tendência. |
| `/garmin_peso <valor>` | Idêntico ao `/peso` da Fase 5, mas explicitamente como Garmin (entra em `garmin_body_composition.source = 'manual'`). |
| `/garmin_status` | Training status + readiness + acute/chronic load. |
| `/garmin_semana` | Resumo da semana: sono médio, HRV média, treinos totais, distância, calorias, evolução do peso. |
| `/garmin_sync` | Força sync imediato (não espera o cron). |

**Jobs no scheduler unificado:**

| Job | Horário | Frequência | Conteúdo |
|---|---|---|---|
| `garmin_sync_morning` | 06:30 | Diário | Puxa dados Garmin da última noite + dia anterior, grava nas tabelas. **Job de dados, sem envio.** |
| `garmin_morning_report` | 07:30 | Diário | Mensagem: "Bom dia. Dormiu Xh (score Y, HRV Z). Body battery: A%. Readiness: B/100. Treino planejado?" Antecede o `/checkin` das 08:00. |
| `garmin_evening_report` | 19:00 | Diário | "Hoje: X passos, Y kcal, treino: Z (se houver). Estresse médio: W. Vai descansar bem?" Antecede o `/fechamento` das 19:30. |
| `garmin_sync_postworkout` | a cada 30min | Polling leve | Detecta atividade nova e dispara mensagem de resumo ("Treino: corrida 7,2km em 38min, FC média 152, training effect 3,4 aeróbico"). Opcional — só ativar se o `garmin-dashboard` atual já fazia isso. |
| `garmin_weekly_block` | Domingo 17:55 | Semanal | Pré-cálculo do bloco Garmin que entra na `/semana` das 18:00. |

**Integração com fluxos existentes:**

- **`/checkin` 08:00** — passa a chamar `garmin_service.get_morning_context()` e inclui no template uma linha "Dormiu X, HRV Y, readiness Z". O usuário responde os 4 bullets como antes; resposta entra em `health_checkins` com os campos Garmin **já pré-preenchidos** (`weight_kg`, `sleep_hours`, etc. vêm do Garmin, não precisam ser digitados).
- **`/fechamento` 19:30** — inclui "Treino: X (se houve)" e "Passos: Y".
- **`/semana`** — ganha seção **"Saúde — Garmin"** com sono médio, HRV média, treinos totais, distância, peso (delta), readiness média.
- **`/saude_semana`** (Fase 7) — passa a usar Garmin como fonte primária; campos manuais (`/peso`, `/treino`, `/sono`) viram fallback se não houver sync.

**Migração do `garmin-dashboard` atual (próxima sessão):**

A próxima sessão deve:
1. Ler `joaopdavila/garmin-dashboard`, identificar:
   - lib de auth (garth? garminconnect? requests+session manual?)
   - estrutura de jobs/agendamento existente (cron? APScheduler? schedule? loop infinito?)
   - como os dados são armazenados hoje (sqlite? json? csv?)
   - mensagens já enviadas (formatos, horários, conteúdo)
   - token Telegram já em uso (passa a ser o **único** token do projeto unificado)
2. Portar a auth para `app/clients/garmin_client.py` mantendo a sessão atual (não re-logar — reaproveitar tokens existentes para evitar 2FA).
3. Portar as queries de dados (sono, readiness, body battery, atividades) para `app/services/garmin_service.py`.
4. Migrar (se houver) dados históricos do `garmin-dashboard` para o `cpf_assistant.db` via script único `migrations/scripts/import_garmin_legacy.py`.
5. Aposentar o processo do `garmin-dashboard` (parar o cron, remover do startup do Windows) **após 1 semana de overlap** rodando os dois em paralelo para validar paridade.

**Critério de aceite Fase 1.5:**
- Bot unificado roda com **único** processo, **único** token.
- Comandos `/garmin*` respondem com dados reais.
- Jobs `garmin_morning_report` (07:30) e `garmin_evening_report` (19:00) disparam corretamente.
- Tabelas `garmin_*` populam diariamente via `garmin_sync_morning`.
- `/checkin`, `/fechamento` e `/semana` exibem contexto Garmin embutido.
- Nenhuma chamada à API Garmin no caminho síncrono dos handlers — leitura sempre do SQLite, sync fica nos jobs.

**Riscos:**
- Auth Garmin pode exigir re-2FA — mitigar exportando os tokens da sessão atual antes de desligar o `garmin-dashboard`.
- Rate limit da Garmin Connect — só sync de manhã e à noite, sem polling agressivo (exceto post-workout, se necessário).
- Conflito de duas instâncias do bot Telegram com mesmo token → `Conflict: terminated by other getUpdates`. **Cutover plan:** parar o `garmin-dashboard` antes de iniciar a v1 do cpf-assistant unificado.
- Dados históricos no `garmin-dashboard` em formato diferente — migração one-shot tolerante a falhas (linhas com erro vão para um `garmin_import_errors.log`).

### Fase 2 — SQLite e camada de repositórios
**Objetivo:** schema criado, repositório-base funcionando.
**Cria/altera:**
- `app/database.py` com `get_connection()` e runner de migrations.
- `migrations/001_init.sql` com tabela `schema_version` + `bot_interactions`.
- `app/repositories/base.py` com helpers.
**Critério de aceite:** rodar `python -m app.database --init` cria `data/cpf_assistant.db` com schema_version=1.
**Teste manual:** abrir db com DB Browser, conferir tabelas.
**Riscos:** path do db em Windows com espaços. **Mitigação:** `Path(...).resolve()` em `config.py`.

### Fase 3 — Tarefas e Notas
**Objetivo:** primeiros domínios end-to-end.
**Cria/altera:**
- `migrations/002_tasks_notes.sql`.
- `repositories/tasks_repo.py`, `repositories/notes_repo.py`.
- `services/tasks_service.py`, `services/notes_service.py`.
- `handlers/tasks.py`, `handlers/notes.py`.
- Atualiza `bot.py` para registrar handlers.
- `formatters.py` inicial.
- `tests/test_services/test_tasks_service.py` com SQLite em memória.
**Critério de aceite:** ciclo completo `/tarefa` → `/tarefas` → `/feito <id>` → tarefa não aparece em `/tarefas`. Idem `/nota` e `/buscar`.
**Teste manual:** criar 5 tarefas, concluir 2, listar; criar 3 notas, buscar termo.
**Riscos:** parse ambíguo de `/feito <texto>` quando há múltiplos matches. **Mitigação:** fluxo de listar e pedir id.

### Fase 4 — Compras e Finanças
**Objetivo:** capture financeiro básico funcionando.
**Cria/altera:**
- `migrations/003_shopping_expenses_bills.sql`.
- Repos + services + handlers de `shopping` e `finance`.
- Validador de valor monetário em `formatters.py`.
**Critério de aceite:** `/gasto 47,90 mercado pão` cria registro; `/financas_semana` retorna total por categoria.
**Teste manual:** registrar 10 gastos, 2 contas, marcar 1 paga, conferir totais.
**Riscos:** parsing de valor com vírgula/ponto. **Mitigação:** função `parse_money()` testada com casos.

### Fase 5 — Check-in e fechamento manuais
**Objetivo:** templates funcionando sob comando, sem scheduler ainda.
**Cria/altera:**
- `migrations/004_health_closings.sql`.
- `services/health_service.py`, `handlers/health.py`.
- Estado em memória `pending_response: dict[str, ResponseContext]`.
- Handler de mensagem livre (não-comando) que verifica estado pendente.
**Critério de aceite:** `/checkin` envia template; mensagem subsequente é salva em `health_checkins`. Idem `/fechamento`.
**Teste manual:** disparar manual, responder, conferir db.
**Riscos:** estado em memória se perde no restart. **Mitigação aceitável v1:** restart raro; v2 → persistir.

### Fase 6 — Scheduler
**Objetivo:** mensagens automáticas no horário.
**Cria/altera:**
- `app/scheduler.py`.
- `jobs/morning_checkin.py`, `evening_closing.py`, `midday_reminder.py`, `monday_priorities.py`, `friday_finance.py`.
- `main.py` inicia scheduler junto com bot.
**Critério de aceite:** rodar bot, ajustar temporariamente um job para "daqui a 1 minuto", confirmar recebimento.
**Teste manual:** disparar cada job manualmente via função utilitária `python -m app.scheduler --run morning_checkin`.
**Riscos:** PC desligado às 08:00 → job perdido. **Mitigação:** documentar no README; `misfire_grace_time` cobre atrasos curtos.

### Fase 7 — Revisão semanal + Casamento + Saúde estendida
**Objetivo:** features pós-MVP completas.
**Cria/altera:**
- `migrations/005_wedding.sql`.
- `services/wedding_service.py`, `handlers/wedding.py`.
- `services/review_service.py` agrega todos os domínios.
- `handlers/review.py` (`/semana`) + `jobs/weekly_review.py`.
- Comandos `/peso`, `/treino`, `/sono`, `/saude_semana`.
**Critério de aceite:** `/semana` produz relatório consolidado com seções de todos os domínios.
**Teste manual:** popular db com dados de uma semana, rodar `/semana`, conferir.
**Riscos:** relatório muito longo → split em múltiplas mensagens (Telegram limita 4096 chars).

### Fase 8 — Exportação Excel + Backup
**Objetivo:** dados saem do db.
**Cria/altera:**
- `exporters/excel_exporter.py` usando `pandas` + `openpyxl`.
- `/export [dominio]` envia `.xlsx` via `send_document`.
- Job diário 03:00 copia `.db` para `data/backups/cpf_assistant_YYYYMMDD.db` (mantém últimos 14).
- `/backup` manual.
**Critério de aceite:** `/export gastos` recebe `.xlsx` com tabela de expenses.
**Teste manual:** abrir no Excel, conferir colunas.
**Riscos:** db locked durante backup. **Mitigação:** usar `sqlite3.backup()` API.

### Fase 9 — Testes e hardening
**Objetivo:** estabilidade para uso diário.
**Cria/altera:**
- Cobertura `pytest` em `services/` e `repositories/` ≥ 70%.
- Error handler global do bot que loga stack e responde "Erro interno, log gravado".
- Documentação de troubleshooting no README.
- Script `scripts/run.bat` para Windows iniciar o bot.
**Critério de aceite:** `pytest` passa local; bot roda por 7 dias sem crash não tratado.
**Teste manual:** rodar `pytest`; usar bot por uma semana inteira.
**Riscos:** descoberta de bugs reais só após dias de uso. **Mitigação:** logs detalhados.

---

## 11. Critérios de aceite do MVP

A v1 está pronta quando, **simultaneamente**, todos os itens abaixo forem verdade:

1. Bot conecta ao Telegram com token do `.env` e responde apenas ao `TELEGRAM_CHAT_ID` configurado.
2. Comandos `/start`, `/help`, `/ping` funcionam.
3. Tarefas: criar, listar, marcar feita, marcar pendente — funcionando e persistindo.
4. Notas: criar, listar, buscar.
5. Compras: adicionar (com dedupe), listar, marcar comprado, limpar.
6. Finanças: `/gasto`, `/conta`, `/contas`, `/pago`, `/financas_semana` funcionando.
7. Check-in (`/checkin`) e fechamento (`/fechamento`) manuais salvam respostas.
8. Scheduler dispara: 08:00 check-in, 12:30 reminder, 19:30 fechamento, domingo 18:00 revisão.
9. `/semana` gera relatório consolidado.
10. Logs em `logs/app.log` sem expor token nem PII sensível.
11. SQLite em `data/cpf_assistant.db` persistente entre restarts.
12. README com instruções de setup no Windows (passo a passo).
13. `.env.example` cobre todas as variáveis.
14. Bot roda 7 dias consecutivos com você usando, sem crash não tratado.

---

## 12. Riscos e decisões em aberto

### Riscos técnicos
| Risco | Severidade | Mitigação |
|---|---|---|
| PC desligado nos horários de job | Média | Documentar no README; futuramente migrar para Raspberry/cloud. |
| `.db` corrompido por crash durante write | Baixa | SQLite é robusto; backups diários a partir da Fase 8. |
| Telegram bloqueia bot por flood | Baixa | Single user, volume baixíssimo. |
| Token vazado em commit | Alta | `.gitignore` rigoroso, `.env.example` sem valores, code review. |
| Estado em memória perdido no restart (check-in pendente) | Baixa | Aceitável v1; documentar comportamento. |
| Mensagem do scheduler > 4096 chars (limite Telegram) | Média | Função `send_long_message()` que faz split por seção. |
| Encoding em Windows (acentos, emoji) | Média | `utf-8` explícito em todo I/O de arquivo. |
| Conflito de timezone no APScheduler vs SQLite | Média | Padronizar `America/Sao_Paulo` no scheduler e gravar datas locais naive no db. |

### Decisões em aberto (precisam ser respondidas antes do código)
1. **Repositório:** novo repo `telegram-cpf-assistant` separado, ou subdiretório dentro de `joaopdavila/joaopdavila`? **Recomendação:** novo repo privado.
2. **Onde rodar:** PC pessoal sempre ligado? Notebook que dorme? Vai pensar em mini-PC futuro? **Impacto:** decide urgência da Fase 3.0.
3. **Categorias de gasto:** fixas (CHECK constraint) ou livres com sugestão? **Recomendação:** livres com lista canônica sugerida.
4. **Idioma das respostas do bot:** PT-BR puro ou misturado com emojis? **Recomendação:** PT-BR seco, sem emoji por padrão (você adiciona se quiser).
5. **`/limpar_compras`:** apaga só `bought` ou também `pending`? **Recomendação:** só `bought`, com confirmação.
6. **Mensagens do midday (12:30):** todo dia? Só dias úteis? **Recomendação:** dias úteis.
7. **Captura de resposta livre pós-check-in:** janela de 2h é razoável? Vai responder mais tarde? **Decidir.**
8. **Múltiplos check-ins por dia:** permitir sobrescrever ou bloquear? **Recomendação:** upsert por data (sobrescreve).
9. **Backup:** quantos dias manter? **Recomendação:** 14.
10. **Quem é o "fornecedor" no casamento:** tabela separada `wedding_vendors` ou campo livre em `wedding_items`? **Recomendação:** campo livre na v1; tabela própria na v2.

---

## 13. Sugestão de estrutura do README

```markdown
# telegram-cpf-assistant

Assistente pessoal via Telegram para organização de pessoa física.
Rodando localmente, single-user, SQLite.

## Requisitos
- Windows 10/11 (testado) ou Linux
- Python 3.11+
- Conta no Telegram + bot criado via @BotFather

## Setup
1. `git clone ...`
2. `python -m venv .venv && .venv\Scripts\activate`
3. `pip install -r requirements.txt`
4. Copiar `.env.example` para `.env` e preencher:
   - `TELEGRAM_BOT_TOKEN` (do BotFather)
   - `TELEGRAM_CHAT_ID` (use @userinfobot para descobrir)
   - `TIMEZONE=America/Sao_Paulo`
   - `DATABASE_PATH=./data/cpf_assistant.db`
   - `LOG_LEVEL=INFO`
5. `python -m app.database --init` (cria schema)
6. `python -m app.main` (inicia o bot)

## Como descobrir seu CHAT_ID
[passo a passo com @userinfobot]

## Comandos
[link para seção / tabela resumida]

## Rodar no startup do Windows
[receita com Task Scheduler]

## Backup
[como funciona, onde ficam os arquivos]

## Troubleshooting
- "Conflict: terminated by other getUpdates" → outra instância rodando.
- Bot não responde → checar `TELEGRAM_CHAT_ID`, logs em `logs/app.log`.
- Encoding errors → garantir terminal em UTF-8 (`chcp 65001`).

## Estrutura do projeto
[árvore resumida]

## Segurança
- Token e chat_id ficam só no `.env`, nunca commitado.
- Bot rejeita mensagens de qualquer chat que não seja o autorizado.
- Logs não contêm token nem valores monetários completos em texto livre.

## Roadmap
[link/resumo das fases pós-MVP]

## Licença
Pessoal / MIT (sua escolha).
```

---

## 14. Próximo prompt (para usar quando quiser implementar)

> Implemente a **Fase 0 (setup)** e a **Fase 1 (bot mínimo com gate de segurança)** do projeto `telegram-cpf-assistant`, seguindo o plano em `/root/.claude/plans/voc-um-arquiteto-eventual-wind.md`.
>
> Entregue:
> 1. Estrutura de pastas conforme seção 3 do plano (criar pastas vazias com `.gitkeep` onde necessário).
> 2. `.gitignore` cobrindo Python, `data/`, `logs/`, `.env`.
> 3. `.env.example` com `TELEGRAM_BOT_TOKEN=`, `TELEGRAM_CHAT_ID=`, `TIMEZONE=America/Sao_Paulo`, `DATABASE_PATH=./data/cpf_assistant.db`, `LOG_LEVEL=INFO`.
> 4. `requirements.txt` com `python-telegram-bot==21.*`, `APScheduler==3.*`, `python-dotenv==1.*`, `pandas`, `openpyxl`, `pytest`.
> 5. `app/config.py`: dataclass `Settings` carregado via `python-dotenv`, com `.redacted()` para logs e validação de chaves obrigatórias (erro claro se faltar).
> 6. `app/logger.py`: `setup_logging()` com `RotatingFileHandler` em `logs/app.log` (5MB × 5) + console; nunca logar token.
> 7. `app/security.py`: decorator `authorized_only` que rejeita silenciosamente updates de `chat_id != settings.TELEGRAM_CHAT_ID` com log `WARNING`.
> 8. `app/bot.py`: cria `Application` do `python-telegram-bot`, registra handlers `/start`, `/help` (placeholder listando comandos planejados), `/ping` (responde "pong — uptime Xh"). Todos decorados com `authorized_only`. Inclui `error_handler` global que loga stack e responde "Erro interno, log gravado".
> 9. `app/main.py`: entrypoint que carrega config, configura logging, instancia bot e inicia polling (`run_polling`).
> 10. `README.md` com seção de Setup (passo a passo Windows) e seção de Segurança.
>
> Restrições:
> - Não implementar SQLite, scheduler, handlers de domínio ou jobs ainda — isso é Fase 2+.
> - Nunca hardcodar token ou chat_id.
> - Código em Python 3.11+, type hints onde fizer sentido, sem comentários desnecessários.
> - Funcionar no Windows (paths com `pathlib`, encoding `utf-8` explícito).
>
> Critério de aceite:
> - `python -c "from app.config import Settings; s = Settings.load(); print(s.redacted())"` imprime config sem expor token.
> - `python -m app.main` inicia o bot; `/start` no Telegram do chat autorizado responde; mensagem de outro chat é ignorada (com `WARNING` no log).
> - `/ping` responde com uptime.
> - Nenhum import de SQLite ou APScheduler ainda.
>
> Faça commits separados por Fase 0 e Fase 1, mensagens descritivas. Crie a branch `claude/telegram-cpf-assistant-impl-fase-0-1` ou continue na branch atual `claude/telegram-cpf-assistant-design-t31ZQ` — confirme comigo qual prefere.

---

## Verificação do plano

Não há código a executar nesta etapa. A "verificação" do plano consiste em:

1. **Você lê este documento e confirma:**
   - Cobertura funcional (todos os comandos previstos no escopo aparecem na seção 5).
   - Modelo de dados (todas as tabelas necessárias estão na seção 4).
   - Plano de fases (cada fase tem objetivo, arquivos, aceite e risco).
2. **Você responde às 10 decisões em aberto** da seção 12 — ou as adia para o início da implementação.
3. **Você aprova ou pede ajuste** via `ExitPlanMode`.

Quando aprovar, basta usar o **prompt da seção 14** para iniciar a Fase 0+1.
