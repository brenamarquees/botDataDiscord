from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .models import Area, Event, Task


@dataclass(slots=True)
class CalendarStore:
    db_path: Path

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists():
            self.save([])

    def load(self) -> list[Event]:
        with self.db_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return [Event.from_dict(item) for item in data]

    def save(self, events: list[Event]) -> None:
        with self.db_path.open("w", encoding="utf-8") as f:
            json.dump([event.to_dict() for event in events], f, ensure_ascii=False, indent=2)

    def seed_if_empty(self) -> bool:
        events = self.load()
        if events:
            return False
        self.save(default_events_2026())
        return True


def default_events_2026() -> list[Event]:
    return [
        Event(
            name="8ª Technovation Summer School for Girls",
            start_date=date(2026, 1, 10),
            end_date=date(2026, 5, 21),
            acting="Responsável",
            partners="TechGirls (Isadora e Dani)",
            notes="Curso e escola",
            tasks=[
                Task("Planejar divulgação de abertura", Area.MARKETING, date(2025, 12, 27)),
                Task("Definir monitoras e cronograma", Area.ENSINO, date(2026, 1, 3)),
            ],
        ),
        Event(
            name="Workshop Mulheres na IA",
            start_date=date(2026, 2, 27),
            end_date=date(2026, 2, 27),
            acting="Divulgação nas redes e participação",
            partners="Meninas Digitais Sudeste",
            notes="Evento de extensão",
            tasks=[
                Task("Produzir posts para redes sociais", Area.MARKETING, date(2026, 2, 13)),
                Task("Organizar presença da equipe", Area.DIRETORIA, date(2026, 2, 20)),
            ],
        ),
        Event(
            name="Pint of Science 2026",
            start_date=date(2026, 5, 18),
            end_date=date(2026, 5, 20),
            acting="Colaboração",
            partners="CCEx - ICMC",
            notes="Evento de extensão",
            tasks=[
                Task("Mapear empresas parceiras", Area.FINANCEIRO, date(2026, 5, 4)),
                Task("Escalar voluntárias", Area.RH, date(2026, 5, 8)),
            ],
        ),
        Event(
            name="WebMedia 4 Everyone",
            start_date=date(2026, 11, 9),
            end_date=date(2026, 11, 13),
            acting="Apresentação de artigo",
            partners="Comunidade acadêmica",
            notes="Participação em eventos acadêmicos",
            tasks=[
                Task("Fechar submissão do artigo", Area.ENSINO, date(2026, 7, 3)),
                Task("Reservar orçamento para deslocamento", Area.FINANCEIRO, date(2026, 9, 15)),
            ],
        ),
    ]
