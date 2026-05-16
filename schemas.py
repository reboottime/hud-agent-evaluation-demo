"""Pydantic mirror of Oak's ``ClassifierOutputSchema``.

Source: ``apps/backend/src/domain/captures/types.ts`` in the Phoenix monorepo.
Mirrors the four entity variants (``Reading``, ``Workitem``, ``Template``,
``ScheduledEvent``) plus the top-level bundle wrapper. Discriminator is
the ``type`` literal. Fields not exercised by the five PRD cases are
included for parse-faithfulness but not asserted by the eval.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class _EntityBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temp_id: str = Field(min_length=1)


class ReadingEntity(_EntityBase):
    type: Literal["reading"]
    url: HttpUrl
    title: str = Field(min_length=1)
    is_operational: bool
    related_temp_ids: list[str] | None = None


class WorkitemEntity(_EntityBase):
    type: Literal["workitem"]
    kind: Literal["task", "errand"]
    title: str = Field(min_length=1)
    description: str | None = None
    scheduled_date: str | None = None
    scheduled_time: str | None = None
    deadline: str | None = None
    project_id: str | None = None
    priority: str | None = None
    stakes: str | None = None
    domain: str | None = None
    contact_ids: list[str] | None = None
    related_temp_ids: list[str] | None = None


class TemplateEntity(_EntityBase):
    type: Literal["template"]
    title: str = Field(min_length=1)
    cadence: str = Field(min_length=1)
    project_id: str | None = None
    contact_ids: list[str] | None = None
    related_temp_ids: list[str] | None = None


class ScheduledEventEntity(_EntityBase):
    type: Literal["scheduled_event"]
    title: str = Field(min_length=1)
    date: str = Field(min_length=1)
    time: str = Field(min_length=1)
    duration: int | None = Field(default=None, gt=0)
    description: str | None = None
    location: str | None = None
    domain: str | None = None
    contact_ids: list[str] | None = None
    related_temp_ids: list[str] | None = None


Entity = Annotated[
    Union[ReadingEntity, WorkitemEntity, TemplateEntity, ScheduledEventEntity],
    Field(discriminator="type"),
]


class ClassifierOutput(BaseModel):
    """Top-level bundle returned by the classifier."""

    model_config = ConfigDict(extra="forbid")

    entities: list[Entity]
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_reason: str | None = Field(default=None, max_length=120)
