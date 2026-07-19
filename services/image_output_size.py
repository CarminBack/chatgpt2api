from __future__ import annotations

from io import BytesIO

from PIL import Image

from services.image_access_policy import image_dimensions
from utils.log import logger


def observe_image_output_size(
    image_bytes: bytes,
    *,
    requested_size: object,
    output_size_mode: str,
    identity_id: str,
    model: str,
) -> None:
    if output_size_mode != "observe":
        return
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            actual_width, actual_height = image.size
    except Exception as exc:
        logger.warning({
            "event": "image_output_size_inspect_failed",
            "identity_id": identity_id,
            "model": model,
            "requested_size": str(requested_size or "auto"),
            "error_type": type(exc).__name__,
        })
        return

    requested = image_dimensions(requested_size)
    logger.info({
        "event": "image_output_size_observed",
        "identity_id": identity_id,
        "model": model,
        "requested_size": str(requested_size or "auto"),
        "requested_width": requested[0] if requested else None,
        "requested_height": requested[1] if requested else None,
        "actual_width": actual_width,
        "actual_height": actual_height,
        "exact_match": requested == (actual_width, actual_height) if requested else None,
    })
