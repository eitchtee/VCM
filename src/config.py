import json
import os


class Config:
    def __init__(self):
        self.filename: str = "config.json"

        self.camera_toggle_hotkey: str | None = None
        self.mic_toggle_hotkey: str | None = None
        self.selected_camera_id: int | None = None

        self.enable_camera_function: bool | None = None
        self.enable_mic_function: bool | None = None

        self.load()
        self.save()

    def load(self) -> None:
        """Load configuration from file"""

        if not os.path.exists(self.filename):  # sane defaults
            self.camera_toggle_hotkey = "<cmd>+<shift>+a"
            self.mic_toggle_hotkey = "<cmd>+<shift>+o"
            self.selected_camera_id = 0
            self.enable_camera_function = True
            self.enable_mic_function = True

            self.save()
        else:
            try:
                with open(self.filename, "r") as f:
                    config_data = json.load(f)

                    self.camera_toggle_hotkey = config_data.get("camera_toggle_hotkey")
                    self.mic_toggle_hotkey = config_data.get("mic_toggle_hotkey")
                    self.selected_camera_id = config_data.get("selected_camera_id")
                    self.enable_camera_function = config_data.get(
                        "enable_camera_function"
                    )
                    self.enable_mic_function = config_data.get("enable_mic_function")

            except Exception as e:
                print(f"Error loading config: {e}")

    def save(self) -> None:
        """Save configuration to file"""

        config_data = {
            "camera_toggle_hotkey": self.camera_toggle_hotkey,
            "mic_toggle_hotkey": self.mic_toggle_hotkey,
            "selected_camera_id": self.selected_camera_id,
            "enable_camera_function": self.enable_camera_function,
            "enable_mic_function": self.enable_mic_function,
        }

        try:
            with open(self.filename, "w") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")
