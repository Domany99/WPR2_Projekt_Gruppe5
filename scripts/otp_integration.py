"""
OpenTripPlanner Integration Module

Provides helpers to call OpenTripPlanner (OTP) API using geocoded coordinates.

Usage:
    from otp_integration import OTPClient, plan_trip

    otp = OTPClient(base_url="http://localhost:8080/otp")
    result = otp.plan(
        from_lat=46.9479, from_lon=7.4478,
        to_lat=46.9469, to_lon=7.4409,
        mode="TRANSIT,WALK"
    )
"""
from typing import Optional, Dict, Any
import requests
import os


class OTPClient:
    """Client for OpenTripPlanner API"""

    def __init__(self, base_url: str = None, router_id: str = "default", timeout: int = 30):
        """
        Initialize OTP client.

        Args:
            base_url: OTP server URL (e.g., "http://localhost:8080/otp")
            router_id: Router ID in OTP (default: "default")
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv('OTP_BASE_URL', 'http://localhost:8080/otp')
        self.router_id = router_id
        self.timeout = timeout

    def plan(
        self,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float,
        mode: str = "TRANSIT,WALK",
        date: Optional[str] = None,
        time: Optional[str] = None,
        arrive_by: bool = False,
        max_walk_distance: int = 1000,
        wheelchair: bool = False,
        num_itineraries: int = 3,
        **extra_params
    ) -> Dict[str, Any]:
        """
        Plan a trip using OpenTripPlanner.

        Args:
            from_lat: Start latitude (from geocoding)
            from_lon: Start longitude (from geocoding)
            to_lat: Destination latitude (from geocoding)
            to_lon: Destination longitude (from geocoding)
            mode: Travel modes (e.g., "TRANSIT,WALK", "BICYCLE", "CAR")
            date: Date in MM-DD-YYYY format (default: today)
            time: Time in HH:MM format (default: now)
            arrive_by: True for arrive-by, False for depart-at
            max_walk_distance: Maximum walking distance in meters
            wheelchair: True for wheelchair-accessible routes only
            num_itineraries: Number of alternative routes to return
            **extra_params: Additional OTP query parameters

        Returns:
            Dict with OTP response including itineraries

        Raises:
            requests.exceptions.RequestException: On network/HTTP errors
        """
        # Build OTP plan endpoint URL
        url = f"{self.base_url}/routers/{self.router_id}/plan"

        # Prepare parameters for OTP API
        params = {
            'fromPlace': f"{from_lat},{from_lon}",
            'toPlace': f"{to_lat},{to_lon}",
            'mode': mode,
            'maxWalkDistance': max_walk_distance,
            'wheelchair': str(wheelchair).lower(),
            'numItineraries': num_itineraries,
            'arriveBy': str(arrive_by).lower(),
        }

        # Add date/time if provided
        if date:
            params['date'] = date
        if time:
            params['time'] = time

        # Merge any extra parameters
        params.update(extra_params)

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"OpenTripPlanner request failed: {str(e)}")

    def plan_public_transport(self, from_lat: float, from_lon: float, to_lat: float, to_lon: float, **kwargs) -> Dict[str, Any]:
        """Shortcut for public transport planning (TRANSIT + WALK)"""
        return self.plan(from_lat, from_lon, to_lat, to_lon, mode="TRANSIT,WALK", **kwargs)

    def plan_bicycle(self, from_lat: float, from_lon: float, to_lat: float, to_lon: float, **kwargs) -> Dict[str, Any]:
        """Shortcut for bicycle routing"""
        return self.plan(from_lat, from_lon, to_lat, to_lon, mode="BICYCLE", **kwargs)

    def plan_walk(self, from_lat: float, from_lon: float, to_lat: float, to_lon: float, **kwargs) -> Dict[str, Any]:
        """Shortcut for walking routing"""
        return self.plan(from_lat, from_lon, to_lat, to_lon, mode="WALK", **kwargs)

    def plan_scooter(self, from_lat: float, from_lon: float, to_lat: float, to_lon: float, **kwargs) -> Dict[str, Any]:
        """Shortcut for e-scooter routing"""
        return self.plan(from_lat, from_lon, to_lat, to_lon, mode="SCOOTER", **kwargs)

    def plan_multimodal(
        self,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float,
        modes: list = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Plan multimodal trip (e.g., scooter + transit + bike).

        Args:
            modes: List of modes, e.g., ["SCOOTER", "TRANSIT", "BICYCLE"]
                   Default: ["WALK", "TRANSIT"]

        Example:
            # E-Scooter to bus stop, then bus, then PubliBike to destination
            otp.plan_multimodal(
                from_lat=46.9479, from_lon=7.4474,
                to_lat=46.9469, to_lon=7.4409,
                modes=["SCOOTER", "TRANSIT", "BICYCLE"]
            )
        """
        if modes is None:
            modes = ["WALK", "TRANSIT"]

        mode_str = ",".join(modes)
        return self.plan(from_lat, from_lon, to_lat, to_lon, mode=mode_str, **kwargs)


def parse_otp_itinerary(itinerary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse an OTP itinerary into a simplified format.

    Args:
        itinerary: Single itinerary from OTP response

    Returns:
        Simplified itinerary dict with key information
    """
    legs = itinerary.get('legs', [])

    return {
        'duration_sec': itinerary.get('duration', 0),
        'duration_min': round(itinerary.get('duration', 0) / 60, 1),
        'start_time': itinerary.get('startTime'),
        'end_time': itinerary.get('endTime'),
        'walk_distance_m': itinerary.get('walkDistance', 0),
        'transfers': itinerary.get('transfers', 0),
        'legs': [
            {
                'mode': leg.get('mode'),
                'from': leg.get('from', {}).get('name'),
                'to': leg.get('to', {}).get('name'),
                'duration_sec': leg.get('duration', 0),
                'distance_m': leg.get('distance', 0),
                'route': leg.get('route'),
                'route_short_name': leg.get('routeShortName'),
                'route_long_name': leg.get('routeLongName'),
            }
            for leg in legs
        ]
    }


def format_itinerary_summary(parsed: Dict[str, Any]) -> str:
    """
    Create a human-readable summary of an itinerary.

    Args:
        parsed: Output from parse_otp_itinerary()

    Returns:
        String summary (e.g., "Walk 5 min → Tram 9 → Bus 10 → Walk 3 min (32 min total)")
    """
    parts = []
    for leg in parsed['legs']:
        mode = leg['mode']
        duration = round(leg['duration_sec'] / 60)

        if mode == 'WALK':
            parts.append(f"Walk {duration} min")
        elif mode in ('BUS', 'TRAM', 'RAIL', 'SUBWAY', 'FERRY'):
            route = leg.get('route_short_name') or leg.get('route')
            if route:
                parts.append(f"{mode.title()} {route}")
            else:
                parts.append(mode.title())
        else:
            parts.append(mode.title())

    summary = ' → '.join(parts)
    total = parsed['duration_min']
    return f"{summary} ({total} min total)"


# Convenience function for quick integration
def plan_trip_from_geocoded(
    geocoded_start: Any,
    geocoded_dest: Any,
    mode: str = "public_transport",
    otp_client: Optional[OTPClient] = None
) -> Dict[str, Any]:
    """
    Plan a trip using geocoded addresses.

    Args:
        geocoded_start: GeocodeResult object with .lat and .lon
        geocoded_dest: GeocodeResult object with .lat and .lon
        mode: "public_transport", "bicycle", "walk", "scooter", or custom mode string
        otp_client: OTPClient instance (creates default if None)

    Returns:
        Dict with OTP response
    """
    if otp_client is None:
        otp_client = OTPClient()

    if mode == "public_transport":
        return otp_client.plan_public_transport(
            geocoded_start.lat, geocoded_start.lon,
            geocoded_dest.lat, geocoded_dest.lon
        )
    elif mode == "bicycle":
        return otp_client.plan_bicycle(
            geocoded_start.lat, geocoded_start.lon,
            geocoded_dest.lat, geocoded_dest.lon
        )
    elif mode == "walk":
        return otp_client.plan_walk(
            geocoded_start.lat, geocoded_start.lon,
            geocoded_dest.lat, geocoded_dest.lon
        )
    elif mode == "scooter":
        return otp_client.plan_scooter(
            geocoded_start.lat, geocoded_start.lon,
            geocoded_dest.lat, geocoded_dest.lon
        )
    else:
        # Generic call with custom mode string
        return otp_client.plan(
            geocoded_start.lat, geocoded_start.lon,
            geocoded_dest.lat, geocoded_dest.lon,
            mode=mode
        )


def plan_multimodal_trip(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    use_scooter: bool = False,
    use_bike: bool = False,
    use_transit: bool = True,
    otp_client: Optional[OTPClient] = None
) -> Dict[str, Any]:
    """
    Plan a multimodal trip with flexible mode selection.

    Args:
        from_lat, from_lon: Start coordinates
        to_lat, to_lon: Destination coordinates
        use_scooter: Include e-scooter in routing
        use_bike: Include bicycle (PubliBike) in routing
        use_transit: Include public transport
        otp_client: OTPClient instance (creates default if None)

    Returns:
        Dict with OTP response containing multimodal itineraries

    Example:
        # Scooter + Transit + Bike
        result = plan_multimodal_trip(
            from_lat=46.9479, from_lon=7.4474,
            to_lat=46.9469, to_lon=7.4409,
            use_scooter=True,
            use_bike=True,
            use_transit=True
        )
    """
    if otp_client is None:
        otp_client = OTPClient()

    # Build mode list
    modes = ["WALK"]  # Always allow walking

    if use_scooter:
        modes.append("SCOOTER")
    if use_bike:
        modes.append("BICYCLE")
    if use_transit:
        modes.append("TRANSIT")

    return otp_client.plan_multimodal(
        from_lat, from_lon,
        to_lat, to_lon,
        modes=modes
    )


