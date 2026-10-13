"""Reading and writing validated JSON artifacts."""

from pathlib import Path

from pydantic import BaseModel, ValidationError

from pipeline.runner import StageError


def write_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")


def read_model[M: BaseModel](path: Path, model_type: type[M]) -> M:
    if not path.is_file():
        raise StageError(f"Missing {path.name}; run the earlier stages first ({path})")
    try:
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise StageError(f"{path.name} is invalid: {error}") from error
