"""Contrato común de entrada y salida de la API.

Los dos motores (tradicional y generativo) devuelven esta misma estructura.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Category = Literal["ACCESS", "BUG", "FEATURE", "SECURITY"]
Priority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Mode = Literal["traditional", "generative"]

MAX_MESSAGE_LENGTH = 10000  # mismo límite que valida el motor generativo


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(max_length=MAX_MESSAGE_LENGTH)
    mode: Mode

    @field_validator("message")
    @classmethod
    def message_no_vacio(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("El mensaje no puede estar vacío")
        return value


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category
    priority: Priority
    response: str = Field(min_length=1, max_length=2000)
    requiresHumanReview: bool
    mode: Mode

    @model_validator(mode="after")
    def security_requiere_revision(self) -> "AnalyzeResponse":
        # Regla del contrato: todo incidente SECURITY pasa por una persona.
        if self.category == "SECURITY":
            self.requiresHumanReview = True
        return self
