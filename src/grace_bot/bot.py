from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .models import Area, Event, Task, VALID_AREAS
from .storage import CalendarStore

MENTION_RE = re.compile(r"<@!?(\d+)>")


@dataclass(slots=True)
class Settings:
    token: str
    guild_id: int
    manager_roles: set[str]
    reminder_channel_name: str
    tz: ZoneInfo


def parse_settings() -> Settings:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    guild_id = int(os.getenv("GUILD_ID", "0").strip() or "0")
    manager_roles = {
        role.strip().lower()
        for role in os.getenv("ALLOWED_MANAGER_ROLE_NAMES", "diretoria,lideranca").split(",")
        if role.strip()
    }
    reminder_channel_name = os.getenv("REMINDER_CHANNEL_NAME", "avisos-grace").strip()
    tz_name = os.getenv("TZ", "America/Sao_Paulo").strip()
    if not token or guild_id <= 0:
        raise RuntimeError("Defina DISCORD_TOKEN e GUILD_ID nas variáveis de ambiente.")
    return Settings(token, guild_id, manager_roles, reminder_channel_name, ZoneInfo(tz_name))


class GraceCalendarBot(commands.Bot):
    def __init__(self, settings: Settings, store: CalendarStore):
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)
        self.settings = settings
        self.store = store
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        self.store.seed_if_empty()
        guild = discord.Object(id=self.settings.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        self.reminder_loop.start()

    def _today(self) -> date:
        return datetime.now(self.settings.tz).date()

    def _load_events(self) -> list[Event]:
        return self.store.load()

    def _save_events(self, events: list[Event]) -> None:
        self.store.save(events)

    def _user_is_manager(self, member: discord.abc.User | discord.Member | None) -> bool:
        if not isinstance(member, discord.Member):
            return False
        names = {role.name.lower() for role in member.roles}
        return bool(names.intersection(self.settings.manager_roles))

    def _parse_mentions(self, mentions_text: str) -> list[int]:
        ids = [int(value) for value in MENTION_RE.findall(mentions_text)]
        return list(dict.fromkeys(ids))

    def _can_update_task(self, member: discord.abc.User | discord.Member | None, task: Task) -> bool:
        if self._user_is_manager(member):
            return True
        if isinstance(member, discord.Member):
            return member.id in task.assignee_ids
        return False

    @tasks.loop(minutes=60)
    async def reminder_loop(self) -> None:
        await self.wait_until_ready()
        guild = self.get_guild(self.settings.guild_id)
        if guild is None:
            return
        channel = discord.utils.get(guild.text_channels, name=self.settings.reminder_channel_name)
        if channel is None:
            return

        target = self._today() + timedelta(days=14)
        events = self._load_events()
        changed = False
        for event in events:
            target_key = target.isoformat()
            if event.start_date == target and target_key not in event.reminded_for_dates:
                await channel.send(
                    f"⏰ **Lembrete (2 semanas):** `{event.name}` em {target:%d/%m/%Y}."
                )
                event.reminded_for_dates.add(target_key)
                changed = True

            for task in event.tasks:
                due_key = task.due_date.isoformat()
                composite_key = f"task::{task.title}::{due_key}"
                if task.due_date == target and not task.done and composite_key not in event.reminded_for_dates:
                    assignees = " ".join(f"<@{uid}>" for uid in task.assignee_ids) or "(sem responsável)"
                    await channel.send(
                        "📌 **Tarefa vencendo em 2 semanas**\n"
                        f"Evento: `{event.name}`\n"
                        f"Área: `{task.area.value}`\n"
                        f"Tarefa: {task.title}\n"
                        f"Responsáveis: {assignees}\n"
                        f"Prazo: {target:%d/%m/%Y}"
                    )
                    event.reminded_for_dates.add(composite_key)
                    changed = True

        if changed:
            self._save_events(events)


def register_commands(bot: GraceCalendarBot) -> None:
    guild = discord.Object(id=bot.settings.guild_id)

    @bot.tree.command(name="eventos", description="Lista eventos cadastrados", guild=guild)
    async def eventos(interaction: discord.Interaction) -> None:
        events_data = bot._load_events()
        if not events_data:
            await interaction.response.send_message("Nenhum evento cadastrado.", ephemeral=True)
            return
        lines = [
            f"**{idx + 1}. {event.name}** ({event.start_date:%d/%m/%Y} - {event.end_date:%d/%m/%Y})"
            for idx, event in enumerate(events_data)
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @bot.tree.command(name="tarefas_area", description="Mostra tarefas por área", guild=guild)
    async def tarefas_area(interaction: discord.Interaction, area: str) -> None:
        area_normalized = area.strip().lower()
        if area_normalized not in VALID_AREAS:
            await interaction.response.send_message(
                "Área inválida. Use: marketing, diretoria, rh, financeiro, ensino.",
                ephemeral=True,
            )
            return

        target_area = Area(area_normalized)
        entries: list[str] = []
        for event in bot._load_events():
            for idx, task in enumerate(event.tasks):
                if task.area == target_area and not task.done:
                    assignees = ", ".join(f"<@{uid}>" for uid in task.assignee_ids) or "sem responsável"
                    entries.append(
                        f"• E{event.name} T{idx + 1}: **{task.title}** | {task.due_date:%d/%m/%Y} | "
                        f"{task.progress}% | {assignees}"
                    )

        if not entries:
            await interaction.response.send_message(
                f"Nenhuma tarefa pendente para `{target_area.value}`.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Tarefas da área **{target_area.value}**:\n" + "\n".join(entries),
            ephemeral=True,
        )

    @bot.tree.command(name="adicionar_evento", description="Adiciona um novo evento", guild=guild)
    async def adicionar_evento(
        interaction: discord.Interaction,
        nome: str,
        inicio: str,
        fim: str,
        atuacao: str,
        parceiros: str,
        notas: str = "",
    ) -> None:
        if not bot._user_is_manager(interaction.user):
            await interaction.response.send_message(
                "Apenas diretoria/lideranças podem adicionar eventos.", ephemeral=True
            )
            return

        try:
            start_date = date.fromisoformat(inicio)
            end_date = date.fromisoformat(fim)
        except ValueError:
            await interaction.response.send_message(
                "Datas inválidas. Use formato AAAA-MM-DD.", ephemeral=True
            )
            return

        events_data = bot._load_events()
        events_data.append(Event(nome.strip(), start_date, end_date, atuacao.strip(), parceiros.strip(), notas.strip()))
        bot._save_events(events_data)
        await interaction.response.send_message(f"Evento `{nome}` adicionado com sucesso.", ephemeral=True)

    @bot.tree.command(name="adicionar_tarefa", description="Adiciona tarefa para um evento", guild=guild)
    async def adicionar_tarefa(
        interaction: discord.Interaction,
        indice_evento: int,
        titulo: str,
        area: str,
        prazo: str,
        responsaveis: str,
        ferramentas: str = "",
        detalhes: str = "",
    ) -> None:
        if not bot._user_is_manager(interaction.user):
            await interaction.response.send_message(
                "Apenas diretoria/lideranças podem adicionar tarefas.", ephemeral=True
            )
            return

        area_normalized = area.strip().lower()
        if area_normalized not in VALID_AREAS:
            await interaction.response.send_message("Área inválida.", ephemeral=True)
            return

        try:
            due_date = date.fromisoformat(prazo)
        except ValueError:
            await interaction.response.send_message("Prazo inválido. Use AAAA-MM-DD.", ephemeral=True)
            return

        assignee_ids = bot._parse_mentions(responsaveis)
        if not assignee_ids:
            await interaction.response.send_message(
                "Informe ao menos um responsável em `responsaveis` usando @menção.",
                ephemeral=True,
            )
            return

        tools = [item.strip() for item in ferramentas.split(",") if item.strip()]

        events_data = bot._load_events()
        if indice_evento < 1 or indice_evento > len(events_data):
            await interaction.response.send_message("Índice de evento inválido.", ephemeral=True)
            return

        event = events_data[indice_evento - 1]
        task = Task(
            title=titulo.strip(),
            area=Area(area_normalized),
            due_date=due_date,
            details=detalhes.strip(),
            tools=tools,
            assignee_ids=assignee_ids,
        )
        event.tasks.append(task)
        bot._save_events(events_data)

        mentions = " ".join(f"<@{uid}>" for uid in assignee_ids)
        await interaction.response.send_message(
            f"Tarefa adicionada ao evento `{event.name}` e responsáveis notificados.", ephemeral=True
        )
        await interaction.channel.send(
            "🆕 **Nova tarefa atribuída**\n"
            f"{mentions}\n"
            f"Evento: `{event.name}`\n"
            f"Tarefa: **{task.title}**\n"
            f"Prazo: {task.due_date:%d/%m/%Y}\n"
            f"Ferramentas: {', '.join(task.tools) if task.tools else '-'}"
        )

    @bot.tree.command(name="atualizar_progresso", description="Atualiza progresso de uma tarefa", guild=guild)
    async def atualizar_progresso(
        interaction: discord.Interaction,
        indice_evento: int,
        indice_tarefa: int,
        percentual: app_commands.Range[int, 0, 100],
    ) -> None:
        events_data = bot._load_events()
        if indice_evento < 1 or indice_evento > len(events_data):
            await interaction.response.send_message("Índice de evento inválido.", ephemeral=True)
            return

        event = events_data[indice_evento - 1]
        if indice_tarefa < 1 or indice_tarefa > len(event.tasks):
            await interaction.response.send_message("Índice de tarefa inválido.", ephemeral=True)
            return

        task = event.tasks[indice_tarefa - 1]
        if not bot._can_update_task(interaction.user, task):
            await interaction.response.send_message(
                "Somente responsáveis da tarefa ou liderança podem atualizar progresso.",
                ephemeral=True,
            )
            return

        task.progress = int(percentual)
        if task.progress < 100:
            task.done = False
            task.reviewed = False
            task.delivery_link = ""
            task.reviewer_id = None
        bot._save_events(events_data)
        await interaction.response.send_message(
            f"Progresso da tarefa `{task.title}` atualizado para {task.progress}%.",
            ephemeral=True,
        )

    @bot.tree.command(name="concluir_tarefa", description="Concluir tarefa com link e liderança revisora", guild=guild)
    async def concluir_tarefa(
        interaction: discord.Interaction,
        indice_evento: int,
        indice_tarefa: int,
        link_entrega: str,
        lider_revisor: discord.Member,
    ) -> None:
        events_data = bot._load_events()
        if indice_evento < 1 or indice_evento > len(events_data):
            await interaction.response.send_message("Índice de evento inválido.", ephemeral=True)
            return

        event = events_data[indice_evento - 1]
        if indice_tarefa < 1 or indice_tarefa > len(event.tasks):
            await interaction.response.send_message("Índice de tarefa inválido.", ephemeral=True)
            return

        task = event.tasks[indice_tarefa - 1]
        if not bot._can_update_task(interaction.user, task):
            await interaction.response.send_message(
                "Somente responsáveis da tarefa ou liderança podem concluir.",
                ephemeral=True,
            )
            return

        if not bot._user_is_manager(lider_revisor):
            await interaction.response.send_message(
                "O usuário informado em `lider_revisor` deve ser uma liderança/diretoria.",
                ephemeral=True,
            )
            return

        task.progress = 100
        task.done = True
        task.delivery_link = link_entrega.strip()
        task.reviewer_id = lider_revisor.id
        task.reviewed = False
        bot._save_events(events_data)

        await interaction.response.send_message(
            "Tarefa marcada como finalizada e enviada para revisão.",
            ephemeral=True,
        )
        await interaction.channel.send(
            "✅ **Tarefa finalizada aguardando revisão**\n"
            f"Revisor: <@{lider_revisor.id}>\n"
            f"Evento: `{event.name}`\n"
            f"Tarefa: **{task.title}**\n"
            f"Entrega: {task.delivery_link}"
        )

    @bot.tree.command(name="revisar_tarefa", description="Liderança aprova/reprova entrega", guild=guild)
    async def revisar_tarefa(
        interaction: discord.Interaction,
        indice_evento: int,
        indice_tarefa: int,
        aprovar: bool,
        comentario: str = "",
    ) -> None:
        if not bot._user_is_manager(interaction.user):
            await interaction.response.send_message("Apenas liderança pode revisar.", ephemeral=True)
            return

        events_data = bot._load_events()
        if indice_evento < 1 or indice_evento > len(events_data):
            await interaction.response.send_message("Índice de evento inválido.", ephemeral=True)
            return

        event = events_data[indice_evento - 1]
        if indice_tarefa < 1 or indice_tarefa > len(event.tasks):
            await interaction.response.send_message("Índice de tarefa inválido.", ephemeral=True)
            return

        task = event.tasks[indice_tarefa - 1]
        if task.reviewer_id and isinstance(interaction.user, discord.Member):
            if task.reviewer_id != interaction.user.id:
                await interaction.response.send_message(
                    "A tarefa possui revisor definido. Somente essa liderança pode revisar.",
                    ephemeral=True,
                )
                return

        if aprovar:
            task.reviewed = True
            msg = "Revisão aprovada."
        else:
            task.done = False
            task.progress = 90
            task.reviewed = False
            msg = "Revisão solicitou ajustes (tarefa reaberta com 90%)."

        bot._save_events(events_data)
        notes = f"\nComentário: {comentario}" if comentario.strip() else ""
        await interaction.response.send_message(msg + notes, ephemeral=True)

    @bot.tree.command(name="detalhar_evento", description="Mostra tarefas e detalhes de um evento", guild=guild)
    async def detalhar_evento(interaction: discord.Interaction, indice_evento: int) -> None:
        events_data = bot._load_events()
        if indice_evento < 1 or indice_evento > len(events_data):
            await interaction.response.send_message("Índice de evento inválido.", ephemeral=True)
            return

        event = events_data[indice_evento - 1]
        tasks_lines = []
        for idx, task in enumerate(event.tasks):
            assignees = ", ".join(f"<@{uid}>" for uid in task.assignee_ids) or "-"
            tools = ", ".join(task.tools) or "-"
            reviewer = f"<@{task.reviewer_id}>" if task.reviewer_id else "-"
            status = "aprovada" if task.reviewed else ("finalizada" if task.done else "em andamento")
            tasks_lines.append(
                f"{idx + 1}. [{status}] {task.title} | {task.area.value} | {task.due_date:%d/%m/%Y} | "
                f"{task.progress}%\n   responsáveis: {assignees}\n   ferramentas: {tools}\n"
                f"   entrega: {task.delivery_link or '-'} | revisor: {reviewer}"
            )

        tasks_text = "\n".join(tasks_lines) if tasks_lines else "Sem tarefas."
        await interaction.response.send_message(
            f"**{event.name}**\n"
            f"Período: {event.start_date:%d/%m/%Y} - {event.end_date:%d/%m/%Y}\n"
            f"Atuação: {event.acting}\nParceiros: {event.partners}\nNotas: {event.notes or '-'}\n"
            f"Tarefas:\n{tasks_text}",
            ephemeral=True,
        )


def build_bot(data_dir: Path | None = None) -> GraceCalendarBot:
    settings = parse_settings()
    store = CalendarStore((data_dir or Path("data")) / "events.json")
    bot = GraceCalendarBot(settings=settings, store=store)
    register_commands(bot)
    return bot


def run() -> None:
    bot = build_bot()
    bot.run(bot.settings.token)
