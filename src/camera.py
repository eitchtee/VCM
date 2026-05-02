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
        self._setup_retry_interval = self._config_value(
            "camera_setup_retry_interval", 3.0
        )
        self._last_setup_attempt_time = -self._setup_retry_interval
        self._camera_warmup_timeout = self._config_value("camera_warmup_timeout", 2.0)
        self._camera_warmup_sleep = 0.1
        self._read_failure_count = 0
        self._read_failure_release_threshold = self._config_value(
            "camera_read_failure_threshold", 3
        )
        self._keep_camera_open_when_muted = bool(
            self._config_value("camera_keep_open_when_muted", False)
        )
        self._camera_unavailable_log_interval = 5.0
        self._last_unavailable_log_time = -self._camera_unavailable_log_interval
        self._last_camera_active = self.config.camera_active

    def _config_value(self, key, default):
        getter = getattr(self.config, "get", None)
        if callable(getter):
            return getter(key, getattr(self.config, key, default))
        return getattr(self.config, key, default)

    def _setup_physical_camera(self):
        self.logger.info(
            f"Attempting to open physical camera (ID: {self.cam_id}) "
            f"with target {self.target_width}x{self.target_height}@{self.target_fps}fps."
        )
        last_failure = None

        for backend_name, capture_args in self._camera_backend_attempts():
            vc = None
            try:
                self.logger.debug(
                    f"Opening physical camera with {backend_name} backend."
                )
                vc = cv2.VideoCapture(*capture_args)
            except Exception as e:
                last_failure = f"{backend_name} open exception: {e}"
                self.logger.warning(
                    f"Exception opening physical camera with {backend_name} backend: {e}",
                    exc_info=True,
                )
                continue

            if not self._is_capture_opened(vc, backend_name):
                last_failure = f"{backend_name} backend did not open"
                self.logger.warning(
                    f"Failed to open physical camera with {backend_name} backend."
                )
                self._release_capture(vc, backend_name)
                continue

            self._apply_camera_properties(vc, backend_name)
            self._log_camera_properties(vc, backend_name)

            if not self._wait_for_first_frame(vc, backend_name):
                last_failure = f"{backend_name} backend opened but produced no frame"
                self._release_capture(vc, backend_name)
                continue

            self._read_failure_count = 0
            self._last_unavailable_log_time = -self._camera_unavailable_log_interval
            return vc

        self.logger.error(
            f"Could not open physical video source (ID: {self.cam_id}) with any backend. "
            f"Last failure: {last_failure or 'unknown'}."
        )
        return None

    def _camera_backend_attempts(self):
        return (
            ("DirectShow", (self.cam_id, cv2.CAP_DSHOW)),
            ("default", (self.cam_id,)),
        )

    def _is_capture_opened(self, vc, backend_name):
        try:
            return vc is not None and vc.isOpened()
        except Exception as e:
            self.logger.warning(
                f"Exception checking whether {backend_name} camera backend opened: {e}",
                exc_info=True,
            )
            return False

    def _apply_camera_properties(self, vc, backend_name):
        properties = (
            ("FOURCC", cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG")),
            ("FRAME_WIDTH", cv2.CAP_PROP_FRAME_WIDTH, self.target_width),
            ("FRAME_HEIGHT", cv2.CAP_PROP_FRAME_HEIGHT, self.target_height),
            ("FPS", cv2.CAP_PROP_FPS, self.target_fps),
            ("BUFFERSIZE", cv2.CAP_PROP_BUFFERSIZE, 1),
        )

        for property_name, property_id, value in properties:
            try:
                accepted = vc.set(property_id, value)
            except Exception as e:
                self.logger.warning(
                    f"Could not set camera property {property_name} via "
                    f"{backend_name} backend (camera may still be usable): {e}"
                )
                continue

            if accepted is False:
                self.logger.debug(
                    f"Camera property {property_name} was not accepted by "
                    f"{backend_name} backend."
                )

    def _log_camera_properties(self, vc, backend_name):
        actual_width = int(
            self._get_camera_property(
                vc, cv2.CAP_PROP_FRAME_WIDTH, "FRAME_WIDTH", backend_name
            )
        )
        actual_height = int(
            self._get_camera_property(
                vc, cv2.CAP_PROP_FRAME_HEIGHT, "FRAME_HEIGHT", backend_name
            )
        )
        actual_fps = self._get_camera_property(
            vc, cv2.CAP_PROP_FPS, "FPS", backend_name
        )

        self.logger.info(
            f"Physical camera opened with {backend_name} backend. Actual W: {actual_width}, "
            f"H: {actual_height}, FPS: {actual_fps if actual_fps > 0 else 'N/A'}"
        )

        if actual_width != self.target_width or actual_height != self.target_height:
            self.logger.warning(
                f"Resolution mismatch on {backend_name} backend: Requested "
                f"{self.target_width}x{self.target_height}, got "
                f"{actual_width}x{actual_height}. Frames will be resized."
            )

    def _get_camera_property(self, vc, property_id, property_name, backend_name):
        try:
            value = vc.get(property_id)
            return value if value is not None else 0
        except Exception as e:
            self.logger.warning(
                f"Could not read camera property {property_name} via "
                f"{backend_name} backend: {e}"
            )
            return 0

    def _wait_for_first_frame(self, vc, backend_name):
        started_at = time.perf_counter()
        deadline = started_at + self._camera_warmup_timeout
        attempts = 0
        last_failure = "no read attempted"

        while True:
            attempts += 1
            try:
                ret, frame = vc.read()
                if ret and frame is not None:
                    if attempts > 1:
                        self.logger.info(
                            f"Physical camera produced first frame via {backend_name} "
                            f"backend after {attempts} attempts."
                        )
                    return True
                last_failure = f"read returned ret={ret}, frame={'set' if frame is not None else 'None'}"
            except Exception as e:
                last_failure = f"read exception: {e}"
                self.logger.warning(
                    f"Exception while warming up physical camera via {backend_name} "
                    f"backend: {e}",
                    exc_info=True,
                )

            if time.perf_counter() >= deadline:
                elapsed = time.perf_counter() - started_at
                self.logger.warning(
                    f"Physical camera opened with {backend_name} backend but did not "
                    f"produce a frame after {attempts} attempts over {elapsed:.1f}s. "
                    f"Last result: {last_failure}."
                )
                return False

            time.sleep(self._camera_warmup_sleep)

    def _release_capture(self, vc, backend_name):
        if vc is None:
            return
        try:
            vc.release()
        except Exception as e:
            self.logger.debug(
                f"Error releasing {backend_name} capture candidate: {e}",
                exc_info=True,
            )

    def _log_camera_unavailable(self):
        now = time.perf_counter()
        if now - self._last_unavailable_log_time < self._camera_unavailable_log_interval:
            return
        retry_in = max(
            0.0,
            self._setup_retry_interval - (now - self._last_setup_attempt_time),
        )
        self.logger.error(
            f"Physical camera not available. Sending black frame. "
            f"Next setup retry in {retry_in:.1f}s."
        )
        self._last_unavailable_log_time = now

    def _read_frame_from_physical_camera(self):
        try:
            ret, frame = self.physical_cam_cv2.read()
        except Exception as e:
            self._read_failure_count += 1
            self.logger.warning(
                f"Exception reading frame from physical camera "
                f"({self._read_failure_count}/{self._read_failure_release_threshold}): {e}",
                exc_info=True,
            )
            return None

        if ret and frame is not None:
            if self._read_failure_count:
                self.logger.info(
                    f"Physical camera recovered after {self._read_failure_count} failed reads."
                )
            self._read_failure_count = 0
            return frame

        self._read_failure_count += 1
        self.logger.warning(
            f"Failed to read frame from physical camera "
            f"({self._read_failure_count}/{self._read_failure_release_threshold}). "
            "Using black frame."
        )
        return None

    def _release_physical_camera(self):
        if self.physical_cam_cv2 is not None:
            self.logger.info("Releasing physical camera.")
            try:
                self.physical_cam_cv2.release()
            except Exception as e:
                self.logger.error(
                    f"Error releasing physical camera: {e}", exc_info=True
                )
            self.physical_cam_cv2 = None
            time.sleep(2)  # Give the OS/DirectShow time to fully free the device

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
                camera_active_now = self.config.camera_active
                if camera_active_now != self._last_camera_active:
                    self.logger.info(
                        f"VCM camera feed state changed: {'enabled' if camera_active_now else 'disabled'}."
                    )
                    if camera_active_now:
                        self._last_setup_attempt_time = -self._setup_retry_interval
                        self._last_unavailable_log_time = (
                            -self._camera_unavailable_log_interval
                        )
                    self._last_camera_active = camera_active_now

                if camera_active_now:  # Check VCM's camera enable state
                    if (
                        not self.physical_cam_cv2
                        or not self._is_capture_opened(
                            self.physical_cam_cv2, "active"
                        )
                    ):
                        if self.physical_cam_cv2 is not None:
                            self._release_physical_camera()
                        now = time.perf_counter()
                        if now - self._last_setup_attempt_time >= self._setup_retry_interval:
                            self._last_setup_attempt_time = now
                            self.physical_cam_cv2 = self._setup_physical_camera()
                        # else: still in cooldown, will send black frame below

                    if self.physical_cam_cv2:
                        frame = self._read_frame_from_physical_camera()
                        if frame is not None:
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
                            frame_to_send = self.black_frame
                            if (
                                self._read_failure_count
                                >= self._read_failure_release_threshold
                            ):
                                self.logger.warning(
                                    "Releasing physical camera after consecutive read failures."
                                )
                                self._release_physical_camera()
                    else:  # Physical camera setup failed
                        self._log_camera_unavailable()
                        frame_to_send = self.black_frame
                else:  # VCM's camera is disabled by user
                    if self.physical_cam_cv2:  # Release physical cam if it was active
                        if self._keep_camera_open_when_muted and self._is_capture_opened(
                            self.physical_cam_cv2, "muted"
                        ):
                            self.logger.debug(
                                "Camera disabled by VCM config. Keeping physical camera open."
                            )
                        else:
                            self.logger.info(
                                "Camera disabled by VCM config. Releasing physical camera."
                            )
                            self._release_physical_camera()
                    self._read_failure_count = 0
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
