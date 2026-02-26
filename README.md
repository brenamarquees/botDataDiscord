# GRACE Discord Calendar Bot (Python)

Bot de Discord criado do zero para organizar calendário anual do GRACE, com foco em:

- Eventos e cursos ao longo do ano.
- Tarefas por área (`marketing`, `diretoria`, `rh`, `financeiro`, `ensino`).
- Permissão para **diretoria/liderança** adicionar eventos e tarefas.
- Lembretes automáticos com **2 semanas de antecedência** no Discord.

## Arquitetura

- `src/grace_bot/bot.py`: comandos slash, permissões e rotina de lembrete.
- `src/grace_bot/storage.py`: persistência em JSON e carga de eventos iniciais de 2026.
- `src/grace_bot/models.py`: modelos de domínio (`Event`, `Task`, `Area`).
- `data/events.json`: base persistida (gerada na primeira execução).

## Requisitos

- Python 3.10+
- Token de bot no Discord Developer Portal
- Bot adicionado ao servidor com escopo `applications.commands` e permissões para enviar mensagens

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Preencha no `.env`:

- `DISCORD_TOKEN`: token do bot
- `GUILD_ID`: ID do servidor Discord
- `ALLOWED_MANAGER_ROLE_NAMES`: papéis autorizados para editar calendário
- `REMINDER_CHANNEL_NAME`: canal de lembretes (ex.: `avisos-grace`)
- `TZ`: fuso horário (padrão `America/Sao_Paulo`)

## Execução

```bash
export $(cat .env | xargs)
PYTHONPATH=src python -m grace_bot
```

## Comandos disponíveis

- `/eventos` → lista eventos cadastrados.
- `/detalhar_evento indice_evento:<n>` → mostra detalhes e tarefas do evento.
- `/tarefas_area area:<marketing|diretoria|rh|financeiro|ensino>` → lista tarefas pendentes da área.
- `/adicionar_evento ...` → adiciona evento (**somente diretoria/liderança**).
- `/adicionar_tarefa ... responsaveis:"@user @user" ferramentas:"Canva,Trello"` → cria tarefa com responsáveis e ferramentas (**somente diretoria/liderança**).
- `/atualizar_progresso indice_evento:<n> indice_tarefa:<m> percentual:<0-100>` → responsável atualiza andamento.
- `/concluir_tarefa ... link_entrega:<url> lider_revisor:@lider` → finaliza e envia para revisão.
- `/revisar_tarefa ... aprovar:<true|false>` → liderança aprova/reprova entrega.

## Lembretes automáticos (2 semanas)

A rotina `reminder_loop` roda de hora em hora e envia lembretes quando faltar exatamente 14 dias para:

- início de um evento;
- prazo de uma tarefa pendente (inclui menção aos responsáveis).

O bot evita lembretes duplicados usando marcação interna em `reminded_for_dates`.

## Eventos iniciais incluídos

Na primeira execução, se a base estiver vazia, o bot adiciona eventos iniciais de 2026 derivados do rascunho informado:

- Technovation Summer School for Girls
- Workshop Mulheres na IA
- Pint of Science 2026
- WebMedia 4 Everyone

Depois disso, diretoria/liderança pode continuar alimentando o calendário com os demais eventos e datas comemorativas.

## Próximos passos recomendados

- Migrar persistência JSON para SQLite/PostgreSQL.
- Adicionar comando de importação em lote via CSV.
- Criar painéis por área com Discord embeds.
- Integrar com Google Calendar para sincronização externa.
