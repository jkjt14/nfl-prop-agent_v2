"""A tiny subset of Pydantic tailored for this project."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple, Type


_MISSING = object()


@dataclass
class FieldInfo:
    default: Any = _MISSING
    default_factory: Callable[[], Any] | None = None
    ge: float | None = None
    le: float | None = None
    gt: float | None = None
    lt: float | None = None
    description: str | None = None


def Field(default: Any = _MISSING, *, default_factory: Callable[[], Any] | None = None, **kwargs: Any) -> FieldInfo:
    return FieldInfo(default=default, default_factory=default_factory, **kwargs)


def validator(*fields: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, "_validator_fields", fields)
        return func

    return decorator


def _cast_value(value: Any, annotation: Any) -> Any:
    if isinstance(annotation, str):
        mapping = {"int": int, "float": float, "str": str}
        annotation = mapping.get(annotation, None)
        if annotation is None:
            return value
    try:
        if annotation in (int, float, str):
            return annotation(value)
        if annotation.__name__ == "Path":
            from pathlib import Path

            return Path(value)
    except Exception:
        return value
    return value


class _BaseModelMeta(type):
    def __new__(mcls, name: str, bases: Tuple[type, ...], namespace: Dict[str, Any]):
        annotations = namespace.get("__annotations__", {})
        validators: List[Tuple[Tuple[str, ...], Callable[..., Any]]] = []
        for attr_name, attr_value in list(namespace.items()):
            fields = getattr(attr_value, "_validator_fields", None)
            if fields:
                validators.append((fields, attr_value))
        namespace["__validators__"] = validators
        fields: Dict[str, FieldInfo] = {}
        for field_name, annotation in annotations.items():
            default = namespace.get(field_name, _MISSING)
            if isinstance(default, FieldInfo):
                fields[field_name] = default
                namespace.pop(field_name, None)
            elif default is _MISSING:
                fields[field_name] = FieldInfo()
            else:
                fields[field_name] = FieldInfo(default=default)
        namespace["__fields__"] = fields
        namespace["__annotations__"] = annotations
        return super().__new__(mcls, name, bases, namespace)


class BaseModel(metaclass=_BaseModelMeta):
    __fields__: Dict[str, FieldInfo]
    __validators__: List[Tuple[Tuple[str, ...], Callable[..., Any]]]
    __annotations__: Dict[str, Any]

    def __init__(self, **data: Any) -> None:
        values: Dict[str, Any] = {}
        for name, info in self.__fields__.items():
            if name in data:
                value = data[name]
            elif info.default is not _MISSING:
                value = info.default
            elif info.default_factory is not None:
                value = info.default_factory()
            else:
                raise TypeError(f"Missing required field '{name}'")
            annotation = self.__annotations__.get(name)
            if annotation is not None:
                value = _cast_value(value, annotation)
            if info.ge is not None and value < info.ge:
                raise ValueError(f"Field {name} must be >= {info.ge}")
            if info.le is not None and value > info.le:
                raise ValueError(f"Field {name} must be <= {info.le}")
            if info.gt is not None and value <= info.gt:
                raise ValueError(f"Field {name} must be > {info.gt}")
            if info.lt is not None and value >= info.lt:
                raise ValueError(f"Field {name} must be < {info.lt}")
            values[name] = value
        for fields, validator_fn in self.__validators__:
            for field_name in fields:
                if field_name in values:
                    values[field_name] = validator_fn(self.__class__, values[field_name])
        for name, value in values.items():
            setattr(self, name, value)

    def dict(self) -> Dict[str, Any]:
        return {name: getattr(self, name) for name in self.__fields__}


class BaseSettings(BaseModel):
    class Config:
        env_prefix = ""
        case_sensitive = True

    def __init__(self, **values: Any) -> None:
        config = getattr(self, "Config", BaseSettings.Config)
        prefix = getattr(config, "env_prefix", "")
        case_sensitive = getattr(config, "case_sensitive", True)
        for field_name in self.__fields__:
            env_key = prefix + field_name
            if not case_sensitive:
                env_key = env_key.upper()
            env_value = os.getenv(env_key)
            if env_value is not None and field_name not in values:
                annotation = self.__annotations__.get(field_name)
                values[field_name] = _cast_value(env_value, annotation)
        super().__init__(**values)
