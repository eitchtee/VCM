import logging
from logging.handlers import RotatingFileHandler

import os
import sys
import threading

if hasattr(sys, "_MEIPASS"):
    # Running in a PyInstaller bundle, place logs next to the executable
    log_dir = os.path.dirname(sys.executable)
else:
    # Running as a script, place logs in the script's directory
    log_dir = os.path.abspath(os.path.dirname(__file__))

log_file_path = os.path.join(log_dir, "vcm_app.log")

# Log rotation parameters
max_log_size_bytes = 1 * 1024 * 1024  # 1 MB per log file
backup_log_count = (
    3  # Number of backup files to keep (e.g., vcm_app.log, vcm_app.log.1, ... .3)
)

# Get the root logger instance
# All loggers created with logging.getLogger(__name__) will inherit this configuration
root_logger = logging.getLogger()
root_logger.setLevel(
    logging.INFO
)  # Set the desired logging level (e.g., INFO or DEBUG)

# Clear any existing handlers from the root logger to avoid duplicate logs
# or conflicts if basicConfig was called by a library (though unlikely for root).
if root_logger.hasHandlers():
    root_logger.handlers.clear()

# Create a rotating file handler
# This handler writes to `log_file_path`. When the file reaches `maxBytes`,
# it's renamed (e.g., to vcm_app.log.1), and a new `vcm_app.log` is started.
# `backupCount` determines how many old log files are kept.
try:
    rotating_file_handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=max_log_size_bytes,
        backupCount=backup_log_count,
        encoding="utf-8",  # Explicitly set encoding for cross-platform compatibility
    )
except PermissionError:
    # Fallback in case of permission issues (e.g., running from a restricted directory)
    # Try logging to a user's temp directory as a last resort for this session.
    # This is a basic fallback; more robust error handling might be needed for production.
    import tempfile

    fallback_log_dir = tempfile.gettempdir()
    log_file_path = os.path.join(fallback_log_dir, "vcm_app_fallback.log")
    rotating_file_handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=max_log_size_bytes,
        backupCount=backup_log_count,
        encoding="utf-8",
    )
    logging.warning(
        f"Original log path had permission issues. Logging to fallback: {log_file_path}"
    )


# Define the log message format
log_formatter = logging.Formatter(
    "%(asctime)s - %(threadName)s - [%(name)s:%(lineno)d] - %(levelname)s - %(message)s"
)
rotating_file_handler.setFormatter(log_formatter)

# Add the configured rotating file handler to the root logger
root_logger.addHandler(rotating_file_handler)

# Optional: If you ALSO want console output during development (in addition to the file)
# uncomment the following lines:
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)  # Set level for console output if different
console_handler.setFormatter(log_formatter)  # Use the same or a different formatter
root_logger.addHandler(console_handler)

from pynput import keyboard
from PIL import Image, ImageDraw  # Still needed for pystray
import pystray
from pystray import MenuItem as item

from config import ConfigReader
from microphone import (
    set_mic_mute as system_set_mic_mute,
    get_mic_status as get_system_mic_status,
)
from camera import CameraManager
from osd import OSDDisplay  # Import the new OSD class

from utils.resources import resource_path


logger = logging.getLogger(__name__)  # Get a logger for main.py scope


# --- Global Variables ---
config = None
hotkey_listener = None
tray_icon_instance = None
osd_manager = None
camera_manager = None
exit_event = threading.Event()  # For gracefully exiting the main thread


# --- Configuration Loading --- (same as before)
def load_configuration():
    global config
    config = ConfigReader()
    logger.info("Configuration loaded in main.")
    # Log specific config details if needed for debugging
    logger.debug(
        f"Camera Hotkey: {config.camera_hotkey}, Mic Hotkey: {config.mic_hotkey}"
    )
    logger.debug(
        f"Initial states: CameraActive={config.camera_active}, MicActive={config.mic_active}"
    )


# --- Hotkey Processing Functions ---
def on_camera_hotkey_press():
    """Placeholder for camera hotkey - Toggles config.camera_active."""
    if config is None:
        logger.error("Config not loaded, cannot toggle camera.")
        if osd_manager:
            osd_manager.update()  # Still update OSD to show error potentially
        return

    config.camera_active = not config.camera_active
    status_message = "Camera ON" if config.camera_active else "Camera OFF"
    logger.info(f"Camera hotkey pressed. New placeholder state: {status_message}")

    if osd_manager:
        osd_manager.update()  # Trigger OSD update


def on_mic_hotkey_press():  # (Updated version from previous step, ensure it's this one)
    if config is None:
        logger.error("Configuration not loaded, cannot toggle microphone.")
        if osd_manager:
            osd_manager.update()
        return

    logger.info(
        f"Mic hotkey ({config.mic_hotkey}) pressed. "
        f"Current config.mic_active: {'Active' if config.mic_active else 'Inactive'}"
    )
    should_os_mic_be_muted = config.mic_active
    success = system_set_mic_mute(should_os_mic_be_muted)

    if success:
        config.mic_active = not config.mic_active
        new_status_message = "Microphone ON" if config.mic_active else "Microphone OFF"
        logger.info(
            f"OS mic state changed. New config.mic_active: {new_status_message}"
        )
    else:
        logger.error("Failed to change OS mic state.")
        # Re-sync config with actual system state on failure
        actual_system_status_active = get_system_mic_status()
        if config.mic_active != actual_system_status_active:
            logger.warning(
                f"Config mic state out of sync. Correcting. System: {'Active' if actual_system_status_active else 'Inactive'}"
            )
            config.mic_active = actual_system_status_active

    if osd_manager:
        osd_manager.update()  # Trigger OSD update


def format_hotkey_for_pynput(hotkey_str):  # (same as before)
    # ... (implementation from previous steps)
    if not hotkey_str:
        return None
    parts = hotkey_str.lower().split("+")
    formatted_parts = []
    for part_original in parts:
        part = part_original.strip()
        if part in ["ctrl", "alt", "shift", "cmd", "win", "super", "control"]:
            formatted_parts.append(
                f"<{part.replace('control', 'ctrl')}>"
            )  # Normalize control
        else:
            formatted_parts.append(
                part_original.lower()
            )  # pynput usually takes lowercase for char keys
    return "+".join(formatted_parts)


def setup_hotkeys():  # (Modified to include camera hotkey)
    global hotkey_listener
    if not config:
        logger.error("Config not loaded. Cannot set up hotkeys.")
        return

    camera_hotkey_str = format_hotkey_for_pynput(config.camera_hotkey)
    mic_hotkey_str = format_hotkey_for_pynput(config.mic_hotkey)

    hotkey_actions = {}
    if camera_hotkey_str:
        hotkey_actions[camera_hotkey_str] = on_camera_hotkey_press
        logger.info(
            f"Registered Camera Hotkey: {config.camera_hotkey} -> {camera_hotkey_str}"
        )
    else:
        logger.warning(
            f"Camera hotkey '{config.camera_hotkey}' invalid or not defined."
        )

    if mic_hotkey_str:
        hotkey_actions[mic_hotkey_str] = on_mic_hotkey_press
        logger.info(f"Registered Mic Hotkey: {config.mic_hotkey} -> {mic_hotkey_str}")
    else:
        logger.warning(f"Mic hotkey '{config.mic_hotkey}' invalid or not defined.")

    if not hotkey_actions:
        logger.warning("No valid hotkeys configured.")
        return

    try:
        hotkey_listener = keyboard.GlobalHotKeys(hotkey_actions)
        hotkey_listener.start()  # Runs in its own thread
        logger.info("Hotkey listener started.")
    except Exception as e:
        logger.error(f"Failed to start hotkey listener: {e}", exc_info=True)


# --- System Tray Icon Functions ---
def get_tray_icon_image():
    icon_path = resource_path("resources/logo.png")
    try:
        image = Image.open(icon_path)
    except FileNotFoundError:
        logger.warning(f"Tray icon '{icon_path}' not found. Creating placeholder.")
        image = Image.new("RGB", (64, 64), "blue")
        ImageDraw.Draw(image).text((10, 25), "VCM", fill="white")
    except Exception as e:
        logger.error(f"Error loading tray icon: {e}. Using placeholder.", exc_info=True)
        image = Image.new("RGB", (64, 64), "grey")  # Different placeholder on error
    return image


def on_quit_vcm(icon, item_or_event=None):
    logger.info("Exit selected. Shutting down VCM...")

    # Stop Camera Manager first
    if camera_manager:
        logger.info("Stopping camera manager...")
        camera_manager.stop()  # This will signal its thread and join

    if hotkey_listener:
        logger.info("Stopping hotkey listener...")
        try:
            hotkey_listener.stop()
        except Exception as e:
            logger.error(f"Error stopping hotkey listener: {e}", exc_info=True)

    if osd_manager:
        logger.info("Closing OSD manager...")
        osd_manager.close()

    if tray_icon_instance:
        logger.info("Stopping tray icon...")
        try:
            tray_icon_instance.stop()
        except Exception as e:
            logger.error(f"Error stopping tray icon: {e}", exc_info=True)

    logger.info("Setting exit event for main thread.")
    exit_event.set()


def setup_tray_icon():
    global tray_icon_instance
    image = get_tray_icon_image()
    menu = (item("Exit VCM", on_quit_vcm),)
    tray_icon_instance = pystray.Icon("VCM", image, "VCM - Video Conference Mute", menu)

    def run_tray():
        logger.info("Tray icon thread started.")
        try:
            tray_icon_instance.run()
        finally:
            logger.info("Tray icon thread finished.")
            # If tray finishes unexpectedly, it might be good to trigger a shutdown
            if not exit_event.is_set():
                logger.warning("Tray icon stopped unexpectedly. Initiating shutdown.")
                on_quit_vcm(tray_icon_instance)  # Pass icon for consistency

    tray_thread = threading.Thread(target=run_tray, daemon=True, name="TrayIconThread")
    tray_thread.start()


# --- Main Application Logic ---
def main():
    global osd_manager, camera_manager

    load_configuration()

    osd_manager = OSDDisplay(config)
    osd_manager.start()

    # Initialize and start the Camera Manager
    camera_manager = CameraManager(config)
    camera_manager.start()

    setup_hotkeys()
    setup_tray_icon()

    logger.info("VCM application is running. Main thread waiting for exit signal.")
    try:
        exit_event.wait()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received in main thread. Shutting down...")
        on_quit_vcm(None)
    finally:
        logger.info("Main thread exiting.")


if __name__ == "__main__":
    main()
