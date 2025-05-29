# microphone.py
import logging
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL, CoInitialize, CoUninitialize, COMError

# It's good practice to ensure COM is initialized in threads that use COM objects.
# pycaw interacts with COM.


def com_initialize():
    try:
        CoInitialize()
    except OSError:  # Already initialized in this thread with a different mode
        pass


def com_uninitialize():
    CoUninitialize()


# Setup logger for this module
logger = logging.getLogger(__name__)


def _get_volume_interface():
    """
    Retrieves the IAudioEndpointVolume interface for the default microphone.
    Manages COM initialization for the call.
    Returns:
        POINTER(IAudioEndpointVolume) or None: The volume interface, or None on error.
    """
    com_initialize()
    volume_interface = None
    try:
        # Import pycaw components here to allow graceful failure if pycaw is missing
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = (
            AudioUtilities.GetMicrophone()
        )  # Gets the default communications microphone
        if not devices:
            logger.error("No default microphone found by AudioUtilities.")
            return None

        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume_interface = cast(interface, POINTER(IAudioEndpointVolume))
        return volume_interface
    except ImportError:
        logger.error(
            "pycaw library not found. Microphone control will not be available."
        )
        return None
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
    finally:  # Uncomment if explicit COM management per call is needed
        if (
            volume_interface is not None
        ):  # Only uninitialize if we potentially succeeded partially
            com_uninitialize()


def get_mic_status():
    """
    Checks the current mute status of the default microphone.
    Returns:
        bool: True if the microphone is active (unmuted), False if muted or an error occurred.
    """
    volume = _get_volume_interface()
    if volume:
        try:
            current_mute_status = volume.GetMute()  # 0 means unmuted, 1 means muted
            logger.debug(
                f"Raw microphone mute status from system: {current_mute_status}"
            )
            return not bool(
                current_mute_status
            )  # True if 0 (unmuted), False if 1 (muted)
        except Exception as e:
            logger.error(f"Error reading microphone mute status: {e}", exc_info=True)
            return False  # Default to muted/inactive on error
    else:
        logger.warning("Could not get microphone status; volume interface unavailable.")
        return False  # Assume muted if interface cannot be retrieved


def set_mic_mute(mute: bool):
    """
    Sets the mute state of the default microphone.
    Args:
        mute (bool): True to mute the microphone, False to unmute.
    Returns:
        bool: True if the operation was successful, False otherwise.
    """
    volume = _get_volume_interface()
    if not volume:
        logger.error(
            f"Cannot {'mute' if mute else 'unmute'} microphone: volume interface is not available."
        )
        return False
    try:
        desired_mute_state = 1 if mute else 0
        volume.SetMute(desired_mute_state, None)
        logger.info(f"Microphone {'muted' if mute else 'unmuted'} successfully.")
        return True
    except Exception as e:
        logger.error(
            f"Error setting microphone mute state to {'mute' if mute else 'unmute'}: {e}",
            exc_info=True,
        )
        return False
