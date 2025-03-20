import threading

import cv2
import numpy as np
import pyvirtualcam
from pyvirtualcam import PixelFormat


class CameraControl:
    def __init__(self, selected_camera_id: int = 0):
        self.selected_camera_id = selected_camera_id
        self.running = False
        self.camera_active = False
        self.camera_lock = threading.Lock()

        self.width = 1280
        self.height = 720
        self.fps = 30
        self.black_frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

    def start(self):
        self.camera_active = False
        self.running = True
        camera_thread = threading.Thread(target=self._process)
        camera_thread.start()

    def stop(self):
        self.running = False

    def _setup_camera(self) -> cv2.VideoCapture:
        vc = cv2.VideoCapture(
            self.selected_camera_id, cv2.CAP_DSHOW
        )  # Specify the backend explicitly for faster startup

        vc.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        vc.set(cv2.CAP_PROP_FPS, self.fps)
        vc.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        vc.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        if not vc.isOpened():
            # Fallback to default
            vc = cv2.VideoCapture(self.selected_camera_id)
            if not vc.isOpened():
                raise RuntimeError("Could not open video source")

        return vc

    def _process(self):
        with pyvirtualcam.Camera(
            self.width, self.height, self.fps, fmt=PixelFormat.BGR, print_fps=False
        ) as cam:
            print(f"Virtual camera started: {cam.device}")

            vc = None
            try:
                while self.running:
                    # with self.camera_lock:
                    if self.camera_active:
                        # Activate camera if needed
                        if vc is None:
                            vc = self._setup_camera()
                        # Read frame
                        ret, frame = vc.read()

                        if not ret:
                            print("Error reading from camera")
                            self.camera_active = False
                            if vc is not None:
                                vc.release()
                                vc = None

                            cam.send(self.black_frame)
                        else:
                            frame = cv2.flip(frame, 1)
                            cam.send(frame)
                    else:
                        # Deactivate camera if needed
                        if vc is not None:
                            vc.release()
                            vc = None
                        cam.send(self.black_frame)

                    # Wait until it's time for the next frame
                    cam.sleep_until_next_frame()

            except Exception as e:
                print(f"Error in camera processing: {e}")
