# VCM - Video Conference Mute

**A utility to quickly mute/unmute your microphone and enable/disable your camera feed via global hotkeys, with a persistent on-screen display for status.**

VCM enhances your video conferencing experience by providing rapid, system-wide control over your microphone and camera, ensuring you're only seen and heard when you intend to be.

This is an alternative to the removed Powertoys' feature Video Conference Mute.

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

### Installation

1. Download the zipped file from [latest release](https://github.com/eitchtee/VCM/releases/latest)
2. Unzip the files to where you want VCM to be
3. [Edit config.yml](#configuration-details)
4. Run `RegisterSoftcam.bat`, Windows will ask for administrative rights, allow it.
5. Launch `VCM.exe`

#### Softcam

VCM comes bundled with pre-built [softcam's](https://github.com/tshino/softcam) dll and python bindings for Windows x64, you can also compile your own version and replace the files inside `<your vcm folder>/_internal/softcam/`


### Unninstall

1. Run `UnregisterSoftcam.bat`, Windows will ask for administrative rights, allow it.
2. Delete VCM's folder


## How to Use

* **Hotkeys**:
    * Press the hotkey configured for `camera_hotkey` (e.g., `Ctrl+Shift+C`) to toggle the camera feed between your webcam and a black screen being sent to the "VCM Virtual Camera".
    * Press the hotkey configured for `mic_hotkey` (e.g., `Ctrl+Shift+M`) to mute or unmute your system microphone.
* **On-Screen Display (OSD)**:
    * The OSD will appear in the bottom-right of your screen whenever your microphone is muted OR your camera feed is set to "disabled" (black screen).
    * It shows the current status of both the camera and microphone using icons.
* **Virtual Camera**:
    * In your video conferencing application (Zoom, OBS, Google Meet, etc.), select "VCM" as your video source.
    * VCM will automatically start feeding video (or a black screen) when the application starts using the virtual camera.
    * The physical webcam light should turn on/off as VCM acquires/releases it based on usage.
* **System Tray Icon**:
    * Look for the VCM icon in your system tray.
    * Right-click it and select "Exit VCM" to close the application.

## Configuration Details

Edit the pre-bundled `config.yaml` file in your VCM folder.

**Example `config.yaml`:**

```yaml
# Hotkey to toggle the camera feed (webcam vs. black screen)
# Format: Modifiers (Ctrl, Alt, Shift, Win/Cmd) + Key (e.g., C, M, F1)
# Ensure these are not commonly used by other applications or your OS.
# Have a look at https://pynput.readthedocs.io/en/latest/keyboard.html#pynput.keyboard.Key for available modifiers

camera_hotkey: "<cmd>+<shift>+a"
# Hotkey to toggle the system microphone mute state. Same rules as camera_hotkey
mic_hotkey: "<cmd>+<shift>+o"

# --- Camera Settings ---
# ID of the physical webcam to use.
# Usually 0 for the default built-in webcam. Try 1, 2, etc., if you have multiple.
camera_id: 0

# Desired resolution for the camera feed (and virtual camera output)
camera_width: 1280
camera_height: 720

# Desired frames per second for the camera feed
camera_fps: 30
