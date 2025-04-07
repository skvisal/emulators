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
from appium.options.android import UiAutomator2Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import WebDriverException
from config import CONFIG
from emulator_player import EmulatorPlayer

def arrange_windows(wname, display, cols):
    window_width, window_height = 320, 540

    monitors = get_monitors()
    n_displays = len(monitors)
    
    while display > n_displays:
        display = int(input("Enter the display number: "))
    if n_displays < 2:
        print("Single monitor detected.")
        raise Exception("Secondary monitor not detected.")

    display_monitor = monitors[display - 1]
    monitor_x = display_monitor.x
    monitor_y = display_monitor.y

    emulator_windows = sorted([w for w in gw.getAllWindows() if wname in w.title],key=lambda w: w.title)
    logging.info(emulator_windows)

    for i, window in enumerate(emulator_windows):
        row = i // cols
        col = i % cols

        target_x = monitor_x + col * window_width
        target_y = monitor_y + row * window_height
        window.moveTo(target_x, target_y)
        window.resizeTo(window_width, window_height)
        
def filter_instance(names, title):
    if not isinstance(names, list):
        names = list(names)
    return [instance for instance in names if instance.startswith(title)]    

def kill_node_processes():
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'].lower() == 'node.exe':
                psutil.Process(proc.info['pid']).terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            logging.warning(f"Failed to terminate process {proc.info['pid']}")

def get_username(fn) -> list:
    data_array = []    
    try:
        with open(fn, 'r', encoding='utf-8') as file:
            for line in file:
                if line.strip():                    
                    record = [item.strip() for item in line.strip().split('|')]
                    data_array.append(record)
        return data_array
    
    except FileNotFoundError:
        print(f"Error: File '{fn}' not found.")
        return []
    except PermissionError:
        print(f"Error: Permission denied accessing '{fn}'.")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []
        
def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        
    EP = EmulatorPlayer()
    fb_credentials = []
    read_cred = EP.read_file_to_array(CONFIG["credentials_file"])
    if read_cred:
        for i, record in enumerate(read_cred, 1):
            fb_uid = record[1]
            fb_pwd = record[2]
            fb_code = record[3]
            fb_loc = record[5]
            fb_credentials.append([fb_uid, fb_pwd, fb_code,fb_loc])
            
    else:
        print("No data to add into credintials list.")    
    logging.info(fb_credentials)
    #return
    
    ldinstance = EP.instances()
    logging.info(f"All LDPlayer instances: {ldinstance}")
    if not ldinstance:
        logging.error("No LDPlayer instances found.")
        return False
    else:
        logging.info(f"LDPlayer instances: {ldinstance}")
        
    logging.info(f"Extract TZ: {EP.extract_loc_tz('auto-dfw-001')}")
    
    all_instances = EP.instances()
    logging.info(f"Total instances: {len(all_instances)}")
    is_running = EP.running_emulators()
    target_instances = filter_instance(all_instances, "auto")

    if not is_running:
        logging.info("No emulator is running. Launching filtered instances now!")
        for instance in target_instances:
            print(instance)

        # Launch instances sequentially with 30-second delay and set timezone
        for index, instance in enumerate(target_instances):
            try:
                logging.info(f"Launching instance {index + 1}/{len(target_instances)}: {instance}")
                if EP.launch_instance(instance):
                    logging.info(f"Successfully launched instance {instance}")
                    # Extract timezone from instance name (e.g., 'sea' in 'auto-sea-001')
                    timezone = EP.extract_loc_tz(instance)
                    #find the device udid after successfull launch
                    device_udid = f"emulator-{5554 + 2*index}"
                    logging.info(f"Setting timezone for {device_udid} to {timezone}")
                    # Set timezone via ADB
                    EP.set_timezone(device_udid, timezone)
                else:
                    logging.error(f"Failed to launch instance {instance}")
                # Wait 30 seconds before next launch
                if index < len(target_instances) - 1:  # No need to wait after the last instance
                    logging.info("Waiting 30 seconds before next launch...")
                    time.sleep(30)
            except Exception as e:
                logging.error(f"Error launching instance {instance}: {str(e)}")

        # Refresh running emulators
        is_running = EP.running_emulators()
        if not is_running:
            logging.error("No instances are running after launch attempt")
            return

        # Prepare instances (if additional setup is needed)
        with ThreadPoolExecutor(max_workers=CONFIG["launch_threads"]) as executor:
            futures = [executor.submit(EP.prepare_instance, device) for device in is_running]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"Error during instance preparation: {str(e)}")
    
    #test instance
    
    emulator_title = 'auto'
    arrange_windows(emulator_title, 2, 6)

    # Get instance details and map UDIDs to locations
    instances_with_indices = EP.get_instances_with_indices()
    auto_instances = [(index, name) for index, name in instances_with_indices if name.startswith("auto")]
    name_to_udid = {name: f"emulator-{5554 + 2*index}" for index, name in auto_instances}
    for name, udid in name_to_udid.items():
        logging.info(f"Name: {name}, UDID: {udid}")
    udid_to_location = {
        udid: name.split("-", 2)[1] if "-" in name else "Unknown"
        for name, udid in name_to_udid.items()
    }
    
    ports = [4723 + i for i, _ in enumerate(is_running)]  # Generate ports for running emulators
    
    successful_servers = []
    logging.info(f"Running emulators: {is_running} and assigned ports: {ports}")

    if len(ports) < len(is_running):
        logging.warning("Not enough ports for all running emulators! Some may be skipped.")

    # Check status and start Appium servers
    logging.info("Prepairing Appium server for each emulators ...")

    futures_appium_servers = []
    with ThreadPoolExecutor(max_workers=CONFIG["num_workers"]) as executor:
        for port in ports:
            future = executor.submit(EP.start_appium_servers, port)
            futures_appium_servers.append(future)
    for future_appium_server in futures_appium_servers:
        try:
            if future_appium_server.result():
                successful_servers.append(future_appium_server.result())
        except Exception as e:
            logging.error(f"Error starting Appium server: {str(e)}")
    logging.info(f"Successful Appium servers: {successful_servers}")
    
    for successful_server in successful_servers:
        logging.info(f"Appium server started on port {successful_server}")
        
    input("Press Enter to continue...")
    if not successful_servers:
        logging.error("Appium server failed to start for all devices")
        return        

    successful_drivers = []
    futures = {}
    logging.info("Initializing drivers for each emulators ...")
    with ThreadPoolExecutor(max_workers=CONFIG["num_workers"]) as executor:
        for device_udid, port in zip(is_running, ports):
            future = executor.submit(EP.initialize_driver, device_udid, port)
            futures[future] = (device_udid, port)

    for future in futures:
        device_udid, port = futures[future]
        logging.info(f"In future process of driver: Device UDID: {device_udid}, Port: {port}")
        try:
            driver = future.result()
            if driver:
                successful_drivers.append((driver, device_udid, port))
                logging.info(f"Successfully initialized driver for {device_udid}")
        except Exception as e:
            logging.error(f"Driver init failed for {device_udid}: {str(e)}")
    
    # Dictionary to store results
    results = {}
    lock = threading.Lock()
    
    # Extend successful_drivers with location
    successful_drivers_with_location = [
        (driver, device_udid, port, udid_to_location.get(device_udid, "Unknown"))
        for driver, device_udid, port in successful_drivers
    ]
    logging.info(f"Successful drivers with location: {successful_drivers_with_location}")
    
    def run_activation(app_id, device_udid, driver, port, location, semaphore, credentials=None):
        try:
            with semaphore:
                if app_id == "wireguard":
                    logging.info(f"############Activating############# device_udid: {device_udid}, uid: {credentials[0]}, pwd: {credentials[1]}, code: {credentials[2]}, location: {location}")
                    return
