from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class Area(str, Enum):
    MARKETING = "marketing"
    DIRETORIA = "diretoria"
    RH = "rh"
    FINANCEIRO = "financeiro"
    ENSINO = "ensino"


VALID_AREAS = {area.value for area in Area}


@dataclass(slots=True)
class Task:
    title: str
    area: Area
    due_date: date
    details: str = ""
    tools: list[str] = field(default_factory=list)
    assignee_ids: list[int] = field(default_factory=list)
    progress: int = 0
    done: bool = False
    delivery_link: str = ""
    reviewer_id: int | None = None
    reviewed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "area": self.area.value,
            "due_date": self.due_date.isoformat(),
            "details": self.details,
            "tools": self.tools,
            "assignee_ids": self.assignee_ids,
            "progress": self.progress,
            "done": self.done,
            "delivery_link": self.delivery_link,
            "reviewer_id": self.reviewer_id,
            "reviewed": self.reviewed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        progress = int(data.get("progress", 0))
        progress = max(0, min(100, progress))
        return cls(
            title=str(data["title"]),
            area=Area(str(data["area"])),
            due_date=date.fromisoformat(str(data["due_date"])),
            details=str(data.get("details", "")),
            tools=[str(item).strip() for item in data.get("tools", []) if str(item).strip()],
            assignee_ids=[int(item) for item in data.get("assignee_ids", [])],
            progress=progress,
            done=bool(data.get("done", False)),
            delivery_link=str(data.get("delivery_link", "")),
            reviewer_id=(int(data["reviewer_id"]) if data.get("reviewer_id") else None),
            reviewed=bool(data.get("reviewed", False)),
        )


@dataclass(slots=True)
class Event:
    name: str
    start_date: date
    end_date: date
    acting: str
    partners: str
    notes: str = ""
    tasks: list[Task] = field(default_factory=list)
    reminded_for_dates: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "acting": self.acting,
            "partners": self.partners,
            "notes": self.notes,
            "tasks": [task.to_dict() for task in self.tasks],
            "reminded_for_dates": sorted(self.reminded_for_dates),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        return cls(
            name=str(data["name"]),
            start_date=date.fromisoformat(str(data["start_date"])),
            end_date=date.fromisoformat(str(data["end_date"])),
            acting=str(data.get("acting", "")),
            partners=str(data.get("partners", "")),
            notes=str(data.get("notes", "")),
            tasks=[Task.from_dict(t) for t in data.get("tasks", [])],
            reminded_for_dates=set(data.get("reminded_for_dates", [])),
        )
