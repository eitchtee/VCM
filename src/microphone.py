import logging
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL, CoInitialize, CoUninitialize, COMError

from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

# It's good practice to ensure COM is initialized in threads that use COM objects. pycaw interacts with COM.


def com_initialize():
    try:
        CoInitialize()
    except OSError:  # Already initialized in this thread with a different mode
        pass


def com_uninitialize():
    CoUninitialize()


# Setup logger for this module
logger = logging.getLogger(__name__)


def _open_volume_interface():
    """
    Retrieves the IAudioEndpointVolume interface for the default microphone.
    COM must already be initialized on the calling thread.
    Returns:
        POINTER(IAudioEndpointVolume) or None: The volume interface, or None on error.
    """
    try:
        devices = (
            AudioUtilities.GetMicrophone()
        )  # Gets the default communications microphone
        if not devices:
            logger.error("No default microphone found by AudioUtilities.")
            return None

        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except COMError as e:
        # Common COM errors include device not found or access issues.
        logger.error(
            f"COMError getting microphone volume interface: {e} (Code: {e.hresult:#010x})"
        )
        if (
            e.hresult == -2147023728
        ):  # AUDCLNT_E_DEVICE_INVALIDATED (e.g. device unplugged)
            logger.error("Microphone device may have been unplugged or become invalid.")
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error getting microphone volume interface: {e}", exc_info=True
        )
        return None


def _with_volume(action, default, description):
    """
    Runs `action(volume_interface)` with COM initialized for the whole call and the
    interface released before COM is torn down again. Returns `default` if the
    interface is unavailable or the action raises.
    """
    com_initialize()
    try:
        volume = _open_volume_interface()
        if volume is None:
            logger.warning(f"Cannot {description}: volume interface is not available.")
            return default
        try:
            return action(volume)
        except Exception as e:
            logger.error(f"Error trying to {description}: {e}", exc_info=True)
            return default
        finally:
            # Drop the interface reference while COM is still initialized.
            del volume
    finally:
        com_uninitialize()


def get_mic_status():
    """
    Checks the current mute status of the default microphone.
    Returns:
        bool: True if the microphone is active (unmuted), False if muted or an error occurred.
    """

    def read(volume):
        current_mute_status = volume.GetMute()  # 0 means unmuted, 1 means muted
        logger.debug(f"Raw microphone mute status from system: {current_mute_status}")
        return not bool(current_mute_status)  # True if 0 (unmuted), False if 1 (muted)

    # Default to muted/inactive when the status cannot be determined.
    return _with_volume(read, False, "read microphone mute status")


def set_mic_mute(mute: bool):
    """
    Sets the mute state of the default microphone.
    Args:
        mute (bool): True to mute the microphone, False to unmute.
    Returns:
        bool: True if the operation was successful, False otherwise.
    """

    def write(volume):
        volume.SetMute(1 if mute else 0, None)
        logger.info(f"Microphone {'muted' if mute else 'unmuted'} successfully.")
        return True

    return _with_volume(write, False, f"{'mute' if mute else 'unmute'} the microphone")
