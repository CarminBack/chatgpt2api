from __future__ import annotations

import re
from dataclasses import dataclass

from services.config import config


RESOLUTION_TIER_LIMITS = {
    "1k": (1024, 1024 * 1024),
    "2k": (2048, 2048 * 2048),
    "4k": (3840, 3840 * 2160),
}
OUTPUT_SIZE_MODES = {"passthrough", "observe"}


class ImageAccessPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class ImageKeyPolicy:
    max_resolution_tier: str = ""
    output_size_mode: str = "passthrough"
    route_model: str = ""


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


def image_key_policy(identity: dict[str, object]) -> ImageKeyPolicy:
    identity_id = str(identity.get("id") or "").strip()
    raw = config.image_key_policies.get(identity_id)
    if not isinstance(raw, dict):
        return ImageKeyPolicy()
    tier = str(raw.get("max_resolution_tier") or "").strip().lower()
    if tier not in RESOLUTION_TIER_LIMITS:
        tier = ""
    output_size_mode = str(raw.get("output_size_mode") or "passthrough").strip().lower()
    if output_size_mode not in OUTPUT_SIZE_MODES:
        output_size_mode = "passthrough"
    return ImageKeyPolicy(
        max_resolution_tier=tier,
        output_size_mode=output_size_mode,
        route_model=str(raw.get("route_model") or "").strip(),
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


def apply_image_request_policy(
    identity: dict[str, object],
    payload: dict[str, object],
) -> dict[str, object]:
    result = dict(payload)
    result["size"] = constrain_image_size(identity, result.get("size"))
    policy = image_key_policy(identity)

    if policy.max_resolution_tier:
        dimensions = image_dimensions(result.get("size"))
        if dimensions:
            max_side, max_pixels = RESOLUTION_TIER_LIMITS[policy.max_resolution_tier]
            if max(dimensions) > max_side or dimensions[0] * dimensions[1] > max_pixels:
                raise ImageAccessPolicyError(
                    f"This API key supports image resolutions up to {policy.max_resolution_tier.upper()}."
                )

    if policy.route_model:
        result["model"] = policy.route_model
    if policy.output_size_mode != "passthrough":
        result["_image_output_size_mode"] = policy.output_size_mode
        result["_image_policy_identity_id"] = str(identity.get("id") or "").strip()
    return result
