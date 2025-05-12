import subprocess
import cv2
import numpy as np
import base64
import random
import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from lxml import html
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class ADBError(Exception):
    """Custom exception for ADB-related errors."""
    pass

class LDPlayerError(Exception):
    """Custom exception for LDPlayer-related errors."""
    pass

class ADB:
    KEYCODE_0 = 0
    KEYCODE_SOFT_LEFT = 1
    KEYCODE_SOFT_RIGHT = 2
    KEYCODE_HOME = 3
    KEYCODE_BACK = 4
    KEYCODE_CALL = 5
    KEYCODE_ENDCALL = 6
    KEYCODE_0_ = 7
    KEYCODE_1 = 8
    KEYCODE_2 = 9
    KEYCODE_3 = 10
    KEYCODE_4 = 11
    KEYCODE_5 = 12
    KEYCODE_6 = 13
    KEYCODE_7 = 14
    KEYCODE_8 = 0xF
    KEYCODE_9 = 0x10
    KEYCODE_STAR = 17
    KEYCODE_POUND = 18
    KEYCODE_DPAD_UP = 19
    KEYCODE_DPAD_DOWN = 20
    KEYCODE_DPAD_LEFT = 21
    KEYCODE_DPAD_RIGHT = 22
    KEYCODE_DPAD_CENTER = 23
    KEYCODE_VOLUME_UP = 24
    KEYCODE_VOLUME_DOWN = 25
    KEYCODE_POWER = 26
    KEYCODE_CAMERA = 27
    KEYCODE_CLEAR = 28
    KEYCODE_A = 29
    KEYCODE_B = 30
    KEYCODE_C = 0x1F
    KEYCODE_D = 0x20
    KEYCODE_E = 33
    KEYCODE_F = 34
    KEYCODE_G = 35
    KEYCODE_H = 36
    KEYCODE_I = 37
    KEYCODE_J = 38
    KEYCODE_K = 39
    KEYCODE_L = 40
    KEYCODE_M = 41
    KEYCODE_N = 42
    KEYCODE_O = 43
    KEYCODE_P = 44
    KEYCODE_Q = 45
    KEYCODE_R = 46
    KEYCODE_S = 47
    KEYCODE_T = 48
    KEYCODE_U = 49
    KEYCODE_V = 50
    KEYCODE_W = 51
    KEYCODE_X = 52
    KEYCODE_Y = 53
    KEYCODE_Z = 54
    KEYCODE_COMMA = 55
    KEYCODE_PERIOD = 56
    KEYCODE_ALT_LEFT = 57
    KEYCODE_ALT_RIGHT = 58
    KEYCODE_SHIFT_LEFT = 59
    KEYCODE_SHIFT_RIGHT = 60
    KEYCODE_TAB = 61
    KEYCODE_SPACE = 62
    KEYCODE_SYM = 0x3F
    KEYCODE_EXPLORER = 0x40
    KEYCODE_ENVELOPE = 65
    KEYCODE_ENTER = 66
    KEYCODE_DEL = 67
    KEYCODE_GRAVE = 68
    KEYCODE_MINUS = 69
    KEYCODE_EQUALS = 70
    KEYCODE_LEFT_BRACKET = 71
    KEYCODE_RIGHT_BRACKET = 72
    KEYCODE_BACKSLASH = 73
    KEYCODE_SEMICOLON = 74
    KEYCODE_APOSTROPHE = 75
    KEYCODE_SLASH = 76
    KEYCODE_AT = 77
    KEYCODE_NUM = 78
    KEYCODE_HEADSETHOOK = 79
    KEYCODE_FOCUS = 80
    KEYCODE_PLUS = 81
    KEYCODE_MENU = 82
    KEYCODE_NOTIFICATION = 83
    KEYCODE_APP_SWITCH = 187

    def __init__(self):
        self._devices: List[str] = []

    def _run_adb_command(self, command: str, emulator: Optional[str] = None, shell: bool = True) -> str:
        """Run an ADB command and handle errors."""
        cmd = f"adb -s {emulator} {command}" if emulator else f"adb {command}"
        try:
            result = subprocess.run(
                cmd, shell=shell, check=True, capture_output=True, text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"ADB command failed: {cmd}, Error: {e.stderr}")
            raise ADBError(f"ADB command failed: {e.stderr}")
        except Exception as e:
            logger.error(f"Unexpected error running ADB command: {cmd}, Error: {str(e)}")
            raise ADBError(f"Unexpected error: {str(e)}")

    def get_devices(self) -> List[str]:
        """Retrieve a list of connected ADB devices."""
        output = self._run_adb_command("devices", shell=True)
        devices = []
        for line in output.splitlines():
            if "device" in line and "List of devices" not in line:
                device_id = line.split("\t")[0]
                devices.append(device_id)
        self._devices = devices
        return devices

    def open_app(self, emulator: str, package: str) -> None:
        """Open an app on the specified emulator."""
        self._run_adb_command(f"shell monkey -p {package} -c android.intent.category.LAUNCHER 1", emulator)

    def screen_capture(self, emulator: str) -> Path:
        """Capture the screen of the emulator and save it as a PNG file."""
        name = emulator.replace(":", "").replace(".", "")
        remote_path = f"/sdcard/Download/{name}.png"
        local_path = Path(f"{name}.png")
        self._run_adb_command(f"shell screencap {remote_path}", emulator)
        self._run_adb_command(f"pull {remote_path} {local_path}", emulator)
        return local_path

    def find_image(self, emulator: str, target_image_path: Path) -> Tuple[Optional[int], Optional[int]]:
        """Find the target image on the emulator's screen and return its center coordinates."""
        try:
            target_img = cv2.imread(str(target_image_path))
            if target_img is None:
                raise ValueError(f"Failed to load target image: {target_image_path}")
            
            screen_path = self.screen_capture(emulator)
            screen_img = cv2.imread(str(screen_path))
            if screen_img is None:
                raise ValueError(f"Failed to load screen capture: {screen_path}")

            w, h = target_img.shape[1], target_img.shape[0]
            result = cv2.matchTemplate(target_img, screen_img, cv2.TM_CCOEFF_NORMED)
            location = np.where(result >= 0.8)
            data = list(zip(*location[::-1]))

            if data:
                x, y = data[0][0], data[0][1]
                return x + w // 2, y + h // 2
            return None, None
        except Exception as e:
            logger.error(f"Error finding image: {str(e)}")
            return None, None

    def tap_image(self, emulator: str, image_path: Path) -> bool:
        """Tap the center of the target image if found on the screen."""
        x, y = self.find_image(emulator, image_path)
        if x is not None and y is not None:
            self._run_adb_command(f"shell input tap {x} {y}", emulator)
            return True
        return False

    def input_text(self, emulator: str, text: str, vietnamese: bool = False) -> None:
        """Input text to the emulator, supporting Vietnamese via ADBKeyboard."""
        if vietnamese:
            encoded = base64.b64encode(text.encode("utf-8")).decode("utf-8")
            self._run_adb_command("shell ime set com.android.adbkeyboard/.AdbIME", emulator)
            self._run_adb_command(f"shell am broadcast -a ADB_INPUT_B64 --es msg {encoded}", emulator)
        else:
            # Sanitize text to prevent command injection
            sanitized_text = text.replace("'", "").replace('"', "")
            self._run_adb_command(f"shell input text '{sanitized_text}'", emulator)

class LDPlayer:
    """Class to interact with LDPlayer emulators."""

    def __init__(self, ld_path: str = "C:\\LDPlayer\\LDPlayer9"):
        self.ld_path = Path(ld_path)
        if not self.ld_path.exists():
            raise LDPlayerError(f"LDPlayer path does not exist: {ld_path}")
        self.param: Optional[str] = None
        self.name_or_id: Optional[str] = None

    def info(self, param: str, name_or_id: str) -> None:
        """Set the emulator parameter and name/ID."""
        self.param = param
        self.name_or_id = name_or_id

    def _run_ld_command(self, command: str) -> str:
        """Run an LDPlayer command and handle errors."""
        try:
            result = subprocess.run(
                f"ldconsole {command}",
                cwd=self.ld_path,
                shell=True,
                check=True,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"LDPlayer command failed: {command}, Error: {e.stderr}")
            raise LDPlayerError(f"LDPlayer command failed: {e.stderr}")
        except Exception as e:
            logger.error(f"Unexpected error running LDPlayer command: {command}, Error: {str(e)}")
            raise LDPlayerError(f"Unexpected error: {str(e)}")

    def get_devices(self) -> List[str]:
        """Retrieve a list of LDPlayer emulator names."""
        output = self._run_ld_command("list")
        return [line for line in output.splitlines() if line]

    def screen_capture(self) -> Path:
        """Capture the screen of the emulator and save it as a PNG file."""
        name = f"screenshot_{self.name_or_id}"
        remote_path = f"/sdcard/Download/{name}.png"
        local_path = Path(name)
        self._run_ld_command(f"adb --{self.param} {self.name_or_id} --command \"shell screencap {remote_path}\"")
        self._run_ld_command(f"adb --{self.param} {self.name_or_id} --command \"pull {remote_path} {local_path}\"")
        return local_path

    def change_info(self) -> str:
        """Change emulator properties with random device info."""
        models = [
            "Samsung_E2100B", "Samsung_B5702", "Samsung_B520", "Asus_PadFone_2",
            "ZTE_Blade_V", "HTC_EndeavorU", "Sony_C5302"
        ]
        model = random.choice(models)
        prefixes = ["8486", "8496", "8497", "8498", "8432", "8433", "8434", "8435", "8436", "8437", "8438", "8439"]
        phone_number = f"+{random.choice(prefixes)}{random.randint(1000000, 9999999)}"
        cmd = (
            f"--cpu 2 --memory 4096 --manufacturer {model.split('_')[0]} "
            f"--model {model} --resolution 360,600,160 --imei auto "
            f"--pnumber \"{phone_number}\" --androidid auto --mac auto --simserial auto --imsi auto"
        )
        self._run_ld_command(f"modify --{self.param} {self.name_or_id} {cmd}")
        
        # Generate random name
        chars = "qwertyuiopasdfghmcnvxbcz"
        new_name = "".join(random.choice(chars) for _ in range(10))
        self._run_ld_command(f"rename --{self.param} {self.name_or_id} --title {new_name}")
        
        return self.get_devices()[int(self.name_or_id)]
