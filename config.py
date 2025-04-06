import os
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


CONFIG = {
    "ldplayer_path": r"D:\\leidian\\LDPlayer9\\ldconsole.exe",    
    "adb_path": r"C:\\Android\\SDK\\platform-tools\\adb.exe",
    "appium_path": r"C:\Users\NDMz\AppData\Roaming\npm\appium.cmd",
    "name_file": r'C:\Users\Admin\Desktop\hovaten.txt',
    "base_data_path": r'C:\Users\Admin\Desktop\data',
    "tesseract_path": r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    "credentials_file": r'cred.data',
    "credentials_json_file": r'credentials.json',
    "appium_base_port": 4724,
    "launch_threads": 1,
    "num_workers": 3,
    "element_timeout": 2,
    "delay_between_launches": 20,
    "webdriver_base_port": 9515,  
    "second_monitor_x_offset": 1920,  
    "instance_width": 320,
    "instance_height": 540,
    "columns": 6,
    "rows": 2,
    #Using ipfo.io with access token
    "vpn_check_url": 'curl ipinfo.io?token=a68d4c55dc04e8',
    "otp_api_url": 'https://your-2fa-service.com/api/otp?secret={}',  # Replace with actual 2FA API
    
    "wg_apk_full": 'com.wireguard.android/.activity.MainActivity',
    "wg_tunnel_name": 'com.wireguard.android/.activity.MainActivity',
    "wg_package": 'com.wireguard.android',
    "wg_package_activity": '.activity.MainActivity',
    "fb_package": 'com.facebook.katana',
    "start_fb": 'com.facebook.katana/.LoginActivity',
    
    # Logging Configuration
    "log_config": {
        "level": logging.INFO,
        "format": "%(asctime)s - %(levelname)s - %(message)s",
        "handlers": [
            logging.FileHandler(os.path.join(BASE_DIR, "app.log")),
            logging.StreamHandler()
        ]
    }
}