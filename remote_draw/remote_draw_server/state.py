import threading
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

@dataclass
class SharedState:
    lock: threading.Lock = field(default_factory=threading.Lock)

    latest_frame_bgr: Optional[np.ndarray] = None
    latest_svg: str = ""

    dirty_svg: bool = False
    forward_dirty: bool = False

    last_change_ts: float = 0.0
    last_forward_sent: str = ""
