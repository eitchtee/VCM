import os
import sys
import threading
import time
import tkinter as tk
from queue import Queue

import pystray
from PIL import Image, ImageDraw, ImageTk
from pynput import keyboard

from src.camera import CameraControl
from src.config import Config
from src.microphone import MicrophoneControl
from src.version import __version__


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class OSDDisplay:
    def __init__(self, parent):
        self.parent = parent
        self.window = None
        self.visible = False
        self.update_queue = Queue()
        self.running = False

        self.bg_color = "#1E1E1E"  # Dark modern background

    def start(self):
        """Start the OSD in its own thread"""
        threading.Thread(target=self._run_osd_loop, daemon=True).start()

    def _load_icons(self):
        """Load icon images or create fallbacks if files not found"""
        icon_size = (12, 12)

        camera_active_path = resource_path("resources/icons/camera_active.png")
        camera_inactive_path = resource_path("resources/icons/camera_inactive.png")

        camera_active_img = Image.open(camera_active_path).resize(icon_size)
        camera_inactive_img = Image.open(camera_inactive_path).resize(icon_size)

        self.camera_active_icon = ImageTk.PhotoImage(camera_active_img)
        self.camera_inactive_icon = ImageTk.PhotoImage(camera_inactive_img)

        mic_active_path = resource_path("resources/icons/mic_active.png")
        mic_inactive_path = resource_path("resources/icons/mic_inactive.png")

        mic_active_img = Image.open(mic_active_path).resize(icon_size)
        mic_inactive_img = Image.open(mic_inactive_path).resize(icon_size)

        self.mic_active_icon = ImageTk.PhotoImage(mic_active_img)
        self.mic_inactive_icon = ImageTk.PhotoImage(mic_inactive_img)

    def _run_osd_loop(self):
        """Run the tkinter main loop in its own thread"""
        self.window = tk.Tk()
        self.window.overrideredirect(True)  # Remove window decorations
        self.window.attributes("-topmost", True)  # Keep on top
        self.window.attributes("-alpha", 0.8)  # Make it semi-transparent

        # Load icons
        self._load_icons()

        # Create the main frame
        self.frame = tk.Frame(self.window, bg=self.bg_color, padx=12, pady=8)
        self.frame.pack()

        # Create icons container
        self.icons_frame = tk.Frame(self.frame, bg=self.bg_color)
        self.icons_frame.pack(pady=2)

        # Create and place camera icon
        self.camera_label = tk.Label(
            self.icons_frame, image=self.camera_inactive_icon, bg=self.bg_color
        )
        self.camera_label.pack(side=tk.LEFT, padx=(0, 5))

        # Create separator
        self.separator = tk.Frame(self.icons_frame, width=1, bg="#555555")
        self.separator.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)

        # Create and place microphone icon
        self.mic_label = tk.Label(
            self.icons_frame, image=self.mic_inactive_icon, bg=self.bg_color
        )
        self.mic_label.pack(side=tk.LEFT, padx=(5, 0))

        # Position window in bottom right
        self._position_window()

        # Make window appear without being clickable
        self.window.lift()

        # Hide window initially
        self.window.withdraw()
        self.visible = False

        # Start the update checking
        self.running = True
        self._check_for_updates()

        # Start tkinter main loop
        self.window.mainloop()

    def _position_window(self):
        """Position the window in bottom right corner"""
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()

        # Get window size
        self.window.update_idletasks()
        width = self.frame.winfo_reqwidth() + 20  # Add padding
        height = self.frame.winfo_reqheight() + 20

        # Position in bottom right with some padding
        x = screen_width - width - 20
        y = screen_height - height - 20
        self.window.geometry(f"+{x}+{y}")

    def _check_for_updates(self):
        """Check for update requests in the queue"""
        if not self.running and self.update_queue.empty():
            return

        # Process all updates in the queue
        while not self.update_queue.empty():
            update_fn = self.update_queue.get()
            update_fn()

        # Schedule next check
        self.window.after(100, self._check_for_updates)

    def update(self):
        """Queue an update to be processed by the tkinter thread"""
        if not self.running:
            return

        # Create a function for the update that will be executed in the tkinter thread
        def do_update():
            # Get current states
            camera_active = self.parent.camera.camera_active
            mic_active = self.parent.mic.is_active
            should_display = camera_active or mic_active

            if should_display:
                # Update icons based on current state
                if camera_active:
                    self.camera_label.config(image=self.camera_active_icon)
                else:
                    self.camera_label.config(image=self.camera_inactive_icon)

                if mic_active:
                    self.mic_label.config(image=self.mic_active_icon)
                else:
                    self.mic_label.config(image=self.mic_inactive_icon)

                # Show the window if it's not already visible
                if not self.visible:
                    self.window.deiconify()
                    self.visible = True
                    self._position_window()  # Reposition when showing
            else:
                # Hide the window if it's currently visible
                if self.visible:
                    self.window.withdraw()
                    self.visible = False

        # Add the update function to the queue
        self.update_queue.put(do_update)

    def close(self):
        """Shut down the OSD"""
        self.running = False

        # Schedule window destruction in tkinter thread
        def do_close():
            if self.window:
                self.window.quit()
                self.window.destroy()

        self.update_queue.put(do_close)


class VCM:
    def __init__(self):
        self.running = True
        self.paused = False

        self.config = Config()

        self.camera = CameraControl(selected_camera_id=self.config.selected_camera_id)
        self.mic = MicrophoneControl()

        self.hotkey_mappings = {}
        self.hotkey_listener = None

        self.action_queue = Queue()

        self.icon = None
        self.osd = OSDDisplay(self)

        self.icon_img = Image.open(resource_path("resources/logo.png"))

        self.version = __version__

    def exit(self, icon, item):
        self.running = False

    def start(self):
        # Start the OSD
        self.osd.start()
        # Wait a moment for the OSD to initialize
        time.sleep(0.5)

        # Start camera and hotkeys
        self._start_hotkeys()
        self.camera.start()

        # Start the icon in a separate thread
        icon_thread = threading.Thread(target=self._setup_tray_icon, daemon=True)
        icon_thread.start()

        # Update OSD with initial state
        self.osd.update()

        # Main loop processes events from queue
        while self.running:
            self._process_queue()
            time.sleep(0.01)

        print("Cleaning up...")
        self.camera.stop()
        self.hotkey_listener.stop()
        self.osd.close()
        self.icon.stop()

    def pause(self):
        print("Pausing...")
        self.camera.stop()
        self.hotkey_listener.stop()
        self.osd.close()
        self.paused = True

        if self.icon:
            self.icon.menu = pystray.Menu(*self._get_menu_items())

    def unpause(self):
        print("Unpausing...")
        self._start_hotkeys()
        self.camera.start()
        self.osd.start()
        self.paused = False

        if self.icon:
            self.icon.menu = pystray.Menu(*self._get_menu_items())

    def _get_menu_items(self):
        menu = []

        if not self.paused:
            if self.config.enable_camera_function:
                menu.append(
                    pystray.MenuItem(
                        "Camera",
                        self._toggle_camera,
                        checked=lambda _: self.camera.camera_active,
                    ),
                )
            if self.config.enable_mic_function:
                menu.append(
                    pystray.MenuItem(
                        "Microphone",
                        self._toggle_mic,
                        checked=lambda _: self.mic.is_active,
                    ),
                )

        menu.append(
            pystray.MenuItem(
                "Pause",
                self.pause if not self.paused else self.unpause,
                checked=lambda _: self.paused,
            ),
        )

        menu.append(
            pystray.MenuItem("Exit", self.exit),
        )

        return menu

    def _setup_tray_icon(self):
        # Create the icon
        self.icon = pystray.Icon(
            "VCM", self.icon_img, f"Video Conference Mute v{self.version}"
        )
        # Set initial menu
        self.icon.menu = pystray.Menu(*self._get_menu_items())
        # Run the icon
        self.icon.run()

    def _start_hotkeys(self):
        print("Starting hotkeys...")
        if self.config.enable_mic_function:
            self.hotkey_mappings[self.config.mic_toggle_hotkey] = (
                self._enqueue_toggle_mic
            )
        if self.config.enable_camera_function:
            self.hotkey_mappings[self.config.camera_toggle_hotkey] = (
                self._enqueue_toggle_camera
            )
        self.hotkey_listener = keyboard.GlobalHotKeys(self.hotkey_mappings)
        self.hotkey_listener.start()

    def _enqueue_toggle_camera(self):
        # Add action to queue for the main thread
        self.action_queue.put(lambda: self._toggle_camera())

    def _enqueue_toggle_mic(self):
        # Add action to queue for the main thread
        self.action_queue.put(lambda: self._toggle_mic())

    def _toggle_camera(self):
        if self.camera.camera_active:
            print("Camera deactivated")
        else:
            print("Camera activated")

        self.camera.camera_active = not self.camera.camera_active

        self.osd.update()  # Update OSD when camera state changes

        if self.icon:
            self.icon.menu = pystray.Menu(*self._get_menu_items())

    def _toggle_mic(self):
        self.mic.toggle()
        # Update OSD when mic state changes
        self.osd.update()

        if self.icon:
            self.icon.menu = pystray.Menu(*self._get_menu_items())

    def _process_queue(self):
        # Process all pending actions in the queue
        while not self.action_queue.empty():
            action = self.action_queue.get()
            action()


def main():
    vcm = VCM()
    vcm.start()
    sys.exit(0)


if __name__ == "__main__":
    main()
