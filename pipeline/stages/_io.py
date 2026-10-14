"""Reading and writing validated JSON artifacts."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from pipeline.runner import StageError


def write_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")


def read_model(path: Path, model_type: type[BaseModel] | TypeAdapter) -> Any:
    """Load JSON into a model class, or into a TypeAdapter (used for the storyboard union)."""
    if not path.is_file():
        raise StageError(f"Missing {path.name}; run the earlier stages first ({path})")
    text = path.read_text(encoding="utf-8")
    try:
        if isinstance(model_type, TypeAdapter):
            return model_type.validate_json(text)
        return model_type.model_validate_json(text)
    except ValidationError as error:
        raise StageError(f"{path.name} is invalid: {error}") from error
