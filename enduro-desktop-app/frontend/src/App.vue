<template>
  <div class="app">
    <header>
      <h1>🏍️ EnduroData</h1>
      <div class="header-actions">
        <span v-if="fileName" class="filename">{{ fileName }}</span>
        <label class="btn">
          Abrir GPX...
          <input type="file" accept=".gpx" @change="onFileChange" hidden>
        </label>
      </div>
    </header>

    <section v-if="stats" class="stats">
      <div class="stat"><b>{{ (stats.total_dist_m / 1000).toFixed(1) }} km</b><span>Distancia</span></div>
      <div class="stat"><b>{{ formattedTime }}</b><span>Duración</span></div>
      <div class="stat"><b>{{ Math.round(stats.elev_gain_m) }} m</b><span>Desnivel +</span></div>
      <div class="stat"><b>{{ stats.avg_speed_kmh.toFixed(1) }} km/h</b><span>Vel. media</span></div>
      <div class="stat"><b>{{ stats.max_speed_kmh.toFixed(0) }} km/h</b><span>Vel. máxima</span></div>
      <div class="stat"><b>{{ stats.tech_pct.toFixed(0) }}%</b><span>% técnico</span></div>
    </section>

    <section class="body">
      <div class="map-panel">
        <div class="layer-switcher">
          <button
            v-for="layer in mapLayers"
            :key="layer.id"
            :class="{ active: activeLayer === layer.id }"
            @click="setLayer(layer.id)"
          >{{ layer.label }}</button>
        </div>
        <div id="map"></div>
      </div>

      <div class="zones-panel">
        <h2>Tramos técnicos</h2>
        <p v-if="!zones.length" class="empty">Carga una ruta para empezar</p>
        <div v-for="(z, i) in sortedZones" :key="i" class="zone" @click="panToZone(z)">
          <b>Tramo técnico {{ i + 1 }}</b>
          <span>{{ z.dist.toFixed(0) }} m · vel. media {{ z.avg_speed.toFixed(1) }} km/h</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import L from 'leaflet'

const BACKEND_URL = 'http://127.0.0.1:8731'

const fileName = ref('')
const stats = ref(null)
const zones = ref([])
const points = ref([])

let map, routeLine, techLines = [], zoneLatLngs = []

// --- Capas de mapa disponibles (gratuitas, sin API key) ---
const mapLayers = [
  { id: 'street', label: 'Calle', leaflet: () => L.tileLayer(
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      { maxZoom: 19, attribution: '© OpenStreetMap' }) },
  { id: 'topo', label: 'Topográfico', leaflet: () => L.tileLayer(
      'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
      { maxZoom: 17, attribution: '© OpenTopoMap' }) },
  { id: 'satellite', label: 'Satélite', leaflet: () => L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 19, attribution: 'Tiles © Esri' }) },
]
const activeLayer = ref('topo') // el topográfico suele ser el más útil para enduro
let currentTileLayer = null

onMounted(() => {
  map = L.map('map').setView([43.46, -3.81], 12) // vista inicial: Cantabria
  currentTileLayer = mapLayers.find(l => l.id === activeLayer.value).leaflet().addTo(map)
})

function setLayer(id) {
  activeLayer.value = id
  map.removeLayer(currentTileLayer)
  currentTileLayer = mapLayers.find(l => l.id === id).leaflet().addTo(map)
}

const sortedZones = computed(() => [...zones.value].sort((a, b) => b.dist - a.dist))

const formattedTime = computed(() => {
  if (!stats.value?.total_time_s) return '—'
  const totalMin = Math.round(stats.value.total_time_s / 60)
  const h = Math.floor(totalMin / 60), m = totalMin % 60
  return h > 0 ? `${h}h ${m}m` : `${m} min`
})

async function onFileChange(e) {
  const file = e.target.files[0]
  if (!file) return
  fileName.value = file.name

  const form = new FormData()
  form.append('file', file)

  try {
    const res = await fetch(`${BACKEND_URL}/analyze`, { method: 'POST', body: form })
    if (!res.ok) throw new Error((await res.json()).detail || 'Error del backend')
    const data = await res.json()
    stats.value = data.stats
    zones.value = data.zones
    points.value = data.points
    drawRoute()
  } catch (err) {
    alert('No se pudo analizar el GPX: ' + err.message)
  }
}

function drawRoute() {
  if (routeLine) map.removeLayer(routeLine)
  techLines.forEach(l => map.removeLayer(l))
  techLines = []

  const latlngs = points.value.map(p => [p.lat, p.lon])
  routeLine = L.polyline(latlngs, { color: '#3a86ff', weight: 4, opacity: 0.8 }).addTo(map)
  map.fitBounds(routeLine.getBounds(), { padding: [30, 30] })

  zoneLatLngs = zones.value.map(z => {
    const segPts = points.value.slice(z.start_idx, z.end_idx + 2).map(p => [p.lat, p.lon])
    const line = L.polyline(segPts, { color: '#e74c3c', weight: 6, opacity: 0.95 }).addTo(map)
    techLines.push(line)
    return segPts[0]
  })
}

function panToZone(z) {
  const idx = zones.value.indexOf(z)
  if (zoneLatLngs[idx]) map.panTo(zoneLatLngs[idx])
}
</script>
