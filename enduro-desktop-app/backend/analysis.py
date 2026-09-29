"""
analysis.py
Lógica de análisis de rutas GPX para EnduroData.
Sin dependencias externas: solo stdlib (xml, math, datetime).
"""
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TrackPoint:
    lat: float
    lon: float
    ele: float
    t: float | None  # timestamp unix, puede ser None si el gpx no lo trae


@dataclass
class Segment:
    a: TrackPoint
    b: TrackPoint
    dist: float       # metros
    dt: float         # segundos
    speed: float       # km/h
    grade: float       # pendiente (adimensional)
    bearing: float      # grados 0-360


@dataclass
class TechnicalZone:
    start_idx: int
    end_idx: int
    dist: float
    avg_speed: float


@dataclass
class RouteAnalysis:
    points: list[TrackPoint]
    segments: list[Segment]
    zones: list[TechnicalZone]
    total_dist_m: float
    total_time_s: float | None
    elev_gain_m: float
    avg_speed_kmh: float
    max_speed_kmh: float
    tech_pct: float


GPX_NS = {"gpx": "http://www.topografix.com/GPX/1/1"}


def parse_gpx(path: str) -> list[TrackPoint]:
    """Lee un archivo .gpx y devuelve la lista de puntos de traza."""
    tree = ET.parse(path)
    root = tree.getroot()

    # el namespace puede variar ligeramente entre exportadores (Strava, Wikiloc...)
    # así que buscamos trkpt sea cual sea el namespace exacto
    points: list[TrackPoint] = []
    for trkpt in root.iter():
        if trkpt.tag.endswith("trkpt"):
            lat = float(trkpt.attrib["lat"])
            lon = float(trkpt.attrib["lon"])
            ele = 0.0
            t = None
            for child in trkpt:
                if child.tag.endswith("ele"):
                    ele = float(child.text)
                elif child.tag.endswith("time"):
                    ts = child.text.replace("Z", "+00:00")
                    t = datetime.fromisoformat(ts).timestamp()
            points.append(TrackPoint(lat=lat, lon=lon, ele=ele, t=t))
    return points


def _haversine(a: TrackPoint, b: TrackPoint) -> float:
    """Distancia en metros entre dos puntos GPS."""
    R = 6371000
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dphi = math.radians(b.lat - a.lat)
    dlmb = math.radians(b.lon - a.lon)
    x = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(x), math.sqrt(1 - x))


def _bearing(a: TrackPoint, b: TrackPoint) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dlmb = math.radians(b.lon - a.lon)
    y = math.sin(dlmb) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlmb)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _build_segments(points: list[TrackPoint]) -> list[Segment]:
    segs = []
    for a, b in zip(points, points[1:]):
        dist = _haversine(a, b)
        dt = (b.t - a.t) if (a.t is not None and b.t is not None) else 1.0
        speed = (dist / dt) * 3.6 if dt > 0 else 0.0
        grade = (b.ele - a.ele) / dist if dist > 0 else 0.0
        segs.append(Segment(a, b, dist, dt, speed, grade, _bearing(a, b)))
    return segs


def _detect_technical_zones(
    segs: list[Segment],
    window: int = 8,
    speed_drop_ratio: float = 0.45,
    turn_density_deg: float = 25.0,
    grade_threshold: float = 0.12,
    min_zone_len_m: float = 25.0,
) -> tuple[list[bool], list[TechnicalZone]]:
    """
    Heurística de detección de tramos técnicos SOLO a partir de GPS
    (sin IMU): combina caída de velocidad respecto a la mediana de la
    ruta, densidad de cambios de rumbo (zigzag) y pendiente fuerte.

    Estos umbrales son deliberadamente ajustables: se espera calibrarlos
    con rutas reales de Hard Enduro. Cuando se incorpore el MPU6050/BNO085
    del hardware, esta función se sustituirá por una versión que use
    fuerzas G reales en vez de este proxy.
    """
    if not segs:
        return [], []

    speeds = sorted(s.speed for s in segs)
    median_speed = speeds[len(speeds) // 2] or 1.0

    flags: list[bool] = []
    for i, s in enumerate(segs):
        lo, hi = max(0, i - window), min(len(segs), i + window)
        turn_sum = 0.0
        for j in range(lo + 1, hi):
            diff = abs(segs[j].bearing - segs[j - 1].bearing)
            if diff > 180:
                diff = 360 - diff
            turn_sum += diff
        turn_density = turn_sum / max(hi - lo, 1)

        slow = s.speed < median_speed * speed_drop_ratio and median_speed > 3
        turny = turn_density > turn_density_deg
        steep = abs(s.grade) > grade_threshold

        flags.append((slow and turny) or (slow and steep) or (turny and steep))

    # agrupar segmentos consecutivos marcados en zonas
    zones: list[TechnicalZone] = []
    cur_start = None
    cur_dist = 0.0
    cur_speeds = []
    for i, flag in enumerate(flags):
        if flag:
            if cur_start is None:
                cur_start = i
                cur_dist = 0.0
                cur_speeds = []
            cur_dist += segs[i].dist
            cur_speeds.append(segs[i].speed)
        elif cur_start is not None:
            if cur_dist > min_zone_len_m:
                zones.append(TechnicalZone(cur_start, i - 1, cur_dist, sum(cur_speeds) / len(cur_speeds)))
            cur_start = None
    if cur_start is not None and cur_dist > min_zone_len_m:
        zones.append(TechnicalZone(cur_start, len(segs) - 1, cur_dist, sum(cur_speeds) / len(cur_speeds)))

    return flags, zones


def analyze_route(path: str) -> RouteAnalysis:
    """Punto de entrada principal: dado un path a un .gpx, devuelve el análisis completo."""
    points = parse_gpx(path)
    if len(points) < 2:
        raise ValueError("El archivo GPX no contiene suficientes puntos de traza válidos.")

    segs = _build_segments(points)
    flags, zones = _detect_technical_zones(segs)

    total_dist = sum(s.dist for s in segs)
    elev_gain = sum(max(0.0, b.ele - a.ele) for a, b in zip(points, points[1:]))
    max_speed = max((s.speed for s in segs if s.speed < 200), default=0.0)  # filtra glitches GPS

    if points[0].t is not None and points[-1].t is not None:
        total_time = points[-1].t - points[0].t
        avg_speed = (total_dist / 1000) / (total_time / 3600) if total_time > 0 else 0.0
    else:
        total_time = None
        avg_speed = sum(s.speed for s in segs) / len(segs) if segs else 0.0

    tech_dist = sum(z.dist for z in zones)
    tech_pct = (tech_dist / total_dist * 100) if total_dist > 0 else 0.0

    return RouteAnalysis(
        points=points,
        segments=segs,
        zones=zones,
        total_dist_m=total_dist,
        total_time_s=total_time,
        elev_gain_m=elev_gain,
        avg_speed_kmh=avg_speed,
        max_speed_kmh=max_speed,
        tech_pct=tech_pct,
    )
