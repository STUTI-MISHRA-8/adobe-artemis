"""Defensive normalization for LLM-produced enum fields.

LLMs occasionally put a value from one field's vocabulary into another
similarly-shaped field (e.g. an observation "type" value like "integration"
leaking into "aep_relevance"). Rather than dropping the whole
requirement/task/observation when that happens — which would silently
violate the "never lose a requirement" guarantee — we coerce unrecognized
values to a safe default and keep the item.
"""

from app.models import AEPLayer, FlagType, Priority

_VALID_LAYERS = {e.value for e in AEPLayer}
_VALID_PRIORITIES = {e.value for e in Priority}
_VALID_FLAGS = {e.value for e in FlagType}


def sanitize_layer(value) -> str:
    return value if value in _VALID_LAYERS else "general"


def sanitize_priority(value) -> str:
    return value if value in _VALID_PRIORITIES else "medium"


def sanitize_flags(values) -> list:
    if not isinstance(values, list):
        return []
    return [v for v in values if v in _VALID_FLAGS]
