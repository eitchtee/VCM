import cv2
import numpy as np
import time
import threading
import logging

from softcam import softcam


class CameraManager:
    def __init__(self, config_reader):
        self.logger = logging.getLogger(__name__)
        self.config = config_reader
        self.running = False
        self.thread = None
        self.physical_cam_cv2 = None  # OpenCV VideoCapture instance
        self.virtual_cam_softcam = None  # Softcam instance

        # Desired properties from config
        self.cam_id = self.config.camera_id
        self.target_width = self.config.camera_width
        self.target_height = self.config.camera_height
        self.target_fps = self.config.camera_fps

        self.black_frame = np.zeros(
            (self.target_height, self.target_width, 3), dtype=np.uint8
        )
        self.last_connection_status = False

    def _setup_physical_camera(self):
        self.logger.info(
            f"Attempting to open physical camera (ID: {self.cam_id}) "
            f"with target {self.target_width}x{self.target_height}@{self.target_fps}fps."
        )
        try:
            vc = cv2.VideoCapture(self.cam_id, cv2.CAP_DSHOW)
            if not vc.isOpened():  # Try without CAP_DSHOW if initial open fails
                self.logger.warning(
                    "Failed to open with CAP_DSHOW, trying default backend."
                )
                vc = cv2.VideoCapture(self.cam_id)

            if not vc.isOpened():
                self.logger.error(
                    f"Could not open physical video source (ID: {self.cam_id}) with any backend."
                )
                return None

            # Attempt to set desired properties
            vc.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            vc.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
            vc.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)
            vc.set(cv2.CAP_PROP_FPS, self.target_fps)
            vc.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Small buffer for low latency

            actual_width = int(vc.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(vc.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = vc.get(cv2.CAP_PROP_FPS)  # Can be 0 if not supported

            self.logger.info(
                f"Physical camera opened. Actual W: {actual_width}, H: {actual_height}, FPS: {actual_fps if actual_fps > 0 else 'N/A'}"
            )

            if actual_width != self.target_width or actual_height != self.target_height:
                self.logger.warning(
                    f"Resolution mismatch: Requested {self.target_width}x{self.target_height}, "
                    f"got {actual_width}x{actual_height}. Frames will be resized."
                )
            return vc
        except Exception as e:
            self.logger.error(
                f"Exception setting up physical camera: {e}", exc_info=True
            )
            if vc and vc.isOpened():
                vc.release()
            return None

    def _release_physical_camera(self):
        if self.physical_cam_cv2 and self.physical_cam_cv2.isOpened():
            self.logger.info("Releasing physical camera.")
            try:
                self.physical_cam_cv2.release()
                time.sleep(1)
            except Exception as e:
                self.logger.error(
                    f"Error releasing physical camera: {e}", exc_info=True
                )
        self.physical_cam_cv2 = None

    def _camera_feed_loop(self):
        self.logger.info("Camera feed loop thread started.")

        try:
            self.virtual_cam_softcam = softcam.camera(
                self.target_width,
                self.target_height,
                self.target_fps,
            )
            self.logger.info(
                f"Virtual camera initialized: {self.target_width}x{self.target_height} @ {self.target_fps} FPS"
            )
        except Exception as e:
            self.logger.error(
                f"Fatal: Failed to initialize virtual camera: {e}", exc_info=True
            )
            self.running = False  # Stop if virtual cam fails critically
            return

        target_frame_duration = (
            1.0 / self.target_fps if self.target_fps > 0 else (1.0 / 30.0)
        )  # Default to 30fps if target_fps is 0

        while self.running:
            loop_start_time = time.perf_counter()
            try:
                is_connected_now = self.virtual_cam_softcam.is_connected()

                if is_connected_now != self.last_connection_status:
                    self.logger.info(
                        f"Virtual camera connection status changed: {'Connected' if is_connected_now else 'Disconnected'}"
                    )
                    self.last_connection_status = is_connected_now

                if not is_connected_now:
                    if self.physical_cam_cv2:  # If physical cam was open, release it
                        self.logger.debug(
                            "Virtual cam disconnected. Releasing physical camera."
                        )
                        self._release_physical_camera()

                    # Wait for connection; use a timeout to periodically check self.running
                    # self.logger.debug("Waiting for virtual camera connection...")
                    # softcam's wait_for_connection might be blocking.
                    # We need to ensure self.running is checked.
                    wait_iter_start = time.perf_counter()
                    while self.running and not self.virtual_cam_softcam.is_connected():
                        time.sleep(0.1)  # Poll running flag
                        if (
                            time.perf_counter() - wait_iter_start > 0.5
                        ):  # Call underlying wait every 0.5s
                            self.virtual_cam_softcam.wait_for_connection(timeout=100)
                            wait_iter_start = time.perf_counter()  # reset timer
                    if not self.running:
                        break  # Exit if stop was requested
                    if not self.virtual_cam_softcam.is_connected():
                        continue  # Still not connected, loop again

                # --- Virtual camera IS connected ---
                if self.config.camera_active:  # Check VCM's camera enable state
                    if (
                        not self.physical_cam_cv2
                        or not self.physical_cam_cv2.isOpened()
                    ):
                        self.physical_cam_cv2 = self._setup_physical_camera()

                    if self.physical_cam_cv2:
                        ret, frame = self.physical_cam_cv2.read()
                        if ret and frame is not None:
                            if (
                                frame.shape[0] != self.target_height
                                or frame.shape[1] != self.target_width
                            ):
                                frame = cv2.resize(
                                    frame,
                                    (self.target_width, self.target_height),
                                    interpolation=cv2.INTER_LINEAR,
                                )
                            frame_to_send = cv2.flip(frame, 1)  # Horizontal flip
                        else:
                            self.logger.warning(
                                "Failed to read frame from physical camera. Using black frame."
                            )
                            frame_to_send = self.black_frame
                            self._release_physical_camera()  # Try re-setup next time
                    else:  # Physical camera setup failed
                        self.logger.error(
                            "Physical camera not available. Sending black frame."
                        )
                        frame_to_send = self.black_frame
                else:  # VCM's camera is disabled by user
                    if self.physical_cam_cv2:  # Release physical cam if it was active
                        self.logger.info(
                            "Camera disabled by VCM config. Releasing physical camera."
                        )
                        self._release_physical_camera()
                    frame_to_send = self.black_frame
                    # self.logger.debug("Camera disabled, sending black frame.")

                if frame_to_send is not None:
                    self.virtual_cam_softcam.send_frame(frame_to_send)

            except Exception as e:
                self.logger.error(f"Error in camera feed loop: {e}", exc_info=True)
                if (
                    self.virtual_cam_softcam and self.virtual_cam_softcam.is_connected()
                ):  # Try to send black frame if error
                    try:
                        self.virtual_cam_softcam.send_frame(self.black_frame)
                    except Exception as e_send:
                        self.logger.error(
                            f"Failed to send black frame after error: {e_send}"
                        )
                time.sleep(0.5)  # Pause briefly after an error

            # Frame rate control
            processing_time = time.perf_counter() - loop_start_time
            sleep_time = target_frame_duration - processing_time
            if sleep_time > 0:
                time.sleep(sleep_time)
            # else:
            #     if is_connected_now: # Only log if we are actively trying to send frames
            #         self.logger.warning(f"Frame processing too long: {processing_time:.4f}s, desired: {target_frame_duration:.4f}s")

        # --- Loop finished (self.running is False) ---
        self._release_physical_camera()
        if self.virtual_cam_softcam:
            self.logger.info("Closing virtual camera.")
            try:
                if hasattr(
                    self.virtual_cam_softcam, "close"
                ):  # Check if softcam object has a close method
                    self.virtual_cam_softcam.close()
            except Exception as e:
                self.logger.error(f"Error closing virtual camera: {e}", exc_info=True)
        self.logger.info("Camera feed loop thread finished.")

    def start(self):
        if self.running:
            self.logger.warning("CameraManager start called but already running.")
            return
        self.running = True
        self.thread = threading.Thread(
            target=self._camera_feed_loop, name="CameraFeedThread", daemon=True
        )
        self.thread.start()
        self.logger.info("CameraManager started.")

    def stop(self):
        self.logger.info("CameraManager stop called.")
        self.running = False  # Signal the loop to stop
        if self.thread and self.thread.is_alive():
            self.logger.debug("Waiting for camera feed thread to join...")
            self.thread.join(timeout=3.0)  # Wait for a few seconds
            if self.thread.is_alive():
                self.logger.error("Camera feed thread did not terminate in time!")
        self.logger.info("CameraManager stopped.")
