"use client";

import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { Fragment, useEffect, useMemo, useRef } from "react";
import { MapContainer, Marker, Polyline, Popup, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { environmentalDataLabel } from "@/lib/dataProvenance";
import { RISK_LABELS, riskColor } from "@/lib/riskPalette";
import { waveColor } from "@/lib/wavePalette";
import type { City, RouteCandidate } from "@/lib/types";

const MODE_LABELS: Record<string, string> = {
  darat: "Darat",
  laut: "Laut",
  kombinasi: "Kombinasi (Darat + Laut)",
};

function makeDivIcon(html: string, size: number) {
  return L.divIcon({ html, className: "", iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
}

const pinIcon = (label: string, highlight: boolean) =>
  makeDivIcon(
    `<div style="background:${highlight ? "#00668a" : "#0032a0"};color:#fff;border-radius:9999px;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;border:2px solid #fff;box-shadow:0 2px 6px rgba(15,23,42,0.22);cursor:grab">${label}</div>`,
    26
  );

const portIcon = makeDivIcon(
  '<div style="background:#3556c1;border-radius:9999px;width:14px;height:14px;border:2px solid #fff;box-shadow:0 1px 2px rgba(15,23,42,0.35)"></div>',
  14
);

const hotspotIcon = makeDivIcon(
  '<div style="background:#ba1a1a;color:#fff;border-radius:9999px;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;border:2px solid #fff;box-shadow:0 1px 3px rgba(15,23,42,0.4)">!</div>',
  22
);

function FitBounds({ origin, destination, routes }: { origin: City; destination: City; routes: RouteCandidate[] }) {
  const map = useMap();
  const didInitialFit = useRef(false);
  const prevRouteKey = useRef("");

  useEffect(() => {
    if (!didInitialFit.current) {
      map.fitBounds(
        [
          [origin.lat, origin.lon],
          [destination.lat, destination.lon],
        ],
        { padding: [60, 60] }
      );
      didInitialFit.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const key = routes.map((r) => r.route_id).join(",");
    if (routes.length > 0 && key !== prevRouteKey.current) {
      const pts: [number, number][] = [
        [origin.lat, origin.lon],
        [destination.lat, destination.lon],
      ];
      for (const r of routes) pts.push(...r.geometry);
      map.fitBounds(pts, { padding: [40, 40] });
      prevRouteKey.current = key;
    }
  }, [routes, origin, destination, map]);

  return null;
}

function ClickToPlace({
  pickMode,
  onOriginChange,
  onDestinationChange,
}: {
  pickMode: "origin" | "destination" | null;
  onOriginChange: (lat: number, lon: number) => void;
  onDestinationChange: (lat: number, lon: number) => void;
}) {
  useMapEvents({
    click(e) {
      if (pickMode === "origin") onOriginChange(e.latlng.lat, e.latlng.lng);
      else if (pickMode === "destination") onDestinationChange(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function MapReady({ onReady }: { onReady?: () => void }) {
  const map = useMap();

  useEffect(() => {
    map.whenReady(() => onReady?.());
  }, [map, onReady]);

  return null;
}

function nearestGeometryIndex(geometry: [number, number][], point: { lat: number; lon: number }): number {
  return geometry.reduce(
    (nearestIndex, coordinate, index) => {
      const [nearestLat, nearestLon] = geometry[nearestIndex];
      const nearestDistance = (nearestLat - point.lat) ** 2 + (nearestLon - point.lon) ** 2;
      const distance = (coordinate[0] - point.lat) ** 2 + (coordinate[1] - point.lon) ** 2;
      return distance < nearestDistance ? index : nearestIndex;
    },
    0,
  );
}

function waveGeometry(route: RouteCandidate): [number, number][] {
  if (route.transport_mode === "darat") return [];
  if (!route.port_pair) return route.geometry;

  const start = nearestGeometryIndex(route.geometry, route.port_pair.embark);
  const end = nearestGeometryIndex(route.geometry, route.port_pair.disembark);
  return route.geometry.slice(Math.min(start, end), Math.max(start, end) + 1);
}

function RouteDetailsPopup({ route, color, isRecommended }: { route: RouteCandidate; color: string; isRecommended: boolean }) {
  return (
    <Popup>
      <div style={{ fontSize: 13, lineHeight: 1.5 }}>
        <strong>{MODE_LABELS[route.transport_mode] ?? route.transport_mode}</strong>
        {isRecommended && <span style={{ color: "#0ca30c" }}> (Direkomendasikan)</span>}
        <br />
        Jarak: {route.distance_km.toFixed(0)} km &middot; Estimasi: {route.estimated_duration_hours.toFixed(1)} jam
        <br />
        Risiko: <strong style={{ color }}>{RISK_LABELS[route.risk_level] ?? route.risk_level}</strong> (skor {" "}
        {(route.risk_probability * 100).toFixed(0)}%)
        <br />
        Gelombang: {route.wave_category} ({route.wave_height_m.toFixed(2)} m) &middot; Cuaca: {route.weather_condition}
        <br />
        Angin: {route.wind_speed_kmh.toFixed(0)} km/j
        <br />
        Sumber lingkungan: {environmentalDataLabel(route)}
        {route.port_pair && <><br />Suhu pelabuhan: {route.port_ambient_temp_c.toFixed(1)}&deg;C</>}
        {route.trigger_reason && <><br /><span style={{ color: "#d03b3b" }}>Peringatan: {route.trigger_reason}</span></>}
        {route.data_quality === "estimated" && <><br /><em>Sebagian jarak/waktu bersifat estimasi (data ORS tidak tersedia/valid).</em></>}
        <br />
        <em>{route.risk_explanation_summary}</em>
      </div>
    </Popup>
  );
}

interface RouteMapProps {
  origin: City;
  destination: City;
  onOriginChange: (lat: number, lon: number) => void;
  onDestinationChange: (lat: number, lon: number) => void;
  pickMode: "origin" | "destination" | null;
  routes?: RouteCandidate[];
  recommendedRouteId?: string;
  selectedRouteId?: string;
  onSelectRoute?: (routeId: string) => void;
  onReady?: () => void;
}

export default function RouteMap({
  origin,
  destination,
  onOriginChange,
  onDestinationChange,
  pickMode,
  routes = [],
  recommendedRouteId,
  selectedRouteId,
  onSelectRoute,
  onReady,
}: RouteMapProps) {
  // Render order matters for map z-index -- draw the selected route last so
  // its halo/line sits on top of every other overlapping route.
  const orderedRoutes = useMemo(
    () => [...routes].sort((a, b) => (a.route_id === selectedRouteId ? 1 : b.route_id === selectedRouteId ? -1 : 0)),
    [routes, selectedRouteId]
  );

  return (
    <MapContainer
      center={[origin.lat, origin.lon]}
      zoom={6}
      scrollWheelZoom
      style={{ height: "100%", width: "100%", cursor: pickMode ? "crosshair" : undefined }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitBounds origin={origin} destination={destination} routes={routes} />
      <MapReady onReady={onReady} />
      <ClickToPlace pickMode={pickMode} onOriginChange={onOriginChange} onDestinationChange={onDestinationChange} />

      {orderedRoutes.map((route) => {
        const isRecommended = route.route_id === recommendedRouteId;
        const isSelected = route.route_id === selectedRouteId;
        const color = riskColor(route.risk_level);
        const seaGeometry = waveGeometry(route);
        const hasSeaLeg = seaGeometry.length > 1;
        const clickHandler = onSelectRoute ? { click: () => onSelectRoute(route.route_id) } : undefined;

        return (
          <Fragment key={route.route_id}>
            {isSelected && (
              <Polyline
                positions={route.geometry}
                pathOptions={{ color: "#0032a0", weight: 9, opacity: 0.2, lineCap: "round", lineJoin: "round" }}
                eventHandlers={clickHandler}
              />
            )}
            <Polyline
              positions={route.geometry}
              pathOptions={{
                color,
                weight: hasSeaLeg ? 2 : isSelected ? 5 : 3,
                opacity: hasSeaLeg ? 0.55 : selectedRouteId ? (isSelected ? 1 : 0.45) : 0.8,
                dashArray: route.data_quality === "estimated" ? "6 6" : undefined,
              }}
              eventHandlers={clickHandler}
            >
              <Tooltip sticky>
                {MODE_LABELS[route.transport_mode] ?? route.transport_mode} -- {RISK_LABELS[route.risk_level] ?? route.risk_level}
                {isRecommended ? " (Direkomendasikan)" : ""}
              </Tooltip>
              <RouteDetailsPopup route={route} color={color} isRecommended={isRecommended} />
            </Polyline>
            {hasSeaLeg && (
              <Polyline
                positions={seaGeometry}
                pathOptions={{
                  color: waveColor(route.wave_height_m),
                  weight: isSelected ? 9 : 7,
                  opacity: selectedRouteId ? (isSelected ? 1 : 0.86) : 0.92,
                  lineCap: "round",
                  lineJoin: "round",
                }}
                eventHandlers={clickHandler}
              >
                <Tooltip sticky>
                  Rute laut -- {route.wave_category} ({route.wave_height_m.toFixed(2)} m)
                </Tooltip>
                <RouteDetailsPopup route={route} color={color} isRecommended={isRecommended} />
              </Polyline>
            )}
          </Fragment>
        );
      })}

      <Marker
        position={[origin.lat, origin.lon]}
        icon={pinIcon("A", pickMode === "origin")}
        draggable
        eventHandlers={{
          dragend: (e) => {
            const { lat, lng } = e.target.getLatLng();
            onOriginChange(lat, lng);
          },
        }}
      >
        <Popup>Asal: {origin.label}</Popup>
      </Marker>
      <Marker
        position={[destination.lat, destination.lon]}
        icon={pinIcon("B", pickMode === "destination")}
        draggable
        eventHandlers={{
          dragend: (e) => {
            const { lat, lng } = e.target.getLatLng();
            onDestinationChange(lat, lng);
          },
        }}
      >
        <Popup>Tujuan: {destination.label}</Popup>
      </Marker>

      {routes.map((route) =>
        route.port_pair ? (
          <Fragment key={`ports-${route.route_id}`}>
            <Marker position={[route.port_pair.embark.lat, route.port_pair.embark.lon]} icon={portIcon}>
              <Popup>Pelabuhan muat: {route.port_pair.embark.port_name}</Popup>
            </Marker>
            <Marker position={[route.port_pair.disembark.lat, route.port_pair.disembark.lon]} icon={portIcon}>
              <Popup>Pelabuhan bongkar: {route.port_pair.disembark.port_name}</Popup>
            </Marker>
          </Fragment>
        ) : null
      )}

      {routes.map((route) =>
        route.risk_hotspot ? (
          <Marker key={`hotspot-${route.route_id}`} position={[route.risk_hotspot.lat, route.risk_hotspot.lon]} icon={hotspotIcon}>
            <Popup>
              <div style={{ fontSize: 13, lineHeight: 1.5 }}>
                <strong>Titik risiko -- {MODE_LABELS[route.transport_mode] ?? route.transport_mode}</strong>
                <br />
                Gelombang {route.wave_category} ({route.wave_height_m.toFixed(2)} m), {route.weather_condition}
                <br />
                Angin {route.wind_speed_kmh.toFixed(0)} km/j
              </div>
            </Popup>
          </Marker>
        ) : null
      )}
    </MapContainer>
  );
}
