import random
import subprocess
from typing import List, Dict

CITY_DATA = [
    {
        "city": "Seattle",
        "state_abbr": "WA",
        "base_lat": 47.6062,
        "base_lon": -122.3321,
        "time_zone": "America/Los_Angeles"
    },
    {
        "city": "Bend",
        "state_abbr": "OR",
        "base_lat": 44.0582,
        "base_lon": -121.3153,
        "time_zone": "America/Los_Angeles"
    },
    {
        "city": "San Francisco",
        "state_abbr": "CA",
        "base_lat": 37.7749,
        "base_lon": -122.4194,
        "time_zone": "America/Los_Angeles"
    },
    {
        "city": "San Jose",
        "state_abbr": "CA",
        "base_lat": 37.3382,
        "base_lon": -121.8863,
        "time_zone": "America/Los_Angeles"
    },
    {
        "city": "Salt Lake City",
        "state_abbr": "UT",
        "base_lat": 40.7608,
        "base_lon": -111.8910,
        "time_zone": "America/Denver"
    },
    {
        "city": "Los Angeles",
        "state_abbr": "CA",
        "base_lat": 34.0522,
        "base_lon": -118.2437,
        "time_zone": "America/Los_Angeles"
    },
    {
        "city": "Las Vegas",
        "state_abbr": "NV",
        "base_lat": 36.1699,
        "base_lon": -115.1398,
        "time_zone": "America/Los_Angeles"
    },
    {
        "city": "Denver",
        "state_abbr": "CO",
        "base_lat": 39.7392,
        "base_lon": -104.9903,
        "time_zone": "America/Denver"
    },
    {
        "city": "Phoenix",
        "state_abbr": "AZ",
        "base_lat": 33.4484,
        "base_lon": -112.0740,
        "time_zone": "America/Phoenix"
    },
    {
        "city": "Chicago",
        "state_abbr": "IL",
        "base_lat": 41.8781,
        "base_lon": -87.6298,
        "time_zone": "America/Chicago"
    },
    {
        "city": "Buffalo",
        "state_abbr": "NY",
        "base_lat": 42.8864,
        "base_lon": -78.8784,
        "time_zone": "America/New_York"
    },
    {
        "city": "Detroit",
        "state_abbr": "MI",
        "base_lat": 42.3314,
        "base_lon": -83.0458,
        "time_zone": "America/New_York"
    },
    {
        "city": "Boston",
        "state_abbr": "MA",
        "base_lat": 42.3601,
        "base_lon": -71.0589,
        "time_zone": "America/New_York"
    },
    {
        "city": "Kansas City",
        "state_abbr": "MO",
        "base_lat": 39.0997,
        "base_lon": -94.5786,
        "time_zone": "America/Chicago"
    },
    {
        "city": "Latham",
        "state_abbr": "NY",
        "base_lat": 42.7462,
        "base_lon": -73.7593,
        "time_zone": "America/New_York"
    },
    {
        "city": "New York",
        "state_abbr": "NY",
        "base_lat": 40.7128,
        "base_lon": -74.0060,
        "time_zone": "America/New_York"
    },
    {
        "city": "Ashburn",
        "state_abbr": "VA",
        "base_lat": 39.0437,
        "base_lon": -77.4875,
        "time_zone": "America/New_York"
    },
    {
        "city": "Dallas",
        "state_abbr": "TX",
        "base_lat": 32.7767,
        "base_lon": -96.7970,
        "time_zone": "America/Chicago"
    },
    {
        "city": "Charlotte",
        "state_abbr": "NC",
        "base_lat": 35.2271,
        "base_lon": -80.8431,
        "time_zone": "America/New_York"
    },
    {
        "city": "Atlanta",
        "state_abbr": "GA",
        "base_lat": 33.7490,
        "base_lon": -84.3880,
        "time_zone": "America/New_York"
    },
    {
        "city": "Houston",
        "state_abbr": "TX",
        "base_lat": 29.7604,
        "base_lon": -95.3698,
        "time_zone": "America/Chicago"
    },
    {
        "city": "Miami",
        "state_abbr": "FL",
        "base_lat": 25.7617,
        "base_lon": -80.1918,
        "time_zone": "America/New_York"
    }
]

def generate_nearby_coordinates(
    city_name: str, 
    num_points: int = 5, 
    max_offset_deg: float = 0.05
) -> List[Dict[str, float]]:
    """
    Generate randomized GPS coordinates near a specified city
    
    Args:
        city_name: Name of the city to generate coordinates for
        num_points: Number of coordinates to generate (default: 5)
        max_offset_deg: Maximum offset in degrees from base coordinates (default: 0.05)
    
    Returns:
        List of dictionaries containing latitude, longitude, and time zone
    """
    city = next((c for c in CITY_DATA if c["city"].lower() == city_name.lower()), None)
    
    if not city:
        raise ValueError(f"City '{city_name}' not found in dataset")
    
    coordinates = []
    for _ in range(num_points):
        lat = city["base_lat"] + random.uniform(-max_offset_deg, max_offset_deg)
        lon = city["base_lon"] + random.uniform(-max_offset_deg, max_offset_deg)
        coordinates.append({
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "time_zone": city["time_zone"],
            "state": city["state_abbr"]
        })
    
    return coordinates

def print_coordinates(coordinates: List[Dict]):
    """Pretty-print generated coordinates"""
    for idx, coord in enumerate(coordinates, 1):
        print(f"Point {idx}:")
        print(f"  Latitude: {coord['latitude']}")
        print(f"  Longitude: {coord['longitude']}")
        print(f"  Time Zone: {coord['time_zone']}")
        print(f"  State: {coord['state']}\n")
        
#Python Automation Script
def set_emulator_gps(emulator_id, lat, lon):
    commands = [
        f"adb -s {emulator_id} shell settings put secure location_providers_allowed +gps",
        f"adb -s {emulator_id} shell settings put secure mock_location 1",
        f"adb -s {emulator_id} emu geo fix {lon} {lat}"
    ]
    
    for cmd in commands:
        subprocess.run(cmd, shell=True, check=True)

# Usage
set_emulator_gps("emulator-5572", 37.7749, -122.4194)

if __name__ == "__main__":
    # Example usage
    city_name = input("Enter city name: ").strip()
    try:
        results = generate_nearby_coordinates(city_name, num_points=5)
        print(f"\nGenerated coordinates for {city_name}:")
        print_coordinates(results)
    except ValueError as e:
        print(f"Error: {e}")
    
    #
    #First Enable Developer Options (via ADB)
    ## Unlock developer options (even if hidden)
    #adb -s emulator-5572 shell settings put global development_settings_enabled 1
    
    # Enable mock location feature
    #adb -s emulator-5572 shell settings put secure mock_location 1
    
   

    # For Android 10+ (API 29+), also set mock location app
    #adb -s emulator-5572 shell appops set com.android.settings WRITE_SECURE_SETTINGS allow
    #adb -s emulator-5572 shell settings put secure mock_location_app com.lexa.fakegps
    #Verify Settings
    # Check mock location status
    #adb -s emulator-5572 shell settings get secure mock_location
    # Should return "1"

    # Check allowed mock location app
    #adb -s emulator-5572 shell settings get secure mock_location_app
        
    #Reset Location Settings:
    #    adb -s emulator-5572 shell settings delete secure location_providers_allowed
    """
    import subprocess

def enable_mock_locations(device_id):
    commands = [
        f"adb -s {device_id} shell settings put global development_settings_enabled 1",
        f"adb -s {device_id} shell settings put secure mock_location 1",
        f"adb -s {device_id} shell appops set com.android.settings WRITE_SECURE_SETTINGS allow",
        f"adb -s {device_id} shell settings put secure mock_location_app com.example.fakeloc"
    ]
    
    for cmd in commands:
        subprocess.run(cmd, shell=True, check=True)
        print(f"Executed: {cmd}")

# Usage for emulator-5572
enable_mock_locations("emulator-5572")
    
    """