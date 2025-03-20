from ctypes import cast, POINTER

from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume


class MicrophoneControl:
    def __init__(self):
        self.is_active = self._get_status()

        if self.is_active:
            self.toggle()

    @property
    def volume_interface(self):
        devices = AudioUtilities.GetMicrophone()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        return volume

    def _get_status(self):
        volume = self.volume_interface
        return False if volume.GetMute() else True

    def toggle(self):
        """Toggle microphone between original volume and mute"""
        try:
            volume = self.volume_interface

            if self.is_active:
                volume.SetMute(1, None)
                self.is_active = False
                print("Microphone muted")
            else:
                # Restore original volume
                volume.SetMute(0, None)
                self.is_active = True
                print(f"Microphone unmuted")
        except Exception as e:
            print(f"Error toggling microphone: {e}")
