from __future__ import annotations

import re

from services.config import config


def image_dimensions(size: object) -> tuple[int, int] | None:
    numbers = [int(item) for item in re.findall(r"\d+", str(size or ""))]
    if len(numbers) >= 2:
        return max(1, numbers[0]), max(1, numbers[1])
    if len(numbers) == 1:
        side = max(1, numbers[0])
        return side, side
    return None


def image_max_side(size: object) -> int:
    dimensions = image_dimensions(size)
    return max(dimensions) if dimensions else 1024


def is_1k_only_identity(identity: dict[str, object]) -> bool:
    if "sub2api" not in str(identity.get("source") or ""):
        return False
    try:
        user_id = int(identity.get("sub2api_user_id") or 0)
    except (TypeError, ValueError):
        user_id = 0
    try:
        key_id = int(identity.get("sub2api_key_id") or 0)
    except (TypeError, ValueError):
        key_id = 0
    return (
        user_id in config.image_1k_only_sub2api_user_ids
        or key_id in config.image_1k_only_sub2api_key_ids
    )


def constrain_image_size(identity: dict[str, object], size: object) -> object:
    if not is_1k_only_identity(identity):
        return size
    dimensions = image_dimensions(size)
    if not dimensions:
        return size
    max_side = max(dimensions)
    if max_side <= 1024:
        return size
    scale = 1024 / max_side
    width = min(1024, max(1, round(dimensions[0] * scale)))
    height = min(1024, max(1, round(dimensions[1] * scale)))
    return f"{width}x{height}"
