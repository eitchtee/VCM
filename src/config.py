import logging

import yaml
import os

from microphone import get_mic_status


logger = logging.getLogger(__name__)


class ConfigReader:
    _instance = None
    _config_file_name = "config.yml"  # Default config file name

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConfigReader, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_file_path=None):
        if self._initialized:
            return
        self._initialized = True

        # Determine config file path
        # Priority: provided path > environment variable > default name
        self._config_file_path = config_file_path
        if self._config_file_path is None:
            self._config_file_path = os.getenv(
                "VCM_CONFIG_PATH", self._config_file_name
            )

        self.config_data = {}
        self._load_config()

        # Set attributes directly for easier access
        self.camera_hotkey = self.get("camera_hotkey")
        self.mic_hotkey = self.get("mic_hotkey")
        self.camera_id = self.get("camera_id")
        self.camera_width = self.get("camera_width")
        self.camera_height = self.get("camera_height")
        self.camera_fps = self.get("camera_fps")
        self.camera_status = False

        logger.info("Attempting to get initial microphone status for config...")
        try:
            # Ensure this call happens after any necessary COM initialization if pycaw requires it
            # on the main thread. For now, assuming microphone.py or pycaw handles it.
            self.mic_active = get_mic_status()  # True if unmuted, False if muted/error
            logger.info(
                f"Config: Initial microphone status from system: {'Active (Unmuted)' if self.mic_active else 'Inactive (Muted)'}"
            )
        except Exception as e:
            logger.error(
                f"Config: Error getting initial mic status: {e}. Defaulting to False (Muted).",
                exc_info=True,
            )
            self.mic_active = False

        self.camera_active = True

    def _load_config(self):
        try:
            with open(self._config_file_path, "r") as f:
                self.config_data = yaml.safe_load(f)
                if self.config_data is None:  # Handle empty YAML file
                    self.config_data = {}
                    print(f"Warning: Config file '{self._config_file_path}' is empty.")
        except FileNotFoundError:
            print(
                f"Error: Config file '{self._config_file_path}' not found. Using default/empty values."
            )
            # Initialize with empty dict or default values if file not found
            self.config_data = {}
        except yaml.YAMLError as e:
            print(f"Error parsing YAML in '{self._config_file_path}': {e}")
            self.config_data = {}  # Or raise an exception / exit

    def get(self, key, default=None):
        """
        Retrieves a configuration value by key.
        Returns the default value if the key is not found.
        """
        return self.config_data.get(key, default)

    def reload_config(self, config_file_path=None):
        """
        Reloads the configuration from the YAML file.
        Can optionally specify a new path.
        """
        if config_file_path:
            self._config_file_path = config_file_path
        # Reset specific attributes
        self._load_config()
        self.camera_hotkey = self.get("camera_hotkey")
        self.mic_hotkey = self.get("mic_hotkey")
        self.camera_id = self.get("camera_id")
        self.camera_width = self.get("camera_width")
        self.camera_height = self.get("camera_height")
        self.camera_fps = self.get("camera_fps")
        # Or re-run the dynamic attribute setting if you chose that path

    def __str__(self):
        return f"ConfigReader(file='{self._config_file_path}', data={self.config_data})"
