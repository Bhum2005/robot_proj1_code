"""Robot-facing entry point. Needs only OpenCV + numpy (Pi: OpenCV 4.6, numpy 1.24)."""
from __future__ import annotations

import threading

import cv2
import numpy as np

from meter_ai.reader import MeterReader

# Below this the robot shows no suggestion. On 26 real photos x 4 orientations no wrong
# reading reached 0.6 (highest wrong: 0.48); 81/104 readings were suggested, all correct.
SUGGEST_THRESHOLD = 0.6

_reader: MeterReader | None = None
_lock = threading.Lock()          # cv2.dnn.Net is not thread-safe; Flask is multi-threaded


def _get_reader() -> MeterReader:
    global _reader
    if _reader is None:
        _reader = MeterReader()
    return _reader


def warm_up() -> None:
    """Load the model now (call at server start) so the first capture is not slow."""
    with _lock:
        _get_reader()


def read_meter(frame_bgr: np.ndarray, meter_type: str | None = None,
               threshold: float = SUGGEST_THRESHOLD) -> tuple[str | None, float, np.ndarray | None]:
    """Read the 4-digit meter in a BGR frame of any size.

    Returns (digits or None if confidence < threshold, confidence 0..1, debug image or None).
    The debug image is the upright digit strip the model read, enlarged 2x.
    `meter_type` ("water"/"elec") is accepted for the interface; both use the same model.
    """
    if not isinstance(frame_bgr, np.ndarray) or frame_bgr.ndim != 3 or frame_bgr.size == 0:
        return None, 0.0, None
    with _lock:
        reading = _get_reader().read(frame_bgr)
    if reading.strip is None:
        return None, 0.0, None
    debug = cv2.resize(reading.strip.image, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    digits = reading.digits if reading.confidence >= threshold else None
    return digits, reading.confidence, debug
