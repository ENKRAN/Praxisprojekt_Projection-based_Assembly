from dataclasses import dataclass

@dataclass
class AppConfig:
    host: str = "0.0.0.0"
    port: int = 5000

    jpeg_quality: int = 80

    width: int = 1280
    height: int = 720
    fps: int = 30

    forward_ws_url: str = "ws://10.42.0.23:9001/ws"
    forward_interval_sec: float = 0.20
    debounce_sec: float = 0.15

    save_dir: str = "data/remote_drawings"
    all_svg_filename: str = "all.svg"
    last_svg_filename: str = "last.svg"
    save_interval_sec: float = 0.20
