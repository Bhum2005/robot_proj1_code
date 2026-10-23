"""Strip -> model input. Shared by training and the robot (numpy + OpenCV only)."""
import cv2
import numpy as np


def preprocess(strip_bgr: np.ndarray) -> np.ndarray:
    """BGR strip -> float32 (1, 1, H, W), per-image standardised.

    Standardising each strip removes brightness/contrast differences (glare, dim corners)
    before the model sees it.
    """
    g = cv2.cvtColor(strip_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g = (g - g.mean()) / max(float(g.std()), 1.0)
    return g[None, None]


# ---- กระดาษสีอื่น (เพิ่มโดยทีมเรา) ----
def paper_to_white(strip_bgr: np.ndarray) -> np.ndarray:
    """Re-draw a strip of any paper/ink colour as dark ink on white paper (BGR).

    The model was trained on black digits on white paper. For coloured paper we measure how far
    each pixel's colour is from the paper colour (Lab): paper -> white, ink -> black. The blue
    body in the crop margin is also far from the paper colour, so it turns dark, as it looks in
    the white-paper photos the model learnt from. Works for light digits on dark paper too.
    """
    lab = cv2.cvtColor(strip_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    h, w = lab.shape[:2]
    inner = lab[int(h * 0.2):int(h * 0.8), int(w * 0.12):int(w * 0.88)].reshape(-1, 3)
    paper = np.median(inner, axis=0)                 # กระดาษกินพื้นที่มากกว่าตัวเลข
    d = np.linalg.norm(lab - paper, axis=2)
    ink = float(np.percentile(np.linalg.norm(inner - paper, axis=1), 92))
    g = 255.0 * (1.0 - np.clip(d / max(ink, 8.0), 0.0, 1.0))
    g = g.astype(np.uint8)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
