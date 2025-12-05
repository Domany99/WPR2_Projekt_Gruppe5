from flask import Flask, send_from_directory, jsonify, request
import os

# Resolve static folder to the repo root's /static directory
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
STATIC_DIR = os.path.join(REPO_ROOT, 'static')

# Import geocoding helper
try:
    from geocoding_Adress import Geocoder, geocode_pair
except ImportError:
    # Fallback for different import contexts
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from geocoding_Adress import Geocoder, geocode_pair

# Import OTP integration (optional - only used if OTP is available)
try:
    from otp_integration import OTPClient, parse_otp_itinerary, format_itinerary_summary
    OTP_AVAILABLE = True
except ImportError:
    OTP_AVAILABLE = False

# Import PubliBike API
try:
    from publiBike_api import PubliBikeClient, get_nearby_bikes, get_nearby_return_stations, format_station_summary
    PUBLIBIKE_AVAILABLE = True
except ImportError:
    PUBLIBIKE_AVAILABLE = False

# Import E-Scooter API (Voi)
try:
    from e_scooter_api import VoiScooterClient, get_nearby_scooters, get_scooters_near_start
    ESCOOTER_AVAILABLE = True
except ImportError:
    ESCOOTER_AVAILABLE = False

# Import route segmentation for transfer-based routing
try:
    from route_segmentation import analyze_route_with_alternatives
    SEGMENTATION_AVAILABLE = True
except ImportError:
    SEGMENTATION_AVAILABLE = False

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='')

# Helper function to filter out walk-only routes
def is_walk_only_route(parsed_itinerary):
    """
    Check if a route consists only of WALK legs.
    Walk-only routes are not useful for public transport routing.

    Args:
        parsed_itinerary: Parsed itinerary dict with 'legs'

    Returns:
        True if route is walk-only, False otherwise
    """
    if not parsed_itinerary or 'legs' not in parsed_itinerary:
        return True

    legs = parsed_itinerary['legs']
    if not legs:
        return True

    # Check if all legs are WALK
    return all(leg.get('mode') == 'WALK' for leg in legs)

@app.route('/')
def index():
    # Serve top-level index.html from the resolved static directory
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/routes', methods=['POST'])
def api_routes():
    """Route planning endpoint (prototype):
    - Accepts JSON payload with 'from', 'to', and 'modes' (array of selected modes).
    - Geocodes both addresses and returns coordinates along with routes for each mode.
    """
    data = request.get_json(silent=True) or {}
    start = data.get('from')
    dest = data.get('to')
    # Support both 'modes' (array) and 'mode' (single) for backward compatibility
    modes = data.get('modes', [])
    if not modes:
        single_mode = data.get('mode', 'public_transport')
        modes = [single_mode]

    # Validate at least one mode is selected
    if not modes or len(modes) == 0:
        return jsonify({
            'error': 'Please select at least one travel mode.',
            'received': {'from': start, 'to': dest, 'modes': modes}
        }), 400

    if not start or not dest:
        return jsonify({
            'error': 'Both "from" and "to" are required.',
            'received': {'from': start, 'to': dest, 'modes': modes}
        }), 400

    # Initialize geocoder. In production, set a real contact email.
    geocoder = Geocoder(user_agent="WPR2_Project_Group_05/0.1", email=os.getenv('CONTACT_EMAIL'))

    # Geocode start and destination (use small delay internally for rate limiting)
    try:
        g_start, g_dest = geocode_pair(geocoder, start, dest)
    except Exception as e:
        # Handle network errors or other geocoding failures
        return jsonify({
            'error': f"Geocoding service error: {str(e)}",
            'received': {'from': start, 'to': dest, 'modes': modes}
        }), 500

    # If either failed, return a helpful error
    if g_start is None or g_dest is None:
        missing = []
        if g_start is None:
            missing.append('from')
        if g_dest is None:
            missing.append('to')
        return jsonify({
            'error': f"Could not find location for: {', '.join(missing)}. Please check the address.",
            'received': {'from': start, 'to': dest, 'modes': modes}
        }), 422

    # ============================================================================
    # GEOCODED COORDINATES ARE NOW AVAILABLE FOR OPENTRIPPLANNER!
    # ============================================================================
    # Use these coordinates with OTP:
    #   - g_start.lat, g_start.lon  (start coordinates)
    #   - g_dest.lat, g_dest.lon    (destination coordinates)
    #
    # Example OTP integration (uncomment when OTP server is running):
    #
    # if OTP_AVAILABLE and 'public_transport' in modes:
    #     otp_client = OTPClient(base_url=os.getenv('OTP_BASE_URL', 'http://localhost:8080/otp'))
    #     try:
    #         otp_response = otp_client.plan_public_transport(
    #             from_lat=g_start.lat, from_lon=g_start.lon,
    #             to_lat=g_dest.lat, to_lon=g_dest.lon,
    #             num_itineraries=3
    #         )
    #         # Parse OTP itineraries
    #         itineraries = otp_response.get('plan', {}).get('itineraries', [])
    #         routes_pt = [
    #             {
    #                 'id': f'otp-{i}',
    #                 'mode': 'public_transport',
    #                 'summary': format_itinerary_summary(parse_otp_itinerary(itin)),
    #                 'duration_min': round(itin.get('duration', 0) / 60, 1),
    #                 'legs': parse_otp_itinerary(itin)['legs']
    #             }
    #             for i, itin in enumerate(itineraries)
    #         ]
    #     except Exception as e:
    #         routes_pt = [{'error': f'OTP error: {str(e)}', 'mode': 'public_transport'}]

    # Generate routes for each selected mode
    all_routes = []
    publibike_stations = None  # Cache for station data

    for mode in modes:
        if mode == 'public_transport':
            # Use OpenTripPlanner for public transport routing
            if OTP_AVAILABLE:
                try:
                    otp_client = OTPClient(base_url=os.getenv('OTP_BASE_URL', 'http://localhost:8080/otp'))
                    otp_response = otp_client.plan_public_transport(
                        from_lat=g_start.lat, from_lon=g_start.lon,
                        to_lat=g_dest.lat, to_lon=g_dest.lon,
                        num_itineraries=3  # Request multiple, but only show first valid one
                    )
                    # Parse OTP itineraries
                    itineraries = otp_response.get('plan', {}).get('itineraries', [])

                    if itineraries:
                        route_added = False  # Track if we already added a route
                        for i, itin in enumerate(itineraries):
                            if route_added:
                                break  # Only show one public transport route

                            parsed = parse_otp_itinerary(itin)

                            # Filter out routes that only contain WALK legs
                            if is_walk_only_route(parsed):
                                continue

                            route_data = {
                                'id': f'pt-{i+1}',
                                'mode': 'public_transport',
                                'summary': format_itinerary_summary(parsed),
                                'duration_min': parsed['duration_min'],
                                'transfers': parsed['transfers'],
                                'walk_distance_m': parsed['walk_distance_m'],
                                'start_time': parsed['start_time'],
                                'end_time': parsed['end_time'],
                                'legs': parsed['legs']
                            }

                            # Analyze route for transfer points and alternatives
                            if SEGMENTATION_AVAILABLE and (PUBLIBIKE_AVAILABLE or ESCOOTER_AVAILABLE):
                                try:
                                    # Prepare clients ONLY for selected modes
                                    pb_client = None
                                    es_client = None

                                    if 'publibike' in modes and PUBLIBIKE_AVAILABLE:
                                        pb_client = PubliBikeClient()

                                    if 'e_scooter' in modes and ESCOOTER_AVAILABLE:
                                        es_client = VoiScooterClient()

                                    # Analyze with alternatives (only for selected modes)
                                    segmented = analyze_route_with_alternatives(
                                        otp_itinerary=itin,
                                        publibike_client=pb_client,
                                        escooter_client=es_client,
                                        otp_client=otp_client
                                    )

                                    route_data['segmented'] = segmented
                                    route_data['has_alternatives'] = any(
                                        seg.get('alternatives_available', False)
                                        for seg in segmented.get('segments', [])
                                    )

                                except Exception as e:
                                    # Segmentation failed, continue without it
                                    route_data['segmentation_error'] = str(e)

                            all_routes.append(route_data)
                            route_added = True  # Mark that we added a route
                    else:
                        all_routes.append({
                            'id': 'pt-none',
                            'mode': 'public_transport',
                            'summary': 'No public transport routes found',
                            'error': 'No routes available'
                        })
                except Exception as e:
                    all_routes.append({
                        'id': 'pt-error',
                        'mode': 'public_transport',
                        'summary': f'OTP service error',
                        'error': str(e)
                    })
            else:
                # Fallback if OTP not available
                all_routes.extend([
                    {'id': 'pt-1', 'mode': 'public_transport', 'summary': 'Walk 5 → Tram 8 → Bus 19', 'duration_min': 32},
                    {'id': 'pt-2', 'mode': 'public_transport', 'summary': 'Walk 12 → Tram 7', 'duration_min': 26},
                ])
        elif mode == 'e_scooter':
            # Check for available Voi E-Scooters near start location
            if ESCOOTER_AVAILABLE:
                try:
                    client = VoiScooterClient()
                    # Check start location for available scooters within 300m
                    nearby_scooters = get_nearby_scooters(g_start.lat, g_start.lon, radius_m=300, client=client)

                    if nearby_scooters:
                        # Use the closest available scooter
                        scooter, scooter_dist = nearby_scooters[0]

                        battery = scooter.get_battery_percentage()
                        battery_str = f"{battery:.0f}%" if battery else "N/A"

                        # Calculate route from scooter to destination using OTP
                        if OTP_AVAILABLE:
                            try:
                                otp_client = OTPClient(base_url=os.getenv('OTP_BASE_URL', 'http://localhost:8080/otp'))
                                # Use WALK mode as proxy for e-scooter (OTP doesn't have native SCOOTER routing)
                                # We'll adjust speed/duration manually
                                otp_response = otp_client.plan(
                                    from_lat=scooter.latitude, from_lon=scooter.longitude,
                                    to_lat=g_dest.lat, to_lon=g_dest.lon,
                                    mode="WALK",  # Use walk paths for scooter routing
                                    max_walk_distance=10000,  # Allow longer distances
                                    num_itineraries=1
                                )

                                itineraries = otp_response.get('plan', {}).get('itineraries', [])
                                if itineraries:
                                    parsed = parse_otp_itinerary(itineraries[0])
                                    # E-Scooters are ~3x faster than walking (assume 15 km/h vs 5 km/h)
                                    scooter_duration_min = max(3, round(parsed['duration_min'] / 3, 1))
                                    walk_duration_min = round(scooter_dist / 80, 1)  # ~80m/min walking speed
                                    total_duration = scooter_duration_min + walk_duration_min
                                    distance_km = parsed['walk_distance_m'] / 1000

                                    summary = f"Walk {int(scooter_dist)}m to Voi scooter ({battery_str}) → Scooter {distance_km:.1f}km to destination"
                                else:
                                    # No route found, use estimate
                                    total_duration = 14
                                    summary = f"Walk {int(scooter_dist)}m to Voi scooter (Battery: {battery_str})"
                            except Exception:
                                # OTP error, use estimate
                                total_duration = 14
                                summary = f"Walk {int(scooter_dist)}m to Voi scooter (Battery: {battery_str})"
                        else:
                            # No OTP, use estimate
                            total_duration = 14
                            summary = f"Walk {int(scooter_dist)}m to Voi scooter (Battery: {battery_str})"

                        all_routes.append({
                            'id': 'escoot-1',
                            'mode': 'e_scooter',
                            'summary': summary,
                            'duration_min': round(total_duration, 1),
                            'scooter': {
                                'id': scooter.vehicle_id,
                                'distance': int(scooter_dist),
                                'battery_percentage': battery,
                                'provider': scooter.provider_name,
                                'latitude': scooter.latitude,
                                'longitude': scooter.longitude
                            },
                            'nearby_scooters': [
                                {
                                    'id': s.vehicle_id,
                                    'distance': int(d),
                                    'battery_percentage': s.get_battery_percentage(),
                                    'latitude': s.latitude,
                                    'longitude': s.longitude
                                } for s, d in nearby_scooters[:5]  # Include up to 5 nearest scooters
                            ]
                        })
                    else:
                        # No scooters found
                        all_routes.append({
                            'id': 'escoot-none',
                            'mode': 'e_scooter',
                            'summary': 'No Voi scooters available within 300m',
                            'error': 'No scooters available nearby'
                        })
                except Exception as e:
                    all_routes.append({
                        'id': 'escoot-error',
                        'mode': 'e_scooter',
                        'summary': f'E-Scooter service error',
                        'error': str(e)
                    })
            else:
                # Fallback if E-Scooter API not available
                all_routes.append({
                    'id': 'escoot-1', 'mode': 'e_scooter', 'summary': 'Scooter 2.8 km', 'duration_min': 14
                })
        elif mode == 'publibike':
            # Check for available PubliBikes near start and destination
            if PUBLIBIKE_AVAILABLE:
                try:
                    client = PubliBikeClient()
                    # Check start location for available bikes
                    nearby_start = get_nearby_bikes(g_start.lat, g_start.lon, radius_m=300, client=client)
                    # Check destination for return stations
                    nearby_dest = get_nearby_return_stations(g_dest.lat, g_dest.lon, radius_m=300, client=client)

                    if nearby_start and nearby_dest:
                        # Both start and destination stations available
                        start_station, start_dist = nearby_start[0]
                        dest_station, dest_dist = nearby_dest[0]

                        bike_count = start_station.available_bikes_count()
                        ebike_count = start_station.available_ebikes_count()

                        # Calculate bike route using OTP
                        if OTP_AVAILABLE:
                            try:
                                otp_client = OTPClient(base_url=os.getenv('OTP_BASE_URL', 'http://localhost:8080/otp'))
                                otp_response = otp_client.plan_bicycle(
                                    from_lat=start_station.latitude, from_lon=start_station.longitude,
                                    to_lat=dest_station.latitude, to_lon=dest_station.longitude,
                                    num_itineraries=1
                                )

                                itineraries = otp_response.get('plan', {}).get('itineraries', [])
                                if itineraries:
                                    parsed = parse_otp_itinerary(itineraries[0])
                                    bike_duration_min = parsed['duration_min']
                                    bike_distance_km = parsed['walk_distance_m'] / 1000  # 'walk' distance is total distance

                                    # Add walking time to/from stations (~80m/min)
                                    walk_to_station_min = round(start_dist / 80, 1)
                                    walk_from_station_min = round(dest_dist / 80, 1)
                                    total_duration = bike_duration_min + walk_to_station_min + walk_from_station_min

                                    if ebike_count > 0:
                                        summary = f"Walk {int(start_dist)}m to {start_station.name} → E-Bike {bike_distance_km:.1f}km → {dest_station.name} → Walk {int(dest_dist)}m"
                                    else:
                                        summary = f"Walk {int(start_dist)}m to {start_station.name} → Bike {bike_distance_km:.1f}km → {dest_station.name} → Walk {int(dest_dist)}m"
                                else:
                                    # No route found, use estimate
                                    total_duration = 18
                                    if ebike_count > 0:
                                        summary = f"Walk {int(start_dist)}m to {start_station.name} → E-Bike → {dest_station.name} ({int(dest_dist)}m to destination)"
                                    else:
                                        summary = f"Walk {int(start_dist)}m to {start_station.name} → Bike → {dest_station.name} ({int(dest_dist)}m to destination)"
                            except Exception:
                                # OTP error, use estimate
                                total_duration = 18
                                if ebike_count > 0:
                                    summary = f"Walk {int(start_dist)}m to {start_station.name} → E-Bike → {dest_station.name} ({int(dest_dist)}m to destination)"
                                else:
                                    summary = f"Walk {int(start_dist)}m to {start_station.name} → Bike → {dest_station.name} ({int(dest_dist)}m to destination)"
                        else:
                            # No OTP, use estimate
                            total_duration = 18
                            if ebike_count > 0:
                                summary = f"Walk {int(start_dist)}m to {start_station.name} → E-Bike → {dest_station.name} ({int(dest_dist)}m to destination)"
                            else:
                                summary = f"Walk {int(start_dist)}m to {start_station.name} → Bike → {dest_station.name} ({int(dest_dist)}m to destination)"

                        all_routes.append({
                            'id': 'bike-1',
                            'mode': 'publibike',
                            'summary': summary,
                            'duration_min': round(total_duration, 1),
                            'start_station': {
                                'name': start_station.name,
                                'distance': int(start_dist),
                                'address': start_station.address,
                                'bikes_available': bike_count,
                                'ebikes_available': ebike_count,
                                'latitude': start_station.latitude,
                                'longitude': start_station.longitude
                            },
                            'dest_station': {
                                'name': dest_station.name,
                                'distance': int(dest_dist),
                                'address': dest_station.address,
                                'latitude': dest_station.latitude,
                                'longitude': dest_station.longitude
                            }
                        })

                        # Add alternative routes with different station combinations
                        for i, (s_station, s_dist) in enumerate(nearby_start[1:2], 2):  # Next start station
                            for d_station, d_dist in nearby_dest[0:1]:  # Same dest station
                                bike_cnt = s_station.available_bikes_count()
                                ebike_cnt = s_station.available_ebikes_count()

                                # Calculate alternative route with OTP
                                if OTP_AVAILABLE:
                                    try:
                                        # Reuse or create OTP client
                                        if not locals().get('otp_client'):
                                            otp_client = OTPClient(base_url=os.getenv('OTP_BASE_URL', 'http://localhost:8080/otp'))
                                        otp_response = otp_client.plan_bicycle(
                                            from_lat=s_station.latitude, from_lon=s_station.longitude,
                                            to_lat=d_station.latitude, to_lon=d_station.longitude,
                                            num_itineraries=1
                                        )

                                        itineraries = otp_response.get('plan', {}).get('itineraries', [])
                                        if itineraries:
                                            parsed = parse_otp_itinerary(itineraries[0])
                                            bike_duration = parsed['duration_min']
                                            bike_dist_km = parsed['walk_distance_m'] / 1000

                                            walk_to = round(s_dist / 80, 1)
                                            walk_from = round(d_dist / 80, 1)
                                            alt_total = bike_duration + walk_to + walk_from

                                            if ebike_cnt > 0:
                                                alt_summary = f"Walk {int(s_dist)}m to {s_station.name} → E-Bike {bike_dist_km:.1f}km → {d_station.name} → Walk {int(d_dist)}m"
                                            else:
                                                alt_summary = f"Walk {int(s_dist)}m to {s_station.name} → Bike {bike_dist_km:.1f}km → {d_station.name} → Walk {int(d_dist)}m"
                                        else:
                                            alt_total = 18 + (i-1)*2
                                            if ebike_cnt > 0:
                                                alt_summary = f"Walk {int(s_dist)}m to {s_station.name} → E-Bike → {d_station.name} ({int(d_dist)}m to destination)"
                                            else:
                                                alt_summary = f"Walk {int(s_dist)}m to {s_station.name} → Bike → {d_station.name} ({int(d_dist)}m to destination)"
                                    except Exception:
                                        alt_total = 18 + (i-1)*2
                                        if ebike_cnt > 0:
                                            alt_summary = f"Walk {int(s_dist)}m to {s_station.name} → E-Bike → {d_station.name} ({int(d_dist)}m to destination)"
                                        else:
                                            alt_summary = f"Walk {int(s_dist)}m to {s_station.name} → Bike → {d_station.name} ({int(d_dist)}m to destination)"
                                else:
                                    alt_total = 18 + (i-1)*2
                                    if ebike_cnt > 0:
                                        alt_summary = f"Walk {int(s_dist)}m to {s_station.name} → E-Bike → {d_station.name} ({int(d_dist)}m to destination)"
                                    else:
                                        alt_summary = f"Walk {int(s_dist)}m to {s_station.name} → Bike → {d_station.name} ({int(d_dist)}m to destination)"

                                all_routes.append({
                                    'id': f'bike-{i}',
                                    'mode': 'publibike',
                                    'summary': alt_summary,
                                    'duration_min': round(alt_total, 1),
                                    'start_station': {
                                        'name': s_station.name,
                                        'distance': int(s_dist),
                                        'address': s_station.address,
                                        'bikes_available': bike_cnt,
                                        'ebikes_available': ebike_cnt,
                                        'latitude': s_station.latitude,
                                        'longitude': s_station.longitude
                                    },
                                    'dest_station': {
                                        'name': d_station.name,
                                        'distance': int(d_dist),
                                        'address': d_station.address,
                                        'latitude': d_station.latitude,
                                        'longitude': d_station.longitude
                                    }
                                })
                    elif nearby_start and not nearby_dest:
                        # Start station available but no destination station
                        all_routes.append({
                            'id': 'bike-warning',
                            'mode': 'publibike',
                            'summary': 'Bikes available at start, but no return station near destination (within 300m)',
                            'duration_min': None,
                            'warning': 'No return station near destination'
                        })
                    elif not nearby_start and nearby_dest:
                        # Destination station available but no bikes at start
                        all_routes.append({
                            'id': 'bike-warning',
                            'mode': 'publibike',
                            'summary': 'Return station available at destination, but no bikes near start (within 300m)',
                            'duration_min': None,
                            'warning': 'No bikes available at start'
                        })
                    else:
                        # Neither start nor destination stations available
                        all_routes.append({
                            'id': 'bike-none',
                            'mode': 'publibike',
                            'summary': 'No PubliBike stations within 300m of start or destination',
                            'duration_min': None,
                            'warning': 'No stations available nearby'
                        })
                except Exception as e:
                    # Fallback to mock data if API fails
                    all_routes.append({
                        'id': 'bike-1',
                        'mode': 'publibike',
                        'summary': f'PubliBike route (API unavailable: {str(e)})',
                        'duration_min': 18
                    })
            else:
                # PubliBike API not available - use mock data
                all_routes.append({
                    'id': 'bike-1',
                    'mode': 'publibike',
                    'summary': 'Cycle 3.6 km',
                    'duration_min': 18
                })

    return jsonify({
        'received': {'from': start, 'to': dest, 'modes': modes},
        'geocoded': {
            'from': {
                'query': g_start.query,
                'lat': g_start.lat,
                'lon': g_start.lon,
                'display_name': g_start.display_name,
            },
            'to': {
                'query': g_dest.query,
                'lat': g_dest.lat,
                'lon': g_dest.lon,
                'display_name': g_dest.display_name,
            },
        },
        'routes': all_routes
    })

@app.route('/api/modes', methods=['GET'])
def api_modes():
    return jsonify({'modes': ['public_transport', 'e_scooter', 'publibike']})

@app.route('/api/routes/multimodal', methods=['POST'])
def api_routes_multimodal():
    """
    Multimodal route planning endpoint.
    Combines different transport modes in a single journey.
    Example: E-Scooter to train station → Train → PubliBike to destination
    """
    data = request.get_json(silent=True) or {}
    start = data.get('from')
    dest = data.get('to')

    if not start or not dest:
        return jsonify({
            'error': 'Both "from" and "to" are required.',
            'received': {'from': start, 'to': dest}
        }), 400

    # Geocode addresses
    geocoder = Geocoder(user_agent="WPR2_Project_Group_05/0.1", email=os.getenv('CONTACT_EMAIL'))

    try:
        g_start, g_dest = geocode_pair(geocoder, start, dest)
    except Exception as e:
        return jsonify({
            'error': f"Geocoding service error: {str(e)}",
            'received': {'from': start, 'to': dest}
        }), 500

    if g_start is None or g_dest is None:
        return jsonify({
            'error': 'Could not find location(s).',
            'received': {'from': start, 'to': dest}
        }), 422

    multimodal_routes = []

    # Try multimodal combinations using OTP
    if OTP_AVAILABLE:
        try:
            otp_client = OTPClient(base_url=os.getenv('OTP_BASE_URL', 'http://localhost:8080/otp'))

            # Option 1: Transit + Bicycle
            try:
                response = otp_client.plan_multimodal(
                    from_lat=g_start.lat, from_lon=g_start.lon,
                    to_lat=g_dest.lat, to_lon=g_dest.lon,
                    modes=["TRANSIT", "BICYCLE", "WALK"],
                    num_itineraries=2
                )
                itineraries = response.get('plan', {}).get('itineraries', [])
                for i, itin in enumerate(itineraries):
                    parsed = parse_otp_itinerary(itin)

                    # Filter out walk-only routes
                    if is_walk_only_route(parsed):
                        continue

                    multimodal_routes.append({
                        'id': f'multi-transit-bike-{i+1}',
                        'mode': 'multimodal',
                        'modes_used': ['transit', 'bicycle'],
                        'summary': format_itinerary_summary(parsed),
                        'duration_min': parsed['duration_min'],
                        'transfers': parsed['transfers'],
                        'legs': parsed['legs']
                    })
            except Exception:
                pass  # Continue with other combinations

            # Option 2: Bicycle + Transit
            try:
                response = otp_client.plan_multimodal(
                    from_lat=g_start.lat, from_lon=g_start.lon,
                    to_lat=g_dest.lat, to_lon=g_dest.lon,
                    modes=["BICYCLE", "TRANSIT", "WALK"],
                    num_itineraries=1
                )
                itineraries = response.get('plan', {}).get('itineraries', [])
                for i, itin in enumerate(itineraries):
                    parsed = parse_otp_itinerary(itin)

                    # Filter out walk-only routes
                    if is_walk_only_route(parsed):
                        continue

                    multimodal_routes.append({
                        'id': f'multi-bike-transit-{i+1}',
                        'mode': 'multimodal',
                        'modes_used': ['bicycle', 'transit'],
                        'summary': format_itinerary_summary(parsed),
                        'duration_min': parsed['duration_min'],
                        'transfers': parsed['transfers'],
                        'legs': parsed['legs']
                    })
            except Exception:
                pass

        except Exception as e:
            multimodal_routes.append({
                'error': f'OTP multimodal error: {str(e)}',
                'mode': 'multimodal'
            })

    return jsonify({
        'received': {'from': start, 'to': dest},
        'geocoded': {
            'from': {
                'query': g_start.query,
                'lat': g_start.lat,
                'lon': g_start.lon,
                'display_name': g_start.display_name,
            },
            'to': {
                'query': g_dest.query,
                'lat': g_dest.lat,
                'lon': g_dest.lon,
                'display_name': g_dest.display_name,
            },
        },
        'routes': multimodal_routes
    })

@app.route('/api/routes/segmented', methods=['POST'])
def api_routes_segmented():
    """
    Segmented route planning with alternatives at transfer points.

    Example: Wylerstrasse 101 → Bahnhof Bern (Bus) → Shows alternatives at Bahnhof
    for onward journey (PubliBike, E-Scooter, other buses)

    Returns routes broken down into segments with alternative modes at each transfer.
    """
    data = request.get_json(silent=True) or {}
    start = data.get('from')
    dest = data.get('to')
    primary_mode = data.get('primary_mode', 'public_transport')
    # Alternative modes to consider at transfer points (default: all)
    alternative_modes = data.get('alternative_modes', ['publibike', 'e_scooter'])

    if not start or not dest:
        return jsonify({
            'error': 'Both "from" and "to" are required.',
            'received': {'from': start, 'to': dest}
        }), 400

    # Geocode addresses
    geocoder = Geocoder(user_agent="WPR2_Project_Group_05/0.1", email=os.getenv('CONTACT_EMAIL'))

    try:
        g_start, g_dest = geocode_pair(geocoder, start, dest)
    except Exception as e:
        return jsonify({
            'error': f"Geocoding service error: {str(e)}",
            'received': {'from': start, 'to': dest}
        }), 500

    if g_start is None or g_dest is None:
        return jsonify({
            'error': 'Could not find location(s).',
            'received': {'from': start, 'to': dest}
        }), 422

    if not OTP_AVAILABLE:
        return jsonify({
            'error': 'OTP service not available for segmented routing',
            'received': {'from': start, 'to': dest}
        }), 503

    segmented_routes = []

    try:
        otp_client = OTPClient(base_url=os.getenv('OTP_BASE_URL', 'http://localhost:8080/otp'))

        # Get primary route (e.g., public transport)
        if primary_mode == 'public_transport':
            otp_response = otp_client.plan_public_transport(
                from_lat=g_start.lat, from_lon=g_start.lon,
                to_lat=g_dest.lat, to_lon=g_dest.lon,
                num_itineraries=3
            )
        else:
            otp_response = otp_client.plan(
                from_lat=g_start.lat, from_lon=g_start.lon,
                to_lat=g_dest.lat, to_lon=g_dest.lon,
                mode="TRANSIT,WALK",
                num_itineraries=3
            )

        itineraries = otp_response.get('plan', {}).get('itineraries', [])

        if not itineraries:
            return jsonify({
                'error': 'No routes found',
                'received': {'from': start, 'to': dest}
            }), 404

        # Analyze each itinerary for segments and alternatives
        for i, itin in enumerate(itineraries):
            parsed = parse_otp_itinerary(itin)

            # Filter out routes that only contain WALK legs
            if is_walk_only_route(parsed):
                continue

            # Prepare clients for alternative discovery (only for selected modes)
            pb_client = None
            es_client = None

            if 'publibike' in alternative_modes and PUBLIBIKE_AVAILABLE:
                pb_client = PubliBikeClient()

            if 'e_scooter' in alternative_modes and ESCOOTER_AVAILABLE:
                es_client = VoiScooterClient()

            # Analyze route with alternatives
            if SEGMENTATION_AVAILABLE:
                try:
                    segmented = analyze_route_with_alternatives(
                        otp_itinerary=itin,
                        publibike_client=pb_client,
                        escooter_client=es_client,
                        otp_client=otp_client
                    )

                    segmented_routes.append({
                        'id': f'segmented-{i+1}',
                        'primary_mode': primary_mode,
                        'summary': format_itinerary_summary(parsed),
                        'total_duration_min': parsed['duration_min'],
                        'total_transfers': segmented.get('total_transfers', 0),
                        'transfer_points': segmented.get('transfer_points', []),
                        'segments': segmented.get('segments', []),
                        'original_legs': parsed['legs']
                    })

                except Exception as e:
                    # Fallback: return without segmentation
                    segmented_routes.append({
                        'id': f'route-{i+1}',
                        'primary_mode': primary_mode,
                        'summary': format_itinerary_summary(parsed),
                        'total_duration_min': parsed['duration_min'],
                        'error': f'Segmentation failed: {str(e)}',
                        'legs': parsed['legs']
                    })
            else:
                # No segmentation available
                segmented_routes.append({
                    'id': f'route-{i+1}',
                    'primary_mode': primary_mode,
                    'summary': format_itinerary_summary(parsed),
                    'total_duration_min': parsed['duration_min'],
                    'legs': parsed['legs'],
                    'note': 'Segmentation not available'
                })

    except Exception as e:
        return jsonify({
            'error': f'Routing failed: {str(e)}',
            'received': {'from': start, 'to': dest}
        }), 500

    return jsonify({
        'received': {'from': start, 'to': dest, 'primary_mode': primary_mode},
        'geocoded': {
            'from': {
                'query': g_start.query,
                'lat': g_start.lat,
                'lon': g_start.lon,
                'display_name': g_start.display_name,
            },
            'to': {
                'query': g_dest.query,
                'lat': g_dest.lat,
                'lon': g_dest.lon,
                'display_name': g_dest.display_name,
            },
        },
        'routes': segmented_routes
    })

@app.route('/api/escooters/nearby', methods=['GET'])
def api_escooters_nearby():
    """Get nearby Voi E-Scooters for a given location.
    Query parameters:
    - lat: latitude
    - lon: longitude
    - radius: search radius in meters (default: 300)
    """
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
    except (TypeError, ValueError):
        return jsonify({
            'error': 'Invalid or missing lat/lon parameters'
        }), 400

    radius = int(request.args.get('radius', 300))

    if not ESCOOTER_AVAILABLE:
        return jsonify({
            'error': 'E-Scooter API not available',
            'scooters': []
        }), 503

    try:
        client = VoiScooterClient()
        nearby_scooters = get_nearby_scooters(lat, lon, radius_m=radius, client=client)

        scooters_data = [
            {
                'id': scooter.vehicle_id,
                'latitude': scooter.latitude,
                'longitude': scooter.longitude,
                'distance_m': round(distance, 1),
                'battery_percentage': scooter.get_battery_percentage(),
                'is_available': scooter.is_available(),
                'provider': scooter.provider_name,
                'vehicle_type': scooter.vehicle_type
            }
            for scooter, distance in nearby_scooters
        ]

        return jsonify({
            'scooters': scooters_data,
            'count': len(scooters_data),
            'query': {
                'lat': lat,
                'lon': lon,
                'radius_m': radius
            }
        })

    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch e-scooters: {str(e)}',
            'scooters': []
        }), 500

if __name__ == '__main__':
    # Development server for local testing. In production use a WSGI server.
    app.run(debug=True, host='127.0.0.1', port=5000)
