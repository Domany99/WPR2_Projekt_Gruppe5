"""
PubliBike API Integration

Provides functions to interact with the PubliBike API to fetch station information
and find available bikes near a given location.

API Documentation:
- Station Overview: List all stations with basic info (id, lat, lon, state)
- Station Details: Detailed info including available vehicles

Usage:
    from publiBike_api import PubliBikeClient, find_nearby_stations

    client = PubliBikeClient()
    stations = client.get_stations()
    nearby = find_nearby_stations(start_lat, start_lon, stations, radius_m=300)
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import math
import requests
import os


# PubliBike API Base URL
PUBLIBIKE_API_BASE = os.getenv('PUBLIBIKE_API_BASE', 'https://api.publibike.ch/v1')


@dataclass
class Vehicle:
    """Represents a vehicle available at a station"""
    id: int
    name: str
    type_id: int
    type_name: str
    ebike_battery_level: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Vehicle':
        """Create Vehicle from API response dict"""
        vehicle_type = data.get('type', {})
        return cls(
            id=data.get('id'),
            name=data.get('name'),
            type_id=vehicle_type.get('id'),
            type_name=vehicle_type.get('name', 'Unknown'),
            ebike_battery_level=data.get('ebike_battery_level')
        )

    def is_ebike(self) -> bool:
        """Check if this is an e-bike"""
        return self.ebike_battery_level is not None


@dataclass
class StationState:
    """Represents the state of a station"""
    id: int
    name: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StationState':
        """Create StationState from API response dict"""
        return cls(
            id=data.get('id'),
            name=data.get('name', 'Unknown')
        )

    def is_active(self) -> bool:
        """Check if station is active (typically id=1 means active)"""
        return self.id == 1


@dataclass
class Station:
    """Represents a PubliBike station"""
    id: int
    latitude: float
    longitude: float
    state: StationState
    name: Optional[str] = None
    address: Optional[str] = None
    zip_code: Optional[str] = None
    city: Optional[str] = None
    vehicles: List[Vehicle] = None

    def __post_init__(self):
        if self.vehicles is None:
            self.vehicles = []

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Station':
        """Create Station from API response dict"""
        state_data = data.get('state', {})
        state = StationState.from_dict(state_data)

        vehicles_data = data.get('vehicles', [])
        vehicles = [Vehicle.from_dict(v) for v in vehicles_data]

        return cls(
            id=data.get('id'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            state=state,
            name=data.get('name'),
            address=data.get('address'),
            zip_code=data.get('zip'),
            city=data.get('city'),
            vehicles=vehicles
        )

    def is_active(self) -> bool:
        """Check if station is active"""
        return self.state.is_active()

    def available_bikes_count(self) -> int:
        """Get count of available bikes"""
        return len(self.vehicles)

    def available_ebikes_count(self) -> int:
        """Get count of available e-bikes"""
        return sum(1 for v in self.vehicles if v.is_ebike())

    def has_bikes_available(self) -> bool:
        """Check if any bikes are available"""
        return len(self.vehicles) > 0


class PubliBikeClient:
    """Client for PubliBike API"""

    def __init__(self, api_base: str = None, timeout: int = 10):
        """
        Initialize PubliBike API client.

        Args:
            api_base: Base URL for PubliBike API (default: from env or constant)
            timeout: Request timeout in seconds
        """
        self.api_base = api_base or PUBLIBIKE_API_BASE
        self.timeout = timeout

    def get_stations_overview(self) -> List[Station]:
        """
        Get overview of all stations (without vehicle details).

        Returns:
            List of Station objects with basic info

        Raises:
            requests.exceptions.RequestException: On network/HTTP errors
        """
        url = f"{self.api_base}/public/stations"

        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            stations = []
            for station_data in data:
                station = Station.from_dict(station_data)
                stations.append(station)

            return stations
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch PubliBike stations: {str(e)}")

    def get_station_details(self, station_id: int) -> Station:
        """
        Get detailed information for a specific station including available vehicles.

        Args:
            station_id: Station ID

        Returns:
            Station object with vehicle details

        Raises:
            requests.exceptions.RequestException: On network/HTTP errors
        """
        url = f"{self.api_base}/public/stations/{station_id}"

        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            return Station.from_dict(data)
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch station {station_id} details: {str(e)}")

    def get_all_stations_with_details(self) -> List[Station]:
        """
        Get all stations with detailed vehicle information.

        Note: This makes multiple API calls (one per station), so it may be slow.
        Consider using get_stations_overview() and then fetching details only for nearby stations.

        Returns:
            List of Station objects with vehicle details
        """
        overview = self.get_stations_overview()
        detailed_stations = []

        for station in overview:
            try:
                detailed = self.get_station_details(station.id)
                detailed_stations.append(detailed)
            except Exception as e:
                # Log error but continue with other stations
                print(f"Warning: Failed to fetch details for station {station.id}: {e}")
                detailed_stations.append(station)  # Use overview data

        return detailed_stations


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two coordinates using Haversine formula.

    Args:
        lat1, lon1: First coordinate (latitude, longitude)
        lat2, lon2: Second coordinate (latitude, longitude)

    Returns:
        Distance in meters
    """
    # Earth radius in meters
    R = 6371000

    # Convert to radians
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    # Haversine formula
    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance


def find_nearby_stations(
    lat: float,
    lon: float,
    stations: List[Station],
    radius_m: float = 300,
    only_active: bool = True,
    only_with_bikes: bool = False
) -> List[Tuple[Station, float]]:
    """
    Find stations within a given radius of a coordinate.

    Args:
        lat, lon: Center coordinate (latitude, longitude)
        stations: List of stations to search
        radius_m: Search radius in meters (default: 300)
        only_active: Only include active stations (default: True)
        only_with_bikes: Only include stations with available bikes (default: False)

    Returns:
        List of (Station, distance) tuples, sorted by distance
    """
    nearby = []

    for station in stations:
        # Filter by active state
        if only_active and not station.is_active():
            continue

        # Filter by available bikes
        if only_with_bikes and not station.has_bikes_available():
            continue

        # Calculate distance
        distance = calculate_distance(lat, lon, station.latitude, station.longitude)

        # Check if within radius
        if distance <= radius_m:
            nearby.append((station, distance))

    # Sort by distance (closest first)
    nearby.sort(key=lambda x: x[1])

    return nearby


def get_nearby_bikes(
    lat: float,
    lon: float,
    radius_m: float = 300,
    client: Optional[PubliBikeClient] = None
) -> List[Tuple[Station, float]]:
    """
    Convenience function to get nearby stations with available bikes.

    Args:
        lat, lon: Center coordinate (latitude, longitude)
        radius_m: Search radius in meters (default: 300)
        client: PubliBikeClient instance (creates new if None)

    Returns:
        List of (Station, distance) tuples with bikes available, sorted by distance

    Raises:
        Exception: If API call fails
    """
    if client is None:
        client = PubliBikeClient()

    # Get all stations (overview is faster, details if needed)
    stations = client.get_stations_overview()

    # Find nearby stations
    nearby = find_nearby_stations(
        lat, lon, stations,
        radius_m=radius_m,
        only_active=True,
        only_with_bikes=False  # We'll fetch details separately
    )

    # Fetch details for nearby stations to get vehicle info
    stations_with_bikes = []
    for station, distance in nearby:
        try:
            detailed = client.get_station_details(station.id)
            if detailed.has_bikes_available():
                stations_with_bikes.append((detailed, distance))
        except Exception as e:
            print(f"Warning: Could not fetch details for station {station.id}: {e}")

    return stations_with_bikes


def get_nearby_return_stations(
    lat: float,
    lon: float,
    radius_m: float = 300,
    client: Optional[PubliBikeClient] = None
) -> List[Tuple[Station, float]]:
    """
    Get nearby stations where bikes can be returned (destination).
    Only returns active stations - we don't need to check available docking spots
    since the API doesn't provide this information directly.

    Args:
        lat, lon: Center coordinate (latitude, longitude)
        radius_m: Search radius in meters (default: 300)
        client: PubliBikeClient instance (creates new if None)

    Returns:
        List of (Station, distance) tuples for bike return, sorted by distance

    Raises:
        Exception: If API call fails
    """
    if client is None:
        client = PubliBikeClient()

    # Get all stations
    stations = client.get_stations_overview()

    # Find nearby active stations (no need to check bikes for return)
    nearby = find_nearby_stations(
        lat, lon, stations,
        radius_m=radius_m,
        only_active=True,
        only_with_bikes=False  # For return, we just need active stations
    )

    # Fetch details for nearby stations to get names
    detailed_stations = []
    for station, distance in nearby:
        try:
            detailed = client.get_station_details(station.id)
            detailed_stations.append((detailed, distance))
        except Exception as e:
            # Use overview data if details fail
            print(f"Warning: Could not fetch details for station {station.id}: {e}")
            detailed_stations.append((station, distance))

    return detailed_stations


def format_station_summary(station: Station, distance: float = None) -> str:
    """
    Format a station summary for display.

    Args:
        station: Station object
        distance: Distance in meters (optional)

    Returns:
        Formatted string
    """
    # Use name if available, otherwise show ID
    station_name = station.name if station.name else f"Station #{station.id}"
    parts = [station_name]

    if distance is not None:
        parts.append(f"{int(distance)}m away")

    bike_count = station.available_bikes_count()
    ebike_count = station.available_ebikes_count()

    if bike_count > 0:
        bikes_info = f"{bike_count} bike(s)"
        if ebike_count > 0:
            bikes_info += f" ({ebike_count} e-bike(s))"
        parts.append(bikes_info)
    else:
        parts.append("No bikes available")

    return " · ".join(parts)

