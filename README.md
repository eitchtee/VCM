# VCM - Video Conference Mute

**A utility to quickly mute/unmute your microphone and enable/disable your camera feed via global hotkeys, with a persistent on-screen display for status and a virtual camera output.**

VCM enhances your video conferencing experience by providing rapid, system-wide control over your microphone and camera, ensuring you're only seen and heard when you intend to be.

## Overview

In the age of constant video calls, fumbling for mute buttons or camera toggles within different applications can be cumbersome and error-prone. VCM (Video Conference Mute) solves this by offering:

* **Global Hotkeys**: Instantly toggle your microphone and camera state from any application.
* **On-Screen Display (OSD)**: A sleek, minimal OSD appears in the bottom-right of your screen when your microphone is muted OR your camera feed is disabled, providing clear visual feedback.
* **Virtual Camera Control**: VCM manages a virtual camera feed. When enabled, it relays your physical webcam. When "disabled" via the hotkey, it outputs a black screen to the virtual camera, effectively hiding your video without stopping the virtual camera device itself. It also intelligently releases your physical webcam when the virtual camera is not being actively used by any application.
* **System Tray Access**: Easily exit the application via a system tray icon.
* **Customizable Configuration**: Set your preferred hotkeys, camera device, and resolution.

## Core Features

* **Microphone Control**: Global hotkey to mute/unmute the system's default microphone.
* **Camera Feed Control**: Global hotkey to "enable" (webcam feed) or "disable" (black screen feed) to the virtual camera.
* **Smart Webcam Release**: The physical webcam is only active when the virtual camera is being consumed by an application AND the VCM camera feed is enabled.
* **Persistent On-Screen Display (OSD)**:
    * Displays icons for camera and microphone status.
    * Visible when the microphone is muted OR the camera is "disabled".
    * Positioned in the bottom-right corner.
* **System Tray Icon**: Provides an "Exit VCM" option for convenient shutdown.
* **Configuration via `config.yaml`**: Easily customize hotkeys, camera ID, resolution, and FPS.
* **Virtual Camera Output**: Creates a virtual camera named "VCM Virtual Camera" (customizable in `camera.py`) that applications can use.

## Getting Started

### Prerequisites

* **Python 3.7+**
* **Windows Operating System**: Currently, VCM is primarily designed for Windows due to some specific libraries used (e.g., `pycaw` for microphone control, `cv2.CAP_DSHOW` for camera).
* **`softcam` Virtual Camera Backend**:
    * This project relies on a virtual camera backend library. The code in `camera.py` is set up to import it as `from x64.Release import softcam`.
    * You will need to have this specific module available or adapt `camera.py` to use another virtual camera library like `pyvirtualcam`.
    * If the specified `softcam` module is not found, VCM will run with a **mock camera backend**, which simulates virtual camera behavior for testing the application's UI and logic but won't produce an actual virtual camera device.
* **Physical Webcam**: Required for the camera feed feature.

### Installation & Setup

1.  **Clone or Download:**
    ```bash
    # If you have git installed
    git clone [https://github.com/yourusername/VCM.git](https://github.com/yourusername/VCM.git)
    cd VCM
    # Otherwise, download and extract the ZIP file.
    ```

2.  **Install Dependencies:**
    It's recommended to use a virtual environment.
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    # source venv/bin/activate

    pip install -r requirements.txt
    ```
    If `requirements.txt` is not provided, install manually:
    ```bash
    pip install PyYAML pynput Pillow pystray opencv-python pycaw comtypes
    ```

3.  **Prepare Resources:**
    * **OSD Icons**: Create the following folder structure and place your 16x16 (or similar small size) PNG icons inside:
        ```
        VCM/
        ├── resources/
        │   └── icons/
        │       ├── camera_active.png
        │       ├── camera_inactive.png
        │       ├── mic_active.png
        │       └── mic_inactive.png
        ```
        If icons are missing, the OSD will display placeholder colored squares.
    * **System Tray Icon**: Place a `icon.png` (e.g., 64x64 pixels) in the root `VCM/` directory. A placeholder will be used if not found.

4.  **Configure `config.yaml`:**
    Create a `config.yaml` file in the root `VCM/` directory. See the [Configuration Details](#configuration-details) section below for an example and explanations.

5.  **Run VCM:**
    ```bash
    python main.py
    ```

## How to Use

* **Hotkeys**:
    * Press the hotkey configured for `camera_hotkey` (e.g., `Ctrl+Shift+C`) to toggle the camera feed between your webcam and a black screen being sent to the "VCM Virtual Camera".
    * Press the hotkey configured for `mic_hotkey` (e.g., `Ctrl+Shift+M`) to mute or unmute your system microphone.
* **On-Screen Display (OSD)**:
    * The OSD will appear in the bottom-right of your screen whenever your microphone is muted OR your camera feed is set to "disabled" (black screen).
    * It shows the current status of both the camera and microphone using icons.
* **Virtual Camera**:
    * In your video conferencing application (Zoom, OBS, Google Meet, etc.), select "VCM Virtual Camera" (or the name configured in `camera.py`) as your video source.
    * VCM will automatically start feeding video (or a black screen) when the application starts using the virtual camera.
    * The physical webcam light should turn on/off as VCM acquires/releases it based on usage.
* **System Tray Icon**:
    * Look for the VCM icon in your system tray.
    * Right-click it and select "Exit VCM" to close the application.

## Configuration Details

Create a `config.yaml` file in the same directory as `main.py`. You can also set the `VCM_CONFIG_PATH` environment variable to point to a custom location for `config.yaml`.

**Example `config.yaml`:**

```yaml
# Hotkey to toggle the camera feed (webcam vs. black screen)
# Format: Modifiers (Ctrl, Alt, Shift, Win/Cmd) + Key (e.g., C, M, F1)
# Ensure these are not commonly used by other applications or your OS.
camera_hotkey: "Ctrl+Shift+C"

# Hotkey to toggle the system microphone mute state
mic_hotkey: "Ctrl+Shift+M"

# --- Camera Settings ---
# ID of the physical webcam to use.
# Usually 0 for the default built-in webcam. Try 1, 2, etc., if you have multiple.
camera_id: 0

# Desired resolution for the camera feed (and virtual camera output)
camera_width: 1280
camera_height: 720

# Desired frames per second for the camera feed
camera_fps: 30
