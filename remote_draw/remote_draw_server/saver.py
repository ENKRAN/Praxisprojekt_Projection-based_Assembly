import os
import time

from .state import SharedState
from .config import AppConfig
from .svg_utils import pretty_xml, extract_last_element_svg

def atomic_write_text(path: str, text: str) -> None:
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp_path, path)

def saver_loop(state: SharedState, cfg: AppConfig) -> None:
    os.makedirs(cfg.save_dir, exist_ok=True)
    all_svg_path = os.path.join(cfg.save_dir, cfg.all_svg_filename)
    last_svg_path = os.path.join(cfg.save_dir, cfg.last_svg_filename)

    while True:
        time.sleep(cfg.save_interval_sec)

        with state.lock:
            dirty = state.dirty_svg
            last_change = state.last_change_ts
            svg = state.latest_svg

        if not dirty:
            continue
        if (time.time() - last_change) < cfg.debounce_sec:
            continue

        try:
            formatted_all = pretty_xml(svg)
            if formatted_all:
                atomic_write_text(all_svg_path, formatted_all)

            last_svg_doc = extract_last_element_svg(svg)
            if last_svg_doc:
                atomic_write_text(last_svg_path, pretty_xml(last_svg_doc))

            with state.lock:
                state.dirty_svg = False

        except Exception as e:
            print("Saver: failed to write SVG files:", e)
