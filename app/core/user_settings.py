import json
import os
from pathlib import Path
from typing import Dict, Any

class UserSettings:
    # Path to the config file
    SETTINGS_PATH = Path("data/user_config.json")
    DEFAULT_TAG_SIZE = 0.073

    @classmethod
    def load(cls) -> Dict[str, Any]:
        """Loads settings. Returns a dict with defaults if no file exists."""
        if not cls.SETTINGS_PATH.exists():
            return {"tag_size": cls.DEFAULT_TAG_SIZE}
        
        try:
            with open(cls.SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "tag_size" not in data:
                    data["tag_size"] = cls.DEFAULT_TAG_SIZE
                return data
        except Exception as e:
            print(f"Warning: Could not load settings: {e}")
            return {"tag_size": cls.DEFAULT_TAG_SIZE}

    @classmethod
    def get_tag_size(cls) -> float:
        settings = cls.load()
        return float(settings.get("tag_size", cls.DEFAULT_TAG_SIZE))

    @classmethod
    def get_ssh_host(cls) -> str:
        return str(cls.load().get("ssh_host", ""))

    @classmethod
    def get_ssh_user(cls) -> str:
        return str(cls.load().get("ssh_user", ""))

    @classmethod
    def get_ssh_key_path(cls) -> str:
        return str(cls.load().get("ssh_key_path", ""))

    @classmethod
    def get_remote_script_path(cls) -> str:
        return str(cls.load().get("remote_script_path", ""))

    @classmethod
    def get_remote_work_dir(cls) -> str:
        return str(cls.load().get("remote_work_dir", "/tmp/ar_ai_work"))

    @classmethod
    def get_remote_python_path(cls) -> str:
        return str(cls.load().get("remote_python_path", "python3"))

    @classmethod
    def save(cls, data: Dict[str, Any]):
        """Saves the dictionary to the JSON file."""
        try:
            # Ensure the directory exists
            cls.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            with open(cls.SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            print(f"Settings saved to {cls.SETTINGS_PATH}")
        except Exception as e:
            print(f"Error saving settings: {e}")