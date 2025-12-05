// Global state
let map = null;
let startMarker = null;
let destMarker = null;
let startCoords = null;
let destCoords = null;
let pickingMode = null; // 'start' or 'dest'
let bikeStationMarkers = []; // Array to store PubliBike station markers
let escooterMarkers = []; // Array to store E-Scooter markers
let transferMarkers = []; // Array to store transfer point markers

// Icons for markers
const startIcon = L.icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const destIcon = L.icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

// Icons for PubliBike stations (smaller markers)
const bikePickupIcon = L.icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [20, 33],
  iconAnchor: [10, 33],
  popupAnchor: [1, -28],
  shadowSize: [33, 33]
});

const bikeReturnIcon = L.icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [20, 33],
  iconAnchor: [10, 33],
  popupAnchor: [1, -28],
  shadowSize: [33, 33]
});

// Icon for E-Scooters (orange/violet for Voi branding)
const escooterIcon = L.icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-violet.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [18, 30],
  iconAnchor: [9, 30],
  popupAnchor: [1, -25],
  shadowSize: [30, 30]
});

// Icon for Transfer Points (yellow/orange)
const transferIcon = L.icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-orange.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [22, 36],
  iconAnchor: [11, 36],
  popupAnchor: [1, -30],
  shadowSize: [36, 36]
});

document.addEventListener('DOMContentLoaded', () => {
  const modeCheckboxes = document.querySelectorAll('.mode-checkbox');
  const modeInputs = document.querySelectorAll('input[name="mode"]');
  const results = document.getElementById('results');
  const planBtn = document.getElementById('plan');
  const swapBtn = document.getElementById('swap');
  const fromInp = document.getElementById('from');
  const toInp = document.getElementById('to');
  const form = document.getElementById('plannerForm');
  const pinStartBtn = document.getElementById('pinStart');
  const pinDestBtn = document.getElementById('pinDest');
  const mapInstructions = document.getElementById('mapInstructions');

  // Initialize map centered on Bern
  initMap();

  function initMap() {
    map = L.map('map').setView([46.9480, 7.4474], 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19
    }).addTo(map);

    // Handle map clicks
    map.on('click', onMapClick);
  }

  function onMapClick(e) {
    if (!pickingMode) return;

    const lat = e.latlng.lat;
    const lon = e.latlng.lng;

    if (pickingMode === 'start') {
      setStartLocation(lat, lon);
      reverseGeocode(lat, lon, 'start');
      pickingMode = null;
      pinStartBtn.classList.remove('active');
      updateMapInstructions();
    } else if (pickingMode === 'dest') {
      setDestLocation(lat, lon);
      reverseGeocode(lat, lon, 'dest');
      pickingMode = null;
      pinDestBtn.classList.remove('active');
      updateMapInstructions();
    }
  }

  function setStartLocation(lat, lon) {
    startCoords = { lat, lon };
    if (startMarker) {
      map.removeLayer(startMarker);
    }
    startMarker = L.marker([lat, lon], { icon: startIcon })
      .addTo(map)
      .bindPopup('Start')
      .openPopup();
  }

  function setDestLocation(lat, lon) {
    destCoords = { lat, lon };
    if (destMarker) {
      map.removeLayer(destMarker);
    }
    destMarker = L.marker([lat, lon], { icon: destIcon })
      .addTo(map)
      .bindPopup('Destination')
      .openPopup();
  }

  function clearBikeStationMarkers() {
    // Remove all existing bike station markers
    bikeStationMarkers.forEach(marker => {
      map.removeLayer(marker);
    });
    bikeStationMarkers = [];
  }

  function clearEscooterMarkers() {
    // Remove all existing e-scooter markers
    escooterMarkers.forEach(marker => {
      map.removeLayer(marker);
    });
    escooterMarkers = [];
  }

  function clearTransferMarkers() {
    // Remove all existing transfer point markers
    transferMarkers.forEach(marker => {
      map.removeLayer(marker);
    });
    transferMarkers = [];
  }

  function addTransferPointMarkers(routes) {
    // Clear existing transfer markers
    clearTransferMarkers();

    // Find routes with segmentation data
    const segmentedRoutes = routes.filter(r => r.segmented && r.segmented.transfer_points);
    if (!segmentedRoutes.length) return;

    // Collect unique transfer points (exclude start and end)
    const transferPoints = new Set();

    segmentedRoutes.forEach(route => {
      const points = route.segmented.transfer_points;
      // Skip first (start) and last (destination) points
      for (let i = 1; i < points.length - 1; i++) {
        const tp = points[i];
        if (tp.is_station) {
          const key = `${tp.latitude.toFixed(5)},${tp.longitude.toFixed(5)}`;
          if (!transferPoints.has(key)) {
            transferPoints.add(key);

            // Add marker
            const marker = L.marker([tp.latitude, tp.longitude], { icon: transferIcon })
              .addTo(map);

            let popupContent = `<strong>🔄 ${tp.name}</strong><br>`;
            popupContent += `<em>Transfer Point</em>`;

            marker.bindPopup(popupContent);
            transferMarkers.push(marker);
          }
        }
      }
    });
  }

  function addEscooterMarkers(routes) {
    // Clear existing e-scooter markers first
    clearEscooterMarkers();

    // Find E-Scooter routes
    const escooterRoutes = routes.filter(r => r.mode === 'e_scooter');
    if (!escooterRoutes.length) return;

    // Find the closest scooter across all routes
    let closestScooter = null;
    let minDistance = Infinity;

    escooterRoutes.forEach(route => {
      if (route.nearby_scooters && Array.isArray(route.nearby_scooters)) {
        route.nearby_scooters.forEach(scooter => {
          if (scooter.distance < minDistance) {
            minDistance = scooter.distance;
            closestScooter = scooter;
          }
        });
      }
    });

    // Add marker only for the closest scooter
    if (closestScooter) {
      const battery = closestScooter.battery_percentage;
      const batteryStr = battery ? `${battery.toFixed(0)}%` : 'N/A';

      const popupContent = `
        <b>Voi E-Scooter (Closest)</b><br>
        Distance: ${closestScooter.distance}m<br>
        Battery: ${batteryStr}<br>
        ID: ${closestScooter.id.substring(closestScooter.id.lastIndexOf(':') + 1, closestScooter.id.lastIndexOf(':') + 9)}...
      `;

      const marker = L.marker([closestScooter.latitude, closestScooter.longitude], { icon: escooterIcon })
        .addTo(map)
        .bindPopup(popupContent)
        .openPopup(); // Automatically open the popup for the closest scooter

      escooterMarkers.push(marker);
    }
  }

  function addBikeStationMarkers(routes) {
    // Clear existing markers first
    clearBikeStationMarkers();

    // Find PubliBike routes
    const bikeRoutes = routes.filter(r => r.mode === 'publibike');
    if (!bikeRoutes.length) return;

    // Track unique stations to avoid duplicates
    const addedStations = new Set();

    bikeRoutes.forEach(route => {
      // Add pickup station marker
      if (route.start_station && route.start_station.latitude && route.start_station.longitude) {
        const stationKey = `pickup-${route.start_station.name}`;
        if (!addedStations.has(stationKey)) {
          addedStations.add(stationKey);

          const marker = L.marker(
            [route.start_station.latitude, route.start_station.longitude],
            { icon: bikePickupIcon }
          ).addTo(map);

          let popupContent = `<strong>🟢 ${route.start_station.name}</strong><br>`;
          popupContent += `<em>Pick-up Station</em><br>`;
          popupContent += `${route.start_station.distance}m from start<br>`;
          if (route.start_station.bikes_available) {
            popupContent += `<strong>${route.start_station.bikes_available} bike(s) available</strong>`;
            if (route.start_station.ebikes_available > 0) {
              popupContent += ` (${route.start_station.ebikes_available} e-bike(s))`;
            }
          }
          if (route.start_station.address) {
            popupContent += `<br><small>${route.start_station.address}</small>`;
          }

          marker.bindPopup(popupContent);
          bikeStationMarkers.push(marker);
        }
      }

      // Add return station marker
      if (route.dest_station && route.dest_station.latitude && route.dest_station.longitude) {
        const stationKey = `return-${route.dest_station.name}`;
        if (!addedStations.has(stationKey)) {
          addedStations.add(stationKey);

          const marker = L.marker(
            [route.dest_station.latitude, route.dest_station.longitude],
            { icon: bikeReturnIcon }
          ).addTo(map);

          let popupContent = `<strong>🔴 ${route.dest_station.name}</strong><br>`;
          popupContent += `<em>Return Station</em><br>`;
          popupContent += `${route.dest_station.distance}m from destination`;
          if (route.dest_station.address) {
            popupContent += `<br><small>${route.dest_station.address}</small>`;
          }

          marker.bindPopup(popupContent);
          bikeStationMarkers.push(marker);
        }
      }
    });
  }

  async function reverseGeocode(lat, lon, type) {
    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=18&addressdetails=1`,
        {
          headers: {
            'User-Agent': 'WPR2_Project_Group_05/0.1'
          }
        }
      );
      const data = await response.json();
      const address = data.display_name || `${lat.toFixed(5)}, ${lon.toFixed(5)}`;

      if (type === 'start') {
        fromInp.value = address;
      } else {
        toInp.value = address;
      }
    } catch (e) {
      // Fallback to coordinates
      const coordStr = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
      if (type === 'start') {
        fromInp.value = coordStr;
      } else {
        toInp.value = coordStr;
      }
    }
  }

  function updateMapInstructions() {
    if (pickingMode === 'start') {
      mapInstructions.textContent = '📍 Click map to set START location';
      mapInstructions.style.color = '#28a745';
    } else if (pickingMode === 'dest') {
      mapInstructions.textContent = '📍 Click map to set DESTINATION location';
      mapInstructions.style.color = '#dc3545';
    } else {
      mapInstructions.textContent = 'Click pin buttons or click map to set locations';
      mapInstructions.style.color = '';
    }
  }

  // Pin button handlers
  pinStartBtn.addEventListener('click', () => {
    if (pickingMode === 'start') {
      pickingMode = null;
      pinStartBtn.classList.remove('active');
    } else {
      pickingMode = 'start';
      pinStartBtn.classList.add('active');
      pinDestBtn.classList.remove('active');
    }
    updateMapInstructions();
  });

  pinDestBtn.addEventListener('click', () => {
    if (pickingMode === 'dest') {
      pickingMode = null;
      pinDestBtn.classList.remove('active');
    } else {
      pickingMode = 'dest';
      pinDestBtn.classList.add('active');
      pinStartBtn.classList.remove('active');
    }
    updateMapInstructions();
  });

  // Mode selection - handle checkbox changes
  modeInputs.forEach(input => {
    input.addEventListener('change', (e) => {
      const label = e.target.closest('.mode-checkbox');
      if (e.target.checked) {
        label.classList.add('active');
      } else {
        label.classList.remove('active');
      }
    });
  });

  // Allow clicking anywhere on the label to toggle
  modeCheckboxes.forEach(label => {
    label.addEventListener('click', (e) => {
      // Let the checkbox handle the click naturally
      if (e.target.tagName !== 'INPUT') {
        const checkbox = label.querySelector('input[type="checkbox"]');
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event('change'));
      }
    });
  });

  // Swap button
  swapBtn.addEventListener('click', () => {
    const a = fromInp.value;
    fromInp.value = toInp.value;
    toInp.value = a;

    // Swap markers and coordinates
    const tempCoords = startCoords;
    startCoords = destCoords;
    destCoords = tempCoords;

    const tempMarker = startMarker;
    startMarker = destMarker;
    destMarker = tempMarker;

    if (startMarker) {
      startMarker.setIcon(startIcon).bindPopup('Start');
    }
    if (destMarker) {
      destMarker.setIcon(destIcon).bindPopup('Destination');
    }
  });

  // Render routes
  function renderRoutes(data) {
    if (data.error) {
      results.innerHTML = `<div class="route-placeholder">${data.error}</div>`;
      return;
    }

    // Save geocoded data globally for station markers
    window.lastGeocodedData = data.geocoded;

    // Update map with geocoded locations if available
    if (data.geocoded && data.geocoded.from && data.geocoded.to) {
      const from = data.geocoded.from;
      const to = data.geocoded.to;

      setStartLocation(from.lat, from.lon);
      setDestLocation(to.lat, to.lon);

      // Fit map to show both markers
      const bounds = L.latLngBounds([
        [from.lat, from.lon],
        [to.lat, to.lon]
      ]);
      map.fitBounds(bounds, { padding: [50, 50] });
    }

    const routes = data.routes || [];
    if (!routes.length) {
      results.innerHTML = '<div class="route-placeholder">No routes found.</div>';
      return;
    }

    // Add PubliBike station markers to map
    addBikeStationMarkers(routes);

    // Add E-Scooter markers to map
    addEscooterMarkers(routes);

    // Add transfer point markers to map
    addTransferPointMarkers(routes);

    // Group routes by mode
    const groupedRoutes = {};
    routes.forEach(r => {
      const mode = r.mode || 'unknown';
      if (!groupedRoutes[mode]) {
        groupedRoutes[mode] = [];
      }
      groupedRoutes[mode].push(r);
    });

    // Mode icons and labels
    const modeInfo = {
      'public_transport': { icon: '🚌', label: 'Public Transport' },
      'e_scooter': { icon: '🛴', label: 'E-Scooter' },
      'publibike': { icon: '🚲', label: 'PubliBike' }
    };

    // Render grouped routes
    let html = '';
    for (const [mode, modeRoutes] of Object.entries(groupedRoutes)) {
      const info = modeInfo[mode] || { icon: '📍', label: mode };
      html += `<div class="mode-group">`;
      html += `<div class="mode-group-header">${info.icon} ${info.label}</div>`;

      modeRoutes.forEach((r, routeIndex) => {
        const cost = r.est_cost_chf ? ` · ~${r.est_cost_chf} CHF` : '';
        let details = r.duration_min ? `${r.duration_min} min` : '';

        html += `<div class="route-card">`;
        html += `<div><strong>${r.summary || 'Route'}</strong></div>`;
        html += `<div class="route-details">${details}${cost}</div>`;

        // Check if route has segmentation data
        if (r.segmented && r.segmented.segments && r.segmented.segments.length > 0) {
          html += renderSegmentedRoute(r, routeIndex);
        }
        // Fallback: Add detailed station info for PubliBike routes
        else if (r.start_station || r.dest_station) {
          html += '<div class="station-details">';

          if (r.start_station) {
            html += `
              <div class="station-info">
                <strong>🟢 Pick up:</strong> ${r.start_station.name} (${r.start_station.distance}m)
            `;
            if (r.start_station.bikes_available) {
              html += `<br><span class="bikes-count">${r.start_station.bikes_available} bike(s) available`;
              if (r.start_station.ebikes_available > 0) {
                html += ` (${r.start_station.ebikes_available} e-bike(s))`;
              }
              html += `</span>`;
            }
            html += '</div>';
          }

          if (r.dest_station) {
            html += `
              <div class="station-info">
                <strong>🔴 Return:</strong> ${r.dest_station.name} (${r.dest_station.distance}m from destination)
              </div>
            `;
          }

          html += '</div>';
        }

        if (r.warning) {
          html += `<div class="route-warning">⚠ ${r.warning}</div>`;
        }

        html += '</div>';
      });

      html += `</div>`;
    }

    results.innerHTML = html;

    // Attach event listeners for toggle buttons
    attachAlternativeToggleListeners();
  }

  // Render segmented route with transfer points and alternatives
  function renderSegmentedRoute(route, routeIndex) {
    const segmented = route.segmented;
    let html = '<div class="segmented-route">';

    // Show transfer points count if available
    if (segmented.total_transfers !== undefined) {
      html += `<div class="route-meta">🔄 ${segmented.total_transfers} transfer(s)</div>`;
    }

    // Render each segment
    segmented.segments.forEach((segment, segIndex) => {
      const segId = `seg-${routeIndex}-${segIndex}`;

      html += `<div class="route-segment">`;

      // Segment header
      html += `<div class="segment-header">`;
      html += `<span class="segment-label">📍 ${segment.from} → ${segment.to}</span>`;
      html += `<span class="segment-mode">${getModeIcon(segment.mode)} ${segment.mode}</span>`;
      html += `</div>`;

      // Segment details
      html += `<div class="segment-details">`;
      if (segment.route_info && segment.route_info.route_short_name) {
        html += `<span class="segment-line">Line ${segment.route_info.route_short_name}</span> · `;
      }
      html += `${segment.duration_min} min · ${(segment.distance_m / 1000).toFixed(1)} km`;
      html += `</div>`;

      // Show alternatives if available
      if (segment.alternatives_available && segment.alternatives && segment.alternatives.length > 0) {
        const altCount = segment.alternatives.length;
        html += `
          <div class="alternatives-section">
            <button class="toggle-alternatives" data-segment="${segId}">
              ⚡ ${altCount} alternative(s) available at ${segment.to} 
              <span class="toggle-icon">▼</span>
            </button>
            <div class="alternatives-list" id="alt-${segId}" style="display: none;">
        `;

        segment.alternatives.forEach((alt, altIndex) => {
          html += renderAlternative(alt, segIndex, altIndex);
        });

        html += `</div></div>`;
      }

      html += `</div>`; // Close route-segment
    });

    html += '</div>'; // Close segmented-route
    return html;
  }

  // Render a single alternative
  function renderAlternative(alt, segIndex, altIndex) {
    let html = `<div class="alternative-card ${alt.mode}">`;

    // Alternative header
    const icon = getModeIcon(alt.mode);
    const duration = alt.duration_min ? `${alt.duration_min} min` : 'N/A';
    const cost = alt.est_cost_chf ? `CHF ${alt.est_cost_chf}` : '';

    html += `<div class="alternative-header">`;
    html += `<span class="alt-mode">${icon} ${alt.mode.toUpperCase()}</span>`;
    html += `<span class="alt-info">${duration}${cost ? ' · ' + cost : ''}</span>`;
    html += `</div>`;

    // Alternative summary with comparison badges
    html += `<div class="alternative-summary">`;
    html += alt.summary;

    // Add comparison badges if this alternative is better
    // (You can enhance this by comparing to original segment duration)
    if (alt.duration_min && alt.duration_min < 15) {
      html += `<span class="time-badge">⚡ Fast</span>`;
    }
    if (alt.est_cost_chf && alt.est_cost_chf <= 4.0) {
      html += `<span class="cost-badge">💰 Affordable</span>`;
    }

    html += `</div>`;

    // Mode-specific details
    if (alt.mode === 'publibike' && alt.start_station) {
      html += `<div class="alternative-details">`;
      html += `<div class="station-mini">`;
      html += `🟢 <strong>${alt.start_station.name}</strong> (${alt.start_station.distance_m}m)`;
      if (alt.start_station.bikes_available !== undefined) {
        html += `<br>&nbsp;&nbsp;&nbsp;${alt.start_station.bikes_available} bike(s)`;
        if (alt.start_station.ebikes_available > 0) {
          html += `, ${alt.start_station.ebikes_available} e-bike(s)`;
        }
        html += ' available';
      }
      html += `</div>`;
      if (alt.dest_station) {
        html += `<div class="station-mini">`;
        html += `🔴 <strong>${alt.dest_station.name}</strong> (${alt.dest_station.distance_m}m from destination)`;
        html += `</div>`;
      }
      if (alt.distance_km) {
        html += `<div class="station-mini">📏 ${alt.distance_km.toFixed(1)} km route</div>`;
      }
      html += `</div>`;
    } else if (alt.mode === 'e_scooter' && alt.scooter) {
      html += `<div class="alternative-details">`;
      html += `<div class="scooter-mini">`;
      html += `🛴 Scooter ${alt.scooter.distance_m}m away`;
      if (alt.scooter.battery_percentage !== undefined) {
        const batteryLevel = alt.scooter.battery_percentage;
        const batteryIcon = batteryLevel > 80 ? '🔋' : batteryLevel > 50 ? '🔋' : '🪫';
        html += ` · ${batteryIcon} ${batteryLevel.toFixed(0)}% battery`;
      }
      if (alt.distance_km) {
        html += `<br>📏 ${alt.distance_km.toFixed(1)} km route`;
      }
      html += `</div>`;
      html += `</div>`;
    }

    html += `</div>`; // Close alternative-card
    return html;
  }

  // Get icon for transport mode
  function getModeIcon(mode) {
    const icons = {
      'WALK': '🚶',
      'BUS': '🚌',
      'TRAM': '🚊',
      'RAIL': '🚆',
      'SUBWAY': '🚇',
      'TRANSIT': '🚌',
      'BICYCLE': '🚲',
      'publibike': '🚲',
      'e_scooter': '🛴',
      'FERRY': '⛴️'
    };
    return icons[mode] || '📍';
  }

  // Attach toggle listeners for alternatives
  function attachAlternativeToggleListeners() {
    const toggleButtons = document.querySelectorAll('.toggle-alternatives');
    toggleButtons.forEach(btn => {
      btn.addEventListener('click', function() {
        const segId = this.getAttribute('data-segment');
        const altList = document.getElementById(`alt-${segId}`);
        const icon = this.querySelector('.toggle-icon');

        if (altList.style.display === 'none') {
          altList.style.display = 'block';
          icon.textContent = '▲';
        } else {
          altList.style.display = 'none';
          icon.textContent = '▼';
        }
      });
    });
  }

  // Plan routes via API
  async function planRoutesViaAPI() {
    results.innerHTML = '<div class="route-placeholder">Loading results...</div>';

    // Get all selected modes
    const selectedModes = Array.from(modeInputs)
      .filter(input => input.checked)
      .map(input => input.value);

    if (selectedModes.length === 0) {
      results.innerHTML = '<div class="route-placeholder">Please select at least one travel mode.</div>';
      return;
    }

    const from = fromInp.value.trim();
    const to = toInp.value.trim();

    try {
      const res = await fetch('/api/routes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from, to, modes: selectedModes })
      });
      const data = await res.json();
      renderRoutes(data);
    } catch (e) {
      results.innerHTML = '<div class="route-placeholder">Failed to contact server.</div>';
    }
  }

  planBtn.addEventListener('click', (e) => {
    e.preventDefault();
    planRoutesViaAPI();
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    planRoutesViaAPI();
  });

  // Initialize instructions
  updateMapInstructions();
});

