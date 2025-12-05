"""
Route Segmentation and Transfer Point Analysis

Analyzes routes and suggests alternative transport modes at transfer points.
Example: Bus to Bern Bahnhof → Suggest PubliBike/E-Scooter alternatives for onward journey
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TransferPoint:
    """Represents a point where user changes modes or lines"""
    name: str
    latitude: float
    longitude: float
    arrival_time: Optional[int] = None
    departure_time: Optional[int] = None
    is_station: bool = True
    modes_available: List[str] = None

    def __post_init__(self):
        if self.modes_available is None:
            self.modes_available = []


@dataclass
class RouteSegment:
    """Represents a segment of a route between two transfer points"""
    segment_id: str
    from_point: TransferPoint
    to_point: TransferPoint
    mode: str
    duration_min: float
    distance_m: float
    route_info: Dict[str, Any]  # Line number, route details, etc.
    alternatives_available: bool = False
    alternatives: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []


def extract_transfer_points(otp_itinerary: Dict[str, Any]) -> List[TransferPoint]:
    """
    Extract transfer points from an OTP itinerary.
    Transfer points are where user changes mode/line or major stations.

    Args:
        otp_itinerary: Parsed OTP itinerary with legs

    Returns:
        List of TransferPoint objects
    """
    transfer_points = []
    legs = otp_itinerary.get('legs', [])

    if not legs:
        return transfer_points

    # Add starting point
    first_leg = legs[0]
    from_info = first_leg.get('from', {})
    transfer_points.append(TransferPoint(
        name=from_info.get('name', 'Start'),
        latitude=from_info.get('lat', 0),
        longitude=from_info.get('lon', 0),
        departure_time=first_leg.get('startTime'),
        is_station=first_leg.get('mode') != 'WALK'
    ))

    # Add intermediate transfer points (where mode changes)
    for i, leg in enumerate(legs[:-1]):  # All except last
        to_info = leg.get('to', {})
        next_leg = legs[i + 1]

        # Check if this is a significant transfer point
        is_transfer = (
            leg.get('mode') != next_leg.get('mode') or  # Mode change
            leg.get('route') != next_leg.get('route') or  # Route/line change
            'bahnhof' in to_info.get('name', '').lower() or  # Major station
            'station' in to_info.get('name', '').lower()
        )

        if is_transfer:
            transfer_points.append(TransferPoint(
                name=to_info.get('name', f'Transfer {i+1}'),
                latitude=to_info.get('lat', 0),
                longitude=to_info.get('lon', 0),
                arrival_time=leg.get('endTime'),
                departure_time=next_leg.get('startTime'),
                is_station=True
            ))

    # Add destination
    last_leg = legs[-1]
    to_info = last_leg.get('to', {})
    transfer_points.append(TransferPoint(
        name=to_info.get('name', 'Destination'),
        latitude=to_info.get('lat', 0),
        longitude=to_info.get('lon', 0),
        arrival_time=last_leg.get('endTime'),
        is_station=False
    ))

    return transfer_points


def create_route_segments(
    otp_itinerary: Dict[str, Any],
    transfer_points: List[TransferPoint]
) -> List[RouteSegment]:
    """
    Create route segments between transfer points.

    Args:
        otp_itinerary: Parsed OTP itinerary
        transfer_points: List of identified transfer points

    Returns:
        List of RouteSegment objects
    """
    segments = []
    legs = otp_itinerary.get('legs', [])

    if len(transfer_points) < 2:
        return segments

    # Map transfer points to leg sequences
    current_segment_start = 0
    transfer_idx = 1  # Start from second transfer point

    for leg_idx, leg in enumerate(legs):
        # Check if this leg ends at a transfer point
        to_info = leg.get('to', {})

        if transfer_idx < len(transfer_points):
            tp = transfer_points[transfer_idx]

            # Check if leg ends at this transfer point
            if abs(to_info.get('lat', 0) - tp.latitude) < 0.0001 and \
               abs(to_info.get('lon', 0) - tp.longitude) < 0.0001:

                # Create segment from last transfer point to this one
                segment_legs = legs[current_segment_start:leg_idx + 1]

                # Aggregate segment info
                total_duration = sum(l.get('duration', 0) for l in segment_legs) / 60  # to minutes
                total_distance = sum(l.get('distance', 0) for l in segment_legs)

                # Primary mode (non-WALK mode if exists)
                primary_mode = 'WALK'
                route_info = {}
                for l in segment_legs:
                    if l.get('mode') != 'WALK':
                        primary_mode = l.get('mode', 'TRANSIT')
                        route_info = {
                            'route': l.get('route'),
                            'route_short_name': l.get('routeShortName'),
                            'route_long_name': l.get('routeLongName'),
                            'headsign': l.get('headsign')
                        }
                        break

                segment = RouteSegment(
                    segment_id=f"seg-{len(segments) + 1}",
                    from_point=transfer_points[transfer_idx - 1],
                    to_point=transfer_points[transfer_idx],
                    mode=primary_mode,
                    duration_min=round(total_duration, 1),
                    distance_m=total_distance,
                    route_info=route_info
                )

                segments.append(segment)
                current_segment_start = leg_idx + 1
                transfer_idx += 1

    return segments


def find_alternative_modes_at_transfer(
    transfer_point: TransferPoint,
    destination: TransferPoint,
    publibike_client=None,
    escooter_client=None,
    otp_client=None,
    search_radius_m: int = 300
) -> List[Dict[str, Any]]:
    """
    Find alternative transport modes available at a transfer point.

    Args:
        transfer_point: Current transfer point
        destination: Final destination
        publibike_client: PubliBike API client
        escooter_client: E-Scooter API client
        otp_client: OTP client for routing
        search_radius_m: Search radius in meters

    Returns:
        List of alternative route options
    """
    alternatives = []

    # Check for PubliBikes
    if publibike_client:
        try:
            from publiBike_api import get_nearby_bikes, get_nearby_return_stations

            nearby_bikes = get_nearby_bikes(
                transfer_point.latitude,
                transfer_point.longitude,
                radius_m=search_radius_m,
                client=publibike_client
            )

            nearby_returns = get_nearby_return_stations(
                destination.latitude,
                destination.longitude,
                radius_m=search_radius_m,
                client=publibike_client
            )

            if nearby_bikes and nearby_returns:
                start_station, start_dist = nearby_bikes[0]
                dest_station, dest_dist = nearby_returns[0]

                # Calculate route with OTP if available
                duration_estimate = None
                distance_km = None

                if otp_client:
                    try:
                        from otp_integration import parse_otp_itinerary

                        otp_response = otp_client.plan_bicycle(
                            from_lat=start_station.latitude,
                            from_lon=start_station.longitude,
                            to_lat=dest_station.latitude,
                            to_lon=dest_station.longitude,
                            num_itineraries=1
                        )

                        itineraries = otp_response.get('plan', {}).get('itineraries', [])
                        if itineraries:
                            parsed = parse_otp_itinerary(itineraries[0])
                            bike_time = parsed['duration_min']
                            walk_to = round(start_dist / 80, 1)
                            walk_from = round(dest_dist / 80, 1)
                            duration_estimate = bike_time + walk_to + walk_from
                            distance_km = parsed['walk_distance_m'] / 1000
                    except Exception as e:
                        logger.warning(f"OTP bicycle routing failed: {e}")

                alternatives.append({
                    'mode': 'publibike',
                    'type': 'bike_share',
                    'summary': f"PubliBike from {start_station.name} ({int(start_dist)}m)",
                    'start_station': {
                        'name': start_station.name,
                        'distance_m': int(start_dist),
                        'bikes_available': start_station.available_bikes_count(),
                        'ebikes_available': start_station.available_ebikes_count(),
                        'latitude': start_station.latitude,
                        'longitude': start_station.longitude
                    },
                    'dest_station': {
                        'name': dest_station.name,
                        'distance_m': int(dest_dist),
                        'latitude': dest_station.latitude,
                        'longitude': dest_station.longitude
                    },
                    'duration_min': duration_estimate,
                    'distance_km': distance_km,
                    'est_cost_chf': 4.0
                })

        except Exception as e:
            logger.warning(f"PubliBike lookup failed: {e}")

    # Check for E-Scooters
    if escooter_client:
        try:
            from e_scooter_api import get_nearby_scooters

            nearby_scooters = get_nearby_scooters(
                transfer_point.latitude,
                transfer_point.longitude,
                radius_m=search_radius_m,
                client=escooter_client
            )

            if nearby_scooters:
                scooter, scooter_dist = nearby_scooters[0]

                # Calculate route with OTP if available
                duration_estimate = None
                distance_km = None

                if otp_client:
                    try:
                        from otp_integration import parse_otp_itinerary

                        otp_response = otp_client.plan(
                            from_lat=scooter.latitude,
                            from_lon=scooter.longitude,
                            to_lat=destination.latitude,
                            to_lon=destination.longitude,
                            mode="WALK",
                            max_walk_distance=10000,
                            num_itineraries=1
                        )

                        itineraries = otp_response.get('plan', {}).get('itineraries', [])
                        if itineraries:
                            parsed = parse_otp_itinerary(itineraries[0])
                            scooter_time = max(3, round(parsed['duration_min'] / 3, 1))
                            walk_to = round(scooter_dist / 80, 1)
                            duration_estimate = scooter_time + walk_to
                            distance_km = parsed['walk_distance_m'] / 1000
                            est_cost = round(1.0 + (scooter_time * 0.29), 2)
                        else:
                            # No route found, use estimate
                            duration_estimate = 10
                            distance_km = None
                            est_cost = 5.0
                    except Exception as e:
                        logger.warning(f"OTP scooter routing failed: {e}")
                        duration_estimate = 10
                        distance_km = None
                        est_cost = 5.0
                else:
                    duration_estimate = 10
                    distance_km = None
                    est_cost = 5.0

                battery = scooter.get_battery_percentage()
                battery_pct = battery if battery is not None else 100  # Default to 100% if unknown

                # Create summary based on battery availability
                if battery is not None:
                    summary = f"Voi Scooter ({int(scooter_dist)}m away, {battery_pct:.0f}% battery)"
                else:
                    summary = f"Voi Scooter ({int(scooter_dist)}m away)"

                alternatives.append({
                    'mode': 'e_scooter',
                    'type': 'scooter_share',
                    'summary': summary,
                    'scooter': {
                        'id': scooter.vehicle_id,
                        'distance_m': int(scooter_dist),
                        'battery_percentage': battery_pct,
                        'provider': scooter.provider_name,
                        'latitude': scooter.latitude,
                        'longitude': scooter.longitude
                    },
                    'duration_min': duration_estimate,
                    'distance_km': distance_km,
                    'est_cost_chf': est_cost
                })

        except Exception as e:
            logger.warning(f"E-Scooter lookup failed: {e}")

    return alternatives


def analyze_route_with_alternatives(
    otp_itinerary: Dict[str, Any],
    publibike_client=None,
    escooter_client=None,
    otp_client=None
) -> Dict[str, Any]:
    """
    Analyze a route and find alternative modes at each transfer point.

    Args:
        otp_itinerary: Parsed OTP itinerary
        publibike_client: PubliBike API client
        escooter_client: E-Scooter API client
        otp_client: OTP client

    Returns:
        Dict with segmented route and alternatives at each transfer
    """
    # Extract transfer points
    transfer_points = extract_transfer_points(otp_itinerary)

    # Create route segments
    segments = create_route_segments(otp_itinerary, transfer_points)

    # For each segment, find alternatives
    for i, segment in enumerate(segments):
        # For the FIRST segment: also check alternatives at the START point
        if i == 0:
            # Look for alternatives from the start point to the final destination
            start_point = segment.from_point
            final_dest = transfer_points[-1]  # Last point is final destination

            start_alternatives = find_alternative_modes_at_transfer(
                transfer_point=start_point,
                destination=final_dest,
                publibike_client=publibike_client,
                escooter_client=escooter_client,
                otp_client=otp_client
            )

            if start_alternatives:
                segment.alternatives_available = True
                segment.alternatives = start_alternatives

        # For all segments except the last: check alternatives at the END point (transfer)
        if i < len(segments) - 1:
            # Look for alternatives from this segment's end point (transfer point)
            # to the final destination
            next_transfer = segment.to_point
            final_dest = transfer_points[-1]  # Last point is final destination

            alternatives = find_alternative_modes_at_transfer(
                transfer_point=next_transfer,
                destination=final_dest,
                publibike_client=publibike_client,
                escooter_client=escooter_client,
                otp_client=otp_client
            )

            if alternatives:
                # If we already have start alternatives (first segment), merge them
                if segment.alternatives_available and i == 0:
                    # Combine start and transfer alternatives
                    segment.alternatives.extend(alternatives)
                else:
                    segment.alternatives_available = True
                    segment.alternatives = alternatives

    return {
        'transfer_points': [
            {
                'name': tp.name,
                'latitude': tp.latitude,
                'longitude': tp.longitude,
                'arrival_time': tp.arrival_time,
                'departure_time': tp.departure_time,
                'is_station': tp.is_station
            }
            for tp in transfer_points
        ],
        'segments': [
            {
                'segment_id': seg.segment_id,
                'from': seg.from_point.name,
                'to': seg.to_point.name,
                'mode': seg.mode,
                'duration_min': seg.duration_min,
                'distance_m': seg.distance_m,
                'route_info': seg.route_info,
                'alternatives_available': seg.alternatives_available,
                'alternatives': seg.alternatives
            }
            for seg in segments
        ],
        'total_segments': len(segments),
        'total_transfers': len(transfer_points) - 2  # Exclude start and end
    }

