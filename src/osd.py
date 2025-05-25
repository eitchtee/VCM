import tkinter as tk
from PIL import Image, ImageTk, ImageDraw
import threading
from queue import Queue
import logging

from utils.resources import resource_path


logger = logging.getLogger(__name__)


class OSDDisplay:
    def __init__(self, config_reader):  # Takes ConfigReader instance
        self.config_reader = config_reader
        self.window = None
        self.visible = False
        self.update_queue = Queue()
        self.running = False  # Controls the _check_for_updates loop

        self.bg_color = "#1E1E1E"  # Dark modern background
        self.icon_size = (16, 16)  # Adjusted for slightly better visibility

        # To hold ImageTk.PhotoImage objects (must keep references)
        self.camera_active_icon = None
        self.camera_inactive_icon = None
        self.mic_active_icon = None
        self.mic_inactive_icon = None
        self.thread = None  # To hold the OSD thread

    def _create_dummy_icon(self, color, text_char):
        """Creates a placeholder icon if actual icons are missing."""
        img = Image.new("RGBA", self.icon_size, color)
        draw = ImageDraw.Draw(img)
        # Simple text centering
        try:
            # Use a basic font if possible, Tkinter default font can be hard to get for PIL
            # For simplicity, we'll just draw text without worrying too much about font specifics here
            text_bbox = draw.textbbox((0, 0), text_char)  # Requires Pillow 9.2.0+
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            position = (
                (self.icon_size[0] - text_width) / 2,
                (self.icon_size[1] - text_height) / 2 - 2,
            )  # Minor adjustment
            draw.text(position, text_char, fill="white")
        except Exception as e:  # Fallback if textbbox fails or font issues
            logger.error(f"Failed to draw text on dummy icon: {e}")
            draw.line([(0, 0), self.icon_size], fill="white", width=2)  # Draw a cross
            draw.line(
                [(self.icon_size[0], 0), (0, self.icon_size[1])], fill="white", width=2
            )
        return ImageTk.PhotoImage(img)

    def _load_icons(self):
        """Load icon images or create fallbacks if files not found"""
        icon_paths = {
            "camera_active": resource_path("resources/icons/camera_active.png"),
            "camera_inactive": resource_path("resources/icons/camera_inactive.png"),
            "mic_active": resource_path("resources/icons/mic_active.png"),
            "mic_inactive": resource_path("resources/icons/mic_inactive.png"),
        }

        try:
            img = Image.open(icon_paths["camera_active"]).resize(
                self.icon_size, Image.Resampling.LANCZOS
            )
            self.camera_active_icon = ImageTk.PhotoImage(img)
        except Exception as e:
            logger.warning(
                f"Failed to load camera_active icon: {e}. Using placeholder."
            )
            self.camera_active_icon = self._create_dummy_icon("green", "C")

        try:
            img = Image.open(icon_paths["camera_inactive"]).resize(
                self.icon_size, Image.Resampling.LANCZOS
            )
            self.camera_inactive_icon = ImageTk.PhotoImage(img)
        except Exception as e:
            logger.warning(
                f"Failed to load camera_inactive icon: {e}. Using placeholder."
            )
            self.camera_inactive_icon = self._create_dummy_icon("red", "C")

        try:
            img = Image.open(icon_paths["mic_active"]).resize(
                self.icon_size, Image.Resampling.LANCZOS
            )
            self.mic_active_icon = ImageTk.PhotoImage(img)
        except Exception as e:
            logger.warning(f"Failed to load mic_active icon: {e}. Using placeholder.")
            self.mic_active_icon = self._create_dummy_icon("green", "M")

        try:
            img = Image.open(icon_paths["mic_inactive"]).resize(
                self.icon_size, Image.Resampling.LANCZOS
            )
            self.mic_inactive_icon = ImageTk.PhotoImage(img)
        except Exception as e:
            logger.warning(f"Failed to load mic_inactive icon: {e}. Using placeholder.")
            self.mic_inactive_icon = self._create_dummy_icon("red", "M")

    def _run_osd_loop(self):
        logger.info("OSD thread started.")
        self.window = tk.Tk()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.85)  # Slightly more opaque

        self._load_icons()

        self.frame = tk.Frame(
            self.window, bg=self.bg_color, padx=10, pady=6
        )  # Adjusted padding
        self.frame.pack()

        self.icons_frame = tk.Frame(self.frame, bg=self.bg_color)
        self.icons_frame.pack()

        self.camera_label = tk.Label(
            self.icons_frame, image=self.camera_inactive_icon, bg=self.bg_color
        )
        self.camera_label.pack(side=tk.LEFT, padx=(0, 4))

        self.separator = tk.Frame(
            self.icons_frame, width=2, height=self.icon_size[1], bg="#4A4A4A"
        )  # Thicker separator
        self.separator.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=1)

        self.mic_label = tk.Label(
            self.icons_frame, image=self.mic_inactive_icon, bg=self.bg_color
        )
        self.mic_label.pack(side=tk.LEFT, padx=(4, 0))

        self.window.withdraw()  # Start hidden
        self.visible = False

        # Initial update to set correct icons and visibility
        self._perform_update_tasks()
        self._position_window()  # Position once after initial content is set

        self.running = True  # Signal that the update loop can run
        self._check_for_updates()  # Start update poller

        logger.info("Starting OSD mainloop.")
        try:
            self.window.mainloop()
        finally:
            logger.info("OSD mainloop finished.")
            self.running = False  # Ensure update loop stops trying to schedule

    def _position_window(self):
        if not self.window:
            return
        self.window.update_idletasks()
        width = self.window.winfo_reqwidth()
        height = self.window.winfo_reqheight()

        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()

        x = screen_width - width - 30  # Padding from edge
        y = screen_height - height - 50  # Padding from edge (and taskbar)
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def _check_for_updates(self):
        if not self.running and self.update_queue.empty():
            # If not running and queue is empty, we are likely shutting down
            logger.debug("OSD update loop: Not running and queue empty, stopping.")
            return

        try:
            while not self.update_queue.empty():
                update_fn = self.update_queue.get_nowait()
                update_fn()
                self.update_queue.task_done()
        except Exception as e:
            logger.error(f"Error processing OSD update queue: {e}", exc_info=True)

        if self.running and self.window:  # Check if window still exists
            self.window.after(100, self._check_for_updates)  # Reschedule

    def _perform_update_tasks(self):
        """This is the actual UI update logic, executed in the Tkinter thread."""
        if (
            not self.window or not self.config_reader
        ):  # Ensure window and config are available
            return

        # Get current states from ConfigReader
        cam_active = self.config_reader.camera_active
        mic_active = self.config_reader.mic_active

        # NEW DISPLAY LOGIC: Show if EITHER camera OR mic is DEACTIVATED
        should_display = not cam_active or not mic_active

        logger.debug(
            f"OSD Update: CamActive={cam_active}, MicActive={mic_active}, ShouldDisplay={should_display}"
        )

        # Update icons
        self.camera_label.config(
            image=self.camera_active_icon if cam_active else self.camera_inactive_icon
        )
        self.mic_label.config(
            image=self.mic_active_icon if mic_active else self.mic_inactive_icon
        )

        if should_display:
            if not self.visible:
                self.window.deiconify()
                self.visible = True
                self._position_window()  # Reposition when showing, ensures it's correct
                logger.debug("OSD shown.")
        else:
            if self.visible:
                self.window.withdraw()
                self.visible = False
                logger.debug("OSD hidden.")

        # Force window to re-evaluate its size if content changed (icons might vary slightly)
        self.window.update_idletasks()

    def update(self):
        """Queues a request to update the OSD display based on current config."""
        if (
            not self.running and not self.window
        ):  # If not fully started or already closing early
            logger.debug("OSD update called but OSD not running or window not ready.")
            return
        self.update_queue.put(self._perform_update_tasks)

    def start(self):
        """Start the OSD in its own thread if not already running."""
        if self.thread and self.thread.is_alive():
            logger.warning("OSD thread already running.")
            return
        self.thread = threading.Thread(
            target=self._run_osd_loop, daemon=True, name="OSDThread"
        )
        self.thread.start()
        logger.info("OSD start method called, thread initiated.")

    def close(self):
        """Signals the OSD to shut down."""
        logger.info("OSD close method called.")
        self.running = False  # Stop _check_for_updates from re-scheduling

        if self.window:
            # Queue the final close actions to be performed on the Tkinter thread
            try:
                self.update_queue.put(self._do_close_tk_resources, block=False)
            except (
                Exception
            ) as e:  # e.g. if queue is full (should not happen with block=False)
                logger.error(f"Error queueing OSD close operation: {e}")
                # Fallback if queueing fails catastrophically
                if self.window:
                    try:
                        self.window.quit()
                        self.window.destroy()
                    except Exception as e_destroy:
                        logger.error(f"Direct destroy failed: {e_destroy}")

        # Wait for the OSD thread to finish
        if self.thread and self.thread.is_alive():
            logger.debug("Waiting for OSD thread to join...")
            self.thread.join(timeout=2.0)  # Wait for up to 2 seconds
            if self.thread.is_alive():
                logger.warning("OSD thread did not terminate in time.")
        logger.info("OSD close finished.")

    def _do_close_tk_resources(self):
        """Helper to quit and destroy Tkinter resources, called from Tkinter thread."""
        if self.window:
            try:
                self.window.quit()  # Stops mainloop
                self.window.destroy()  # Destroys window
                self.window = None
                logger.info("OSD Tkinter resources closed.")
            except Exception as e:
                logger.error(f"Error destroying OSD Tkinter window: {e}", exc_info=True)
