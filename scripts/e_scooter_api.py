"""
E-Scooter API Integration (Voi Technology AB via SharedMobility.ch)

Provides functions to interact with the SharedMobility.ch API to fetch e-scooter information
from Voi Technology AB and find available e-scooters near a given location.

API Documentation:
- Base URL: https://api.sharedmobility.ch/v1/sharedmobility/
- Identify endpoint: Find vehicles near a location with filters

Usage:
    from e_scooter_api import VoiScooterClient, get_nearby_scooters

    client = VoiScooterClient()
    scooters = client.get_scooters_near_location(47.50024, 8.72334, radius_m=500)
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import math
import requests
import os


# SharedMobility.ch API Configuration
SHAREDMOBILITY_BASE_URL = "https://api.sharedmobility.ch/v1/sharedmobility"
SHAREDMOBILITY_IDENTIFY_URL = f"{SHAREDMOBILITY_BASE_URL}/identify"

# Voi Provider Configuration
VOI_PROVIDER_ID = "voiscooters.com"
VOI_PROVIDER_NAME = "Voi Technology AB"


@dataclass
class Scooter:
    """Represents an available e-scooter from Voi"""
    vehicle_id: str
    latitude: float
    longitude: float
    provider_id: str
    provider_name: str
    vehicle_type: str
    battery_level: Optional[float] = None
    is_reserved: bool = False
    is_disabled: bool = False
    distance: Optional[float] = None

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'Scooter':
        """
        Create Scooter from SharedMobility.ch API response.

        Args:
            data: Feature object from API response

        Returns:
            Scooter instance
        """
        attributes = data.get('attributes', {})
        geometry = data.get('geometry', {})

        # Extract coordinates - geometry has x, y format
        lon = geometry.get('x', 0)
        lat = geometry.get('y', 0)

        # Vehicle type can be a list or string
        vehicle_type = attributes.get('vehicle_type', 'E-Scooter')
        if isinstance(vehicle_type, list) and vehicle_type:
            vehicle_type = vehicle_type[0]

        return cls(
            vehicle_id=attributes.get('id', data.get('id', '')),
            latitude=lat,
            longitude=lon,
            provider_id=attributes.get('provider_id', ''),
            provider_name=attributes.get('provider_name', ''),
            vehicle_type=vehicle_type,
            battery_level=attributes.get('battery_level'),
            is_reserved=attributes.get('vehicle_status_reserved', False),
            is_disabled=attributes.get('vehicle_status_disabled', False),
            distance=attributes.get('distance')
        )

    def is_available(self) -> bool:
        """Check if scooter is available for rent"""
        return not self.is_reserved and not self.is_disabled

    def get_battery_percentage(self) -> Optional[float]:
        """Get battery percentage (0-100)"""
        return self.battery_level


class VoiScooterClient:
    """Client for Voi E-Scooter via SharedMobility.ch API"""

    def __init__(self, timeout: int = 10):
        """
        Initialize Voi Scooter API client.

        Args:
            timeout: Request timeout in seconds
        """
        self.base_url = SHAREDMOBILITY_BASE_URL
        self.identify_url = SHAREDMOBILITY_IDENTIFY_URL
        self.timeout = timeout

    def get_scooters_near_location(
        self,
        latitude: float,
        longitude: float,
        radius_m: float = 500,
        offset: int = 0,
        limit: Optional[int] = None
    ) -> List[Scooter]:
        """
        Get Voi e-scooters near a specific location.

        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_m: Search radius in meters (default: 500)
            offset: Pagination offset (default: 0)
            limit: Maximum number of results (optional)

        Returns:
            List of Scooter objects

        Raises:
            Exception: On API errors
        """
        # Build query parameters
        params = {
            'filters': f'ch.bfe.sharedmobility.provider_id={VOI_PROVIDER_ID},ch.bfe.sharedmobility.vehicle_type=E-Scooter',
            'geometry': f'{longitude},{latitude}',
            'tolerance': str(radius_m),
            'offset': str(offset),
            'geometryFormat': 'esrijson'
        }

        try:
            response = requests.get(
                self.identify_url,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            # Parse response - API returns array of features directly
            results = data if isinstance(data, list) else data.get('results', [])
            scooters = []

            for result in results:
                try:
                    scooter = Scooter.from_api_response(result)
                    # Filter by provider to ensure only Voi scooters
                    if scooter.provider_id == VOI_PROVIDER_ID:
                        scooters.append(scooter)

                        # Apply limit if specified
                        if limit and len(scooters) >= limit:
                            break
                except Exception as e:
                    print(f"Warning: Failed to parse scooter data: {e}")
                    continue

            return scooters

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch Voi e-scooters: {str(e)}")

    def get_available_scooters_near_location(
        self,
        latitude: float,
        longitude: float,
        radius_m: float = 500
    ) -> List[Scooter]:
        """
        Get only available (not reserved, not disabled) Voi e-scooters near a location.

        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_m: Search radius in meters (default: 500)

        Returns:
            List of available Scooter objects
        """
        all_scooters = self.get_scooters_near_location(latitude, longitude, radius_m)
        return [s for s in all_scooters if s.is_available()]


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


def find_nearby_scooters(
    lat: float,
    lon: float,
    scooters: List[Scooter],
    radius_m: float = 300,
    only_available: bool = True,
    min_battery_percentage: Optional[float] = None
) -> List[Tuple[Scooter, float]]:
    """
    Find e-scooters within a given radius of a coordinate.
    This function filters already fetched scooters by distance.

    Args:
        lat, lon: Center coordinate (latitude, longitude)
        scooters: List of scooters to filter
        radius_m: Search radius in meters (default: 300)
        only_available: Only include available scooters (default: True)
        min_battery_percentage: Minimum battery percentage (optional)

    Returns:
        List of (Scooter, distance) tuples, sorted by distance
    """
    nearby = []

    for scooter in scooters:
        # Filter by availability
        if only_available and not scooter.is_available():
            continue

        # Filter by battery level
        if min_battery_percentage is not None:
            battery = scooter.get_battery_percentage()
            if battery is None or battery < min_battery_percentage:
                continue

        # Calculate distance
        distance = calculate_distance(lat, lon, scooter.latitude, scooter.longitude)

        # Check if within radius
        if distance <= radius_m:
            nearby.append((scooter, distance))

    # Sort by distance (closest first)
    nearby.sort(key=lambda x: x[1])

    return nearby


def get_nearby_scooters(
    lat: float,
    lon: float,
    radius_m: float = 300,
    client: Optional[VoiScooterClient] = None,
    min_battery_percentage: Optional[float] = None
) -> List[Tuple[Scooter, float]]:
    """
    Convenience function to get nearby available Voi e-scooters.

    Args:
        lat, lon: Center coordinate (latitude, longitude)
        radius_m: Search radius in meters (default: 300)
        client: VoiScooterClient instance (creates new if None)
        min_battery_percentage: Minimum battery percentage (optional)

    Returns:
        List of (Scooter, distance) tuples, sorted by distance

    Example:
        >>> nearby = get_nearby_scooters(47.3769, 8.5417, radius_m=500)
        >>> for scooter, distance in nearby:
        ...     print(f"Scooter {scooter.vehicle_id}: {distance:.0f}m away")
    """
    if client is None:
        client = VoiScooterClient()

    # Fetch scooters using the API (which already filters by radius)
    scooters = client.get_available_scooters_near_location(lat, lon, radius_m=radius_m)

    # Calculate distances and apply additional filters
    result = []
    for scooter in scooters:
        # Filter by battery if specified
        if min_battery_percentage is not None:
            battery = scooter.get_battery_percentage()
            if battery is None or battery < min_battery_percentage:
                continue

        distance = calculate_distance(lat, lon, scooter.latitude, scooter.longitude)
        result.append((scooter, distance))

    # Sort by distance
    result.sort(key=lambda x: x[1])
    return result


def get_scooters_near_start(
    start_lat: float,
    start_lon: float,
    radius_m: float = 300
) -> List[Dict[str, Any]]:
    """
    Get Voi e-scooters near the start address, formatted for frontend.

    Args:
        start_lat: Start address latitude
        start_lon: Start address longitude
        radius_m: Search radius in meters (default: 300)

    Returns:
        List of scooter dictionaries with relevant information
    """
    try:
        nearby_scooters = get_nearby_scooters(start_lat, start_lon, radius_m=radius_m)

        result = []
        for scooter, distance in nearby_scooters:
            battery = scooter.get_battery_percentage()
            result.append({
                'id': scooter.vehicle_id,
                'latitude': scooter.latitude,
                'longitude': scooter.longitude,
                'distance_m': round(distance, 1),
                'battery_percentage': round(battery, 1) if battery else None,
                'is_available': scooter.is_available(),
                'provider_id': scooter.provider_id,
                'provider_name': scooter.provider_name,
                'vehicle_type': scooter.vehicle_type
            })

        return result
    except Exception as e:
        print(f"Error fetching nearby Voi scooters: {e}")
        return []

