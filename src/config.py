import logging

import yaml
import os

from microphone import get_mic_status
from utils.resources import app_dir


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
        # Priority: provided path > environment variable > config.yml next to the app
        self._config_file_path = config_file_path
        if self._config_file_path is None:
            self._config_file_path = os.getenv("VCM_CONFIG_PATH") or os.path.join(
                app_dir(), self._config_file_name
            )

        self.config_data = {}
        self._load_config()

        self._apply_settings()
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
                    logger.warning(
                        f"Config file '{self._config_file_path}' is empty."
                    )
        except FileNotFoundError:
            logger.warning(
                f"Config file '{self._config_file_path}' not found. Using default values."
            )
            # Initialize with empty dict or default values if file not found
            self.config_data = {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML in '{self._config_file_path}': {e}")
            self.config_data = {}  # Or raise an exception / exit

    def _apply_settings(self):
        """Mirror the YAML values onto attributes for convenient access."""
        self.camera_hotkey = self.get("camera_hotkey", "<cmd>+<shift>+a")
        self.mic_hotkey = self.get("mic_hotkey", "<cmd>+<shift>+o")
        self.camera_id = self.get("camera_id", 0)
        self.camera_width = self.get("camera_width", 1280)
        self.camera_height = self.get("camera_height", 720)
        self.camera_fps = self.get("camera_fps", 30)

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
        self._load_config()
        self._apply_settings()

    def __str__(self):
        return f"ConfigReader(file='{self._config_file_path}', data={self.config_data})"
