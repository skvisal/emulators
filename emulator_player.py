import os
import time
import requests
import random
import ctypes
import sys
import subprocess
import psutil
import json
import threading
import pygetwindow as gw
import logging
from typing import Optional
from screeninfo import get_monitors
from ppadb.client import Client as AdbClient
from concurrent.futures import ThreadPoolExecutor, as_completed
from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.by import By
from appium.options.android import UiAutomator2Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import WebDriverException
from config import CONFIG

class EmulatorPlayer:
    def __init__(self):
        self._console = CONFIG["ldplayer_path"]
        self._adb = CONFIG["adb_path"]
        self._appium_path = CONFIG["appium_path"]
        #self._console = "D:\\leidian\\LDPlayer9\\ldconsole.exe"
        #self._adb = "C:\\Android\\SDK\\platform-tools\\adb.exe"
        
        self.driver = None
        self.logger = logging.getLogger(__name__)
        
        logging.info(f"Initializing console {self._console} and adb {self._adb}")
        
    def cleanup(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                self.logger.error(f"Error closing driver: {str(e)}")
        
    def initialize_driver(self, device_udid, port):
        options = UiAutomator2Options()
        options.load_capabilities({
            "platformName": "Android",
            "deviceName": device_udid,
            "appium:udid": device_udid,
            "appium:noReset": True,
            #"appium:automationName": "UiAutomator2",
            #"appium:autoGrantPermissions": True
        })
        max_retries = 3
        retry_delay = 5  # Increased delay for stability
        appium_url = f"http://localhost:{port}/wd/hub"

        for attempt in range(max_retries):
            try:
                self.logger.info(f"Initializing driver for {device_udid} on port {port} (attempt {attempt + 1}/{max_retries})")
                driver = webdriver.Remote(appium_url, options=options)
                driver.implicitly_wait(10)
                # Wait for app to be ready                
                self.logger.info(f"Driver initialized for {device_udid} on port {port}")
                return driver
            except (WebDriverException, TimeoutException) as e:
                self.logger.error(f"Driver init failed for {device_udid}: {str(e)}")
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Failed to initialize driver for {device_udid} after {max_retries} attempts: {str(e)}")
                time.sleep(retry_delay)
            except Exception as e:
                self.logger.error(f"Unexpected error during driver init for {device_udid}: {str(e)}")
                raise
                
    def start_appium_servers(self, port): 
        max_retries = 1
        for attempt in range(max_retries):
            try:
                cmd = [
                    self._appium_path,
                    "-p", str(port),
                    "--base-path", "/wd/hub",
                    "--allow-cors",
                    "--relaxed-security",
                    "--log", f"logs/appium_{port}.log"
                ]
                subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                start_time = time.time()
                while time.time() - start_time < 30:
                    if self.check_appium_status(port):
                        self.logger.info(f"Appium server started on port {port}")
                        return True
                    time.sleep(1)
                self.logger.error(f"Appium server failed to start on port {port} within timeout")
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1}/{max_retries} failed to start Appium on port {port}: {str(e)}")
                if attempt == max_retries - 1:
                    return False
                time.sleep(5)  # Wait before retry
                
    def check_appium_status(self, port):
        try:
            response = requests.get(f"http://127.0.0.1:{port}/wd/hub/status", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return requests.exceptions.RequestException
                
    def is_device_online(self, device_udid):
        """Check if the device is online."""
        try:
            result = subprocess.run(f'{self._adb} devices', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output = result.stdout.decode('utf-8').strip()
            #return device_udid in output and 'device' in output
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Error checking device status for {device_udid}: {e}")
            return False
        
    def restart_adb_if_offline(self, device_udid):
        try:
            result = subprocess.run(f'{self._adb} devices', shell=True, check=True, stdout=subprocess.PIPE)
            output = result.stdout.decode('utf-8').strip().splitlines()
            for line in output[1:]:
                if device_udid in line and 'offline' in line:
                    logging.info(f"Device {device_udid} is offline, restart adb...")
                    subprocess.run(f'adb -s {device_udid} kill-server', shell=True)
                    subprocess.run(f'adb start-server', shell=True)
                    time.sleep(5)
                    return True
            return False
        except subprocess.CalledProcessError as e:
            logging.info(f"Error checking device status: {e}")
            return False
        
    def wait_for_device_online(self, device_udid, max_attempts=3, interval=5):        
        for attempt in range(max_attempts):
            logging.info(f"Attempt {attempt + 1}/{max_attempts}: Checking if device {device_udid} is online...")
            if self.is_device_online(device_udid):
                logging.info(f"Device {device_udid} is online.")
                return True
            else:
                logging.info(f"Device {device_udid} is not online. Retrying in {interval} seconds...")
                time.sleep(interval) # Wait 'interval' seconds before trying again
        logging.error(f"Device {device_udid} is not online after {max_attempts} attempts.")
        return False # After the number of attempts without being online, return False
        
    def running_emulators(self):
        try:
            process = subprocess.Popen([self._adb, 'devices'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, err = process.communicate()
            output = output.decode("utf-8")
            
            if process.returncode != 0:
                raise Exception(f"Error running adb: {err.decode('utf-8')}")
            
            devices = [line.split()[0] for line in output.splitlines() if line and not line.startswith('List of devices')]
            emulators = [device for device in devices if 'emulator' in device]
            
            return emulators
        except Exception as e:
            print(f"Error: {e}")
            return []
    
    def get_instances_with_indices(self):
        """
        Retrieve a list of emulator instances with their indices and names using ldconsole list2.
        Returns:
            list: List of tuples (index, name) for each instance.
        """
        try:
            process = subprocess.Popen(
                [self._console, "list2"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            output, err = process.communicate()
            output = output.decode("utf-8")
            instances = []
            for line in output.splitlines():
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        index = int(parts[0])
                        name = parts[1]
                        instances.append((index, name))
            return instances
        except Exception as e:
            logging.error(f"Error getting instances with indices: {e}")
            return []
    
    def get_all_instances(self) -> list:
        try:
            process = subprocess.Popen(
            [self._console, "list"], 
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
            output, err = process.communicate()
            return [ins.strip() for ins in output.decode("utf-8").split("\r\n") if ins.strip()]
        except OSError as e:
            if e.winerror == 740:
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
                sys.exit()
            raise 
    
    def instances(self) -> list:
        try:
            process = subprocess.Popen(
                [self._console, "list"], 
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            output, err = process.communicate()
            output = output.decode("utf-8")
            return [ins for ins in output.split("\r\n") if ins != '']        
        except Exception as e:
            logging.error(f"Error failed to get instances: {e}")

    def set_timezone(self, device_udid, timezone):
        try:
            #Disable Automatic Date & Time  ->  adb shell settings put global auto_time 0
            #Disable Automatic Time Zone    ->  aadb shell settings put global auto_time_zone 0
            #Check the Locale               ->  adb shell setprop persist.sys.locale en-US
            #set timezone                   ->  adb shell setprop persist.sys.timezone America/Los_Angeles
            cmd_1 = [self._adb, '-s', device_udid, 'shell', 'settings', 'put', 'global', 'auto_time', '0']
            cmd_2 = [self._adb, '-s', device_udid, 'shell', 'settings', 'put', 'global', 'auto_time_zone', '0']
            cmd_3 = [self._adb, '-s', device_udid, 'shell', 'setprop', 'persist.sys.locale', 'en-US']
            cmd_4 = [self._adb, '-s', device_udid, 'shell', 'setprop', 'persist.sys.timezone', timezone]
            result_1 = subprocess.run(cmd_1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            result_2 = subprocess.run(cmd_2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            result_3 = subprocess.run(cmd_3, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            result_4 = subprocess.run(cmd_4, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            if result_1.returncode == 0 and result_2.returncode == 0 and result_3.returncode == 0 and result_4.returncode == 0:
                logging.info(f"Successfully change timezone for device {device_udid}")
                return True
            else:
                logging.error(f"Failed to change timezone for device {device_udid}")
                return False
        except Exception as e:
            logging.error(f"Unexpected error while sending device {device_udid} to home screen: {str(e)}")
            return False
    
    def go_home(self, device_udid):
        try:
            cmd = [self._adb, '-s', device_udid, 'shell', 'input', 'keyevent', 'KEYCODE_HOME']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

            # Logging outputs
            output = result.stdout.decode('utf-8').strip()
            error_output = result.stderr.decode('utf-8').strip()

            if result.returncode == 0:
                logging.info(f"Successfully sent device {device_udid} to the home screen.")
                return True
            else:
                logging.error(f"Failed to send device {device_udid} to home screen. Error: {error_output}")
                return False
        except Exception as e:
            logging.error(f"Unexpected error while sending device {device_udid} to home screen: {str(e)}")
            return False

    def get_otp(self, secret: str) -> Optional[str]:    
        url = f'https://2fa.fb.tools/api/otp/{secret}'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Will raise an HTTPError for bad responses (4xx and 5xx)
            response = response.json()
            
            #print("Complete JSON Data:")
            print(f"This is the response:", response)
            #output = response.get('data', {})
            logging.info("TEST")
            if response.get('ok'):
                print("OK Status:", response['ok'])
                if response.get('data', {}).get("timeRemaining", 0) < 5:                
                    print("Time Remaining:", response['data'].get('timeRemaining'))
                    time.sleep(5)
                    return self.get_otp(secret)  # Recursive retry
                else:
                    print("OTP Code:", response['data'].get('otp'))
                    return response['data'].get('otp')
            else:
                print("Error:", response['error'])
                return None
        except requests.RequestException as e:
            print(f"An error occurred: {e}")
        
    def get_location(self, device_id):
        try:
            cmd = [self._adb, '-s', device_id, 'shell', 'curl', 'https://api.ip2location.io/?key=0E80FACDC37F59287AA892E7195294D1']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

            output = result.stdout.decode('utf-8').strip()  # Extract stdout and decode
            error_output = result.stderr.decode('utf-8').strip()  # Extract stderr

            if not output:
                print(f"Error: No output received from device {device_id}. Stderr: {error_output}")
                return None

            # Parse JSON
            response = json.loads(output)
            location_data = {
                "country": response.get("country_name"),
                "countryCode": response.get("country_code"),
                "region": response.get("region_name"),
                "city": response.get("city_name"),
                "zip": response.get("zip_code"),
                "lat": response.get("latitude"),
                "lon": response.get("longitude"),
                "timezone": response.get("time_zone"),
                "isp": response.get("as"),
                "org": response.get("org"),
                "as": response.get("asn"),
                "ip": response.get("ip")
            }
            return json.dumps(location_data)
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing JSON response: {e}. Raw output: {output}")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
        
        return None

    def read_file_to_array(self, filename):
        # Initialize an empty array to store all records
        data_array = []

        try:
            # Open and read the file
            with open(filename, 'r', encoding='utf-8') as file:
                # Read all lines
                for line in file:
                    # Skip empty lines
                    if line.strip():
                        # Split line by '|' and remove whitespace
                        record = [item.strip() for item in line.strip().split('|')]
                        # Add the parsed record to the array
                        data_array.append(record)

            # Return the populated array
            return data_array

        except FileNotFoundError:
            print(f"Error: File '{filename}' not found.")
            return []
        except PermissionError:
            print(f"Error: Permission denied accessing '{filename}'.")
            return []
        except Exception as e:
            print(f"An error occurred: {e}")
            return []

    def ldplayer_instance(self):
        command = [self._console, "list"] # List all instances of LDPlayer
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info(f"LDPlayer instances: {result.stdout.decode('gbk').strip()}")        
        instances = result.stdout.decode('gbk').strip().split("\r\n")
        return instances

    def launch_instance_old(self, instance) -> bool:
        #Launch an LDPlayer instance
        command = [self._console, "launch"]
        if str(instance).isnumeric():
            command.extend(["--index", str(instance)])
        else:
            command.extend(["--name", instance])            
        try:
            process = subprocess.Popen(
                command, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            _, stderr = process.communicate()
            if process.returncode != 0:
                self.logger.error(f"Failed to launch {instance}: {stderr.decode().strip()}")
                return False
            time.sleep(15)
            logging.info(f"Launched instance {instance} and wait 10 seconds for it to boot")
            return True
        except Exception as e:
            self.logger.error(f"Error launching {instance}: {str(e)}")
            return False
        
    def launch_instance(self, instance) -> tuple[bool, str, str]:
        """
        Launch an LDPlayer instance and return (success, adb_device_name, instance_loc).
        
        Args:
            self: The class instance containing _console and logger.
            instance: Numeric index or name string of the instance to launch.
        
        Returns:
            tuple[bool, str, str]: (True, adb_device_name, instance_loc) if successful,
                                   (False, "", "") if failed or no emulator found.
        """
        command = [self._console, "launch"]
        adb_device_name = ""
        instance_loc = ""
    
        # Construct the launch command based on instance type
        if str(instance).isnumeric():
            command.extend(["--index", str(instance)])
        else:
            command.extend(["--name", instance])
            instance_parts = instance.split("-")
            if len(instance_parts) > 1:
                instance_loc = instance_parts[1]  # Extract instance location
    
        try:
            # Launch the instance
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            _, stderr = process.communicate()
            if process.returncode != 0:
                self.logger.error(f"Failed to launch {instance}: {stderr.decode().strip()}")
                return False, "", ""
    
            # Wait for the instance to boot
            time.sleep(15)
            logging.info(f"Launched instance {instance} and waited 15 seconds for it to boot")
    
            # Fetch the ADB device name from the last emulator in the list
            adb_list_cmd = ["adb", "devices"]
            adb_process = subprocess.run(adb_list_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            adb_output = adb_process.stdout.strip().split("\n")
    
            adb_device_name = ""
            for line in adb_output[1:]:  # Skip "List of devices attached"
                if "emulator" in line:
                    adb_device_name = line.split("\t")[0]  # Update to the last emulator
    
            # Check if an emulator was found
            if not adb_device_name:
                self.logger.error("No emulator found after launching instance")
                return False, "", ""
    
            return True, adb_device_name, instance_loc
    
        except Exception as e:
            self.logger.error(f"Error launching {instance}: {str(e)}")
            return False, "", ""
    
    def instance_tz(self, location):
        #set timezone and location for the instance
        with open('loc_us_data.json', 'r') as f:
            data = json.load()
        
        loc = data.get(location)
            
    
    def extract_loc(self, instance):
        #auto-nyc-001
        instance_id = instance.split("-")[2]
        instance_loc = instance.split("-")[1]
        geo_data = {}
        with open('loc_us_data.json', 'r') as f:
            geo_data = json.load(f)
        
    def extract_loc_tz(self, instance: str) -> str:
        """
        Extract timezone from an instance name like 'auto-nyc-001'.
        Instance format: auto-<LOCATION_CODE>-<ID>
        """
        try:
            parts = instance.split("-")
            if len(parts) < 3:
                raise ValueError(f"Invalid instance format: {instance}")

            inst_mod, inst_loc, inst_id = parts
            logging.info(f"Instance: {instance}, Mod: {inst_mod}, Loc: {inst_loc}, ID: {inst_id}")

            # Load location data from JSON file
            with open('loc_us_data.json', 'r', encoding="utf-8") as f:
                geo_data = json.load(f)

            # Find timezone using state code
            for city, details in geo_data.items():
                print(f"{city} ({details['state_code']}): {details['state_full']} [{details['state_abbr']}] - {details['timezone']}")
               # Corrected comparison using state_code
                if inst_loc.lower() == details["state_code"].lower():
                    logging.info(f"Timezone found for {inst_loc}: {details['timezone']}")
                    return details["timezone"]

            raise KeyError(f"No timezone found for location code: {inst_loc}")

        except (json.JSONDecodeError, FileNotFoundError) as e:
            logging.error(f"Error loading JSON data: {str(e)}")
            return "America/New_York"  # Fallback default
        except Exception as e:
            logging.error(f"Error processing {instance}: {str(e)}")
            return "America/New_York"  # Fallback default
            
       
    def prepare_instance(self, device_udid, location) -> bool:
        #set timezone and location for the instance
        try:
            self.set_location(device_udid, location)
            return True
        except Exception as e:
            logging.error(f"Error preparing instance {device_udid}: {str(e)}")
            return False          
            

    def wireguard_activate(self, device_udid, driver):
        """Activate WireGuard with crash recovery."""
        max_retries = 3
        retry_delay = 2
        if not self.is_device_online(device_udid):
            logging.info(f"Device {device_udid} is offline. Restarting ADB...")
            self.restart_adb_if_offline(device_udid)
            timeout = 10        #wait for 60 seconds
            start_time = time.time()
            while not self.is_device_online(device_udid):
                if time.time() - start_time > timeout:
                    logging.error(f"Timeout: Device {device_udid} did not come online.")
                    return False
                time.sleep(CONFIG['element_timeout'])
                logging.info(f"Device {device_udid} is still offline, waiting...")

        for attempt in range(max_retries):
            try:
                logging.info(f"Activating WireGuard on {device_udid} (attempt {attempt + 1}/{max_retries})")

                # Bring WireGuard app to the foreground
                driver.activate_app("com.wireguard.android")

                # Locate the switch element
                switch_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "com.wireguard.android:id/tunnel_switch")),
                    message=f"Switch not found on {device_udid}"
                )
                time.sleep(CONFIG['element_timeout'])

                logging.info(f"Checking WireGuard switch status on {device_udid}")
                is_switch_on = switch_element.get_attribute("checked") == "true"
                logging.info(f"Emulator {device_udid}: WireGuard status is {'ON' if is_switch_on else 'OFF'}")

                if not is_switch_on:
                    logging.info(f"Emulator {device_udid}: Turning WireGuard ON")
                    switch_element.click()
                    time.sleep(CONFIG['element_timeout'])
                    logging.info(f"Emulator {device_udid}: WireGuard successfully turned ON")
                else:
                    logging.info(f"Emulator {device_udid}: WireGuard is already ON")
                
                try: 
                    data = json.loads(self.get_location(device_udid))
                    if not data:
                        logging.error(f"Error: Failed to get location for {device_udid}")
                        return False
                    else:
                        logging.info(f"Location data for {device_udid}: {data['country']}, {data['city']}, {data['ip']}, {data['timezone']}")
                        #logging.info(f"Location data for {device_udid}: {data}")
                except Exception as e: 
                    logging.error(f"Error: Failed to get location for {device_udid}: {str(e)}")
                    return False 
                self.go_home(device_udid)
                time.sleep(5)
                
                return True

            except (WebDriverException, TimeoutException) as e:
                logging.error(f"Error activating WireGuard on {device_udid}: {str(e)}")

                if attempt == max_retries - 1:
                    return False  # Return failure if all retries fail

                # Restart the app in case of failure
                logging.info(f"Restarting WireGuard on {device_udid}")
                driver.activate_app("com.wireguard.android")
                time.sleep(retry_delay)

    def close_facebook_app(self, driver, device_id):
        logging.info("Closing Facebook app...")
        driver.terminate_app("com.facebook.orca") # Close the Facebook app
        time.sleep(5) # Wait a moment to make sure the application is closed
        logging.info(f"Closed Facebook app on {device_id}.")
        
    def clear_facebook_storage(self, device_udid, app_pkg):
        """Clear the Facebook app's memory and cache for a specific device"""
        try:
            # ADB command to force stop the Facebook app
            app_pkg = 'com.facebook.katana'
            force_stop_command = subprocess.run([self._adb, "-s", device_udid, "shell", "am", "force-stop", app_pkg], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            clear_cache_command = subprocess.run([self._adb, "-s", device_udid, "shell", "pm", "clear", app_pkg], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if force_stop_command.returncode == 0:
                logging.info(f"The Facebook app on {device_udid} has been force stopped.")
            else:
                logging.error(f"Error while executing ADB command to force stop app on {device_udid}: {force_stop_command.stderr.decode('utf-8')}")

            if clear_cache_command.returncode == 0:
                logging.info(f"The Facebook app cache on {device_udid} has been cleared.")
            else:
                logging.error(f"Error while executing ADB command to clear cache on {device_udid}: {clear_cache_command.stderr.decode('utf-8')}")               
            time.sleep(5)

        except Exception as e:
            logging.error(f"Error deleting Facebook app storage on {device_udid}: {e}")
        
    # Function to close Facebook app, clear memory and relaunch
    def restart_facebook_process(self, driver, device_udid, instance_index, port):
        """
        Function is not yet test
        need to check all parameters
        """
    
        logging.info("Warning message not found. Close the application and start again.")
        self.close_facebook_app(driver, device_udid) # Close Facebook app
        self.clear_facebook_storage(device_udid) # Clear Facebook storage
        self.launch_facebook(instance_index, port) # Call the function again to restart Facebook from the beginning
    
    def deny_permission_if_present(self, driver):
        try:
            # Look for the 'Decline' button for about 2 seconds
            element = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, "//android.widget.Button[@resource-id='com.android.packageinstaller:id/permission_allow_button']"))
            )
            element.click()
            logging.info("The 'Deny' button was clicked.")
        except TimeoutException:
            logging.error("Element 'Reject' not found. Continue with next steps.")

    # Check function and click enable button
    def handle_permission_message(self, driver):
        try:
            # Wait for contact access request notification
            WebDriverWait(driver, 2).until(
                EC.visibility_of_element_located((By.XPATH, "//android.widget.TextView[@resource-id='com.android.packageinstaller:id/permission_message']"))
            )
            logging.info("A dialog box requesting access to contacts has appeared.")
            self.deny_permission_if_present(driver)
        except TimeoutException:
            logging.error("There is no dialog box requesting access to contacts.")

    def facebook_login(self, device_udid, driver, fb_uid, fb_pwd, fb_secret, location=None):
        logging.info("Starting Facebook login...")
        
        """
        Perform Facebook login and log the VPN location.
        Args:
            device_udid (str): Emulator UDID.
            driver: Appium driver instance.
            fb_uid (str): Facebook username.
            fb_pwd (str): Facebook password.
            fb_secret (str): Facebook 2FA secret.
            location (str, optional): VPN location from window title.
        Returns:
            bool: True if login successful, False otherwise.
        """
        logging.info(f"Starting Facebook login for {device_udid} with VPN location: {location or 'Unknown'}")
        try:
            logging.info(f"Launching Facebook on {device_udid}")
            driver.activate_app("com.facebook.katana")
            logging.info("Launched Facebook app.")
            time.sleep(CONFIG['element_timeout'])  # Optional, but can be used if needed

            # Wait for the Facebook login page to load completely
            wait = WebDriverWait(driver, 30)  # Adjust timeout if necessary

            # Use a specific element or screen indicator that ensures the app is fully launched
            facebook_login_page_xpath = "//android.widget.ImageView[@content-desc='Facebook from Meta']"

            # Wait for the login page to be displayed
            facebook_login_page = wait.until(EC.presence_of_element_located((By.XPATH, facebook_login_page_xpath)))

            # Alternatively, you could wait for other elements that signify Facebook is fully loaded
            # Example: Wait for the login button or any other unique element
            facebook_login_button_xpath = "//android.widget.Button[@content-desc='Log In']"
            wait.until(EC.presence_of_element_located((By.XPATH, facebook_login_button_xpath)))

            logging.info("Facebook has fully launched and is ready for interaction.")

        except Exception as e:
            logging.error(f"Error during Facebook launch: {e}")

        try:
            logging.info(f"Launching Facebook on {device_udid}")
            driver.activate_app("com.facebook.katana")
            logging.info("Launched Facebook app.")
            time.sleep(CONFIG['element_timeout'])
    
            wait = WebDriverWait(driver, 20)
            facebook_login_page_xpath = "//android.widget.ImageView[@content-desc='Facebook from Meta']"
            facebook_login_page = wait.until(EC.presence_of_element_located((By.XPATH, facebook_login_page_xpath)))
            if not facebook_login_page:
                logging.info("Facebook login page not found.")
                return False
            logging.info("Facebook login page found.")
    
            # Enter username
            uuid_xpath = "(//android.widget.FrameLayout[@resource-id='com.facebook.katana:id/(name removed)'])[2]/android.widget.FrameLayout/android.widget.FrameLayout[2]/android.widget.FrameLayout[1]/android.view.ViewGroup/android.view.ViewGroup/android.view.ViewGroup/android.view.ViewGroup/android.view.ViewGroup/android.view.ViewGroup[1]/android.view.ViewGroup/android.view.ViewGroup/android.widget.EditText"
            uuid_input = wait.until(EC.presence_of_element_located((By.XPATH, uuid_xpath)))
            if uuid_input:
                uuid_input.send_keys(fb_uid)
                logging.info("UUID entered successfully.")
                time.sleep(CONFIG['element_timeout'])
            else:
                logging.info("UUID input field not found.")
                return False
    
            # Enter password
            pwd_xpath = "(//android.widget.FrameLayout[@resource-id='com.facebook.katana:id/(name removed)'])[2]/android.widget.FrameLayout/android.widget.FrameLayout[2]/android.widget.FrameLayout[1]/android.view.ViewGroup/android.view.ViewGroup/android.view.ViewGroup/android.view.ViewGroup/android.view.ViewGroup/android.view.ViewGroup[2]/android.view.ViewGroup/android.widget.EditText"
            pwd_input = wait.until(EC.presence_of_element_located((By.XPATH, pwd_xpath)))
            if pwd_input:
                pwd_input.send_keys(fb_pwd)
                logging.info("Password entered successfully.")
                time.sleep(CONFIG['element_timeout'])
            else:
                logging.info("Password input field not found.")
                return False
    
            # Click login button
            login_btn_xpaths = [
                "//android.widget.Button[@content-desc='Log in']/android.view.ViewGroup",
                "//android.widget.Button[@content-desc='Log into my account']/android.view.ViewGroup"
            ]
            wait = WebDriverWait(driver, 10)  # Increased timeout
            login_btn = None
            for xpath in login_btn_xpaths:
                try:
                    login_btn = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                    login_btn.click()
                    logging.info(f"Clicked on Login button: {xpath}")
                    time.sleep(CONFIG['element_timeout'])
                    break
                except TimeoutException:
                    logging.info(f"Login button not found: {xpath}")
            if not login_btn:
                logging.info("No login button found after trying all options.")
                return False
    
            # Handle OTP if required
            try:
                # Wait for OTP input field (timeout of 10 seconds)
                try_another_way_btn_xpath = "//android.widget.Button[@content-desc='Try another way']/android.view.ViewGroup"
                try_another_way_btn_xpath = wait.until(EC.element_to_be_clickable((By.XPATH, try_another_way_btn_xpath)))
                if try_another_way_btn_xpath:
                    try_another_way_btn_xpath.click()
                    logging.info("Clicked Try another way button")
                    time.sleep(CONFIG['element_timeout'])
                else:
                    logging.info("Try another way button not found")
                    return False
                auth_app_btn_xpath = "//android.widget.RadioButton[@content-desc='Authentication app, Get a code from your authentication app.']/android.view.ViewGroup/android.view.ViewGroup/android.widget.ImageView"
                auth_app_btn = wait.until(EC.element_to_be_clickable((By.XPATH, auth_app_btn_xpath)))
                if auth_app_btn:
                    auth_app_btn.click()
                    logging.info("Clicked Authentication app button")
                    time.sleep(CONFIG['element_timeout'])
                else:
                    logging.info("Authentication app button not found")
                    return False
                continue_btn_xpath = "//android.widget.Button[@content-desc='Continue']/android.view.ViewGroup"
                continue_btn = wait.until(EC.element_to_be_clickable((By.XPATH, continue_btn_xpath)))
                if continue_btn:
                    continue_btn.click()
                    logging.info("Clicked Continue button")
                    time.sleep(CONFIG['element_timeout'])
                else:
                    logging.info("Continue button not found")
                    return False
                trust_box_xpath = "//android.widget.Button[@content-desc='Trust this device and skip this step from now on']/android.view.ViewGroup[1]/android.view.ViewGroup/android.widget.ImageView"
                trust_box = wait.until(EC.presence_of_element_located((By.XPATH, trust_box_xpath)))
                try:
                    trust_box = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, trust_box_xpath)))

                    # Ensure the element is visible and interactable
                    if trust_box.is_displayed() and not trust_box.is_selected():
                        trust_box.click()
                        logging.info("Clicked 'Trust this device and skip this step from now on'")
                        time.sleep(CONFIG['element_timeout'])
                except Exception as e:
                    logging.error(f"Error interacting with trust checkbox: {e}")
    
                # Wait for OTP input field
                otp_xpath = "//android.widget.EditText"
                otp_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, otp_xpath)))
                otp = self.get_otp(str(fb_secret).replace(" ", ""))
                otp_input.send_keys(otp)
                logging.info("OTP code entered successfully.")
                time.sleep(CONFIG['element_timeout'])
    
                continue_btn_xpath = "//android.widget.Button[@content-desc='Continue']/android.view.ViewGroup"
                continue_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, continue_btn_xpath)))
                continue_btn.click()
                logging.info("Clicked Continue button after OTP entry.")
                time.sleep(CONFIG['element_timeout'])
            except TimeoutException:
                logging.info("No OTP required or OTP field not found, proceeding.")
    
            # Handle post-login prompts with a max iteration limit
            prompts_handled = False
            max_attempts = 10
            attempt = 0
            while not prompts_handled and attempt < max_attempts:
                attempt += 1
    
                # Save login info prompt
                try:
                    save_login_info_xpath = "//android.view.View[@content-desc='Save your login info?']"
                    save_login_btn_xpath = "//android.widget.Button[@content-desc='Save']/android.view.ViewGroup"
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, save_login_info_xpath)))
                    save_login_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, save_login_btn_xpath)))
                    save_login_btn.click()
                    logging.info("Clicked Save button for login info.")
                    time.sleep(CONFIG['element_timeout'])
                except TimeoutException:
                    logging.info("Save login info prompt not found, proceeding.")
    
                # Access to contacts prompt
                try:
                    acc_contact_xpath = "//android.view.View[@text='Access to contacts']"
                    acc_contact_skip_xpath = "//android.view.View[@text='Skip']"
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, acc_contact_xpath)))
                    acc_contact_skip = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, acc_contact_skip_xpath)))
                    acc_contact_skip.click()
                    logging.info("Clicked Skip button for contact access.")
                    time.sleep(CONFIG['element_timeout'])                    
    
                    confirm_skip_popup_xpath = "//android.widget.TextView[@resource-id='com.facebook.katana:id/(name removed)' and @text=\"Are you sure you don't want to upload your contacts?\"]"
                    confirm_skip_label_xpath = "//android.widget.Button[@resource-id='com.facebook.katana:id/(name removed)' and @text='SKIP']"
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, confirm_skip_popup_xpath)))
                    confirm_skip_label = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, confirm_skip_label_xpath)))
                    confirm_skip_label.click()
                    logging.info("Clicked SKIP for contact upload confirmation.")
                    time.sleep(CONFIG['element_timeout'])
                except TimeoutException:
                    logging.info("Contact upload prompt or confirmation not found, proceeding.")
    
                # Access to location prompt
                try:
                    access_location_xpath = "//android.view.View[@text='Access to location']"
                    access_location_btn_xpath = "//android.view.ViewGroup[@content-desc='Continue']"
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, access_location_xpath)))
                    access_location_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, access_location_btn_xpath)))
                    access_location_btn.click()
                    logging.info("Clicked Continue for location access.")
                    time.sleep(CONFIG['element_timeout'])
    
                    permission_access_location_btn_xpath = "//android.widget.Button[@resource-id='com.android.packageinstaller:id/permission_allow_button']"
                    permission_access_location_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, permission_access_location_btn_xpath)))
                    permission_access_location_btn.click()
                    logging.info("Clicked Allow for location access.")
                    time.sleep(CONFIG['element_timeout'])
                except TimeoutException:
                    logging.info("Location access prompt not found, proceeding.")
    
                # Add Number prompt
                try:
                    add_number_xpath = "//android.view.View[@text='Add Number']"
                    add_number_skip_xpath = "//android.view.View[@text='Skip']"
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, add_number_xpath)))
                    add_number_skip_label = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, add_number_skip_xpath)))
                    add_number_skip_label.click()
                    logging.info("Clicked SKIP for adding number.")
                    time.sleep(CONFIG['element_timeout'])
                except TimeoutException:
                    logging.info("Add number prompt not found, proceeding.")
    
                # Profile picture prompt
                try:
                    add_picture_xpath = "//android.view.View[@text='Profile picture']"
                    add_picture_skip_xpath = "//android.view.View[@text='Skip']"
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, add_picture_xpath)))
                    add_picture_skip_label = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, add_picture_skip_xpath)))
                    add_picture_skip_label.click()
                    logging.info("Clicked SKIP for adding profile picture.")
                    time.sleep(CONFIG['element_timeout'])
                except TimeoutException:
                    logging.info("Add profile picture prompt not found, proceeding.")
    
                # Check for home screen
                try:
                    facebook_home_icon_xpath = "//android.view.View[@content-desc='Home, tab 1 of 5']"
                    facebook_home_icon = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, facebook_home_icon_xpath)))
                    facebook_home_icon.click()
                    logging.info("Clicked Facebook home icon, login complete.")
                    prompts_handled = True
                except TimeoutException:
                    logging.info("Home icon not yet visible, checking for more prompts.")
                    time.sleep(2)
    
            if not prompts_handled:
                logging.info("Failed to reach home screen after maximum attempts.")
                return False
    
            return True
    
        except Exception as e:
            logging.error(f"Error during Facebook login on {device_udid}: {str(e)}")
            return False
