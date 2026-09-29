# EnduroData Desktop

App de escritorio (Windows/Mac/Linux) para analizar rutas GPX de Hard Enduro,
con mapa real (calle / topográfico / satélite) y detección automática de
tramos técnicos.

**Arquitectura:**
- `frontend/` — Vue 3 + Vite + Leaflet (interfaz y mapa)
- `backend/` — Python + FastAPI (todo el análisis de la ruta, reutiliza el
  motor `analysis.py` ya probado)
- `electron/` — el "pegamento": arranca el backend Python como proceso hijo
  y abre la ventana con el frontend Vue

## Requisitos

- Node.js 18+
- Python 3.10+

## Instalación

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..

# Raíz (Electron)
npm install

# Frontend
cd frontend
npm install
cd ..
```

## Ejecutar en desarrollo

Con el entorno virtual de Python **activado**, desde la carpeta raíz:

```bash
npm run dev
```

Esto arranca Vite (frontend) y Electron a la vez, y Electron a su vez lanza
`backend/server.py` como proceso hijo. Si el backend no arranca, revisa la
consola: probablemente el venv de Python no está activado en esa terminal.

## Capas de mapa

Por defecto se abre en topográfico (el más útil para valorar desnivel y
terreno), pero puedes cambiar a calle o satélite con los botones de la
esquina superior derecha del mapa. Los tres proveedores son gratuitos y no
necesitan API key:

- **Calle** — OpenStreetMap
- **Topográfico** — OpenTopoMap
- **Satélite** — Esri World Imagery

Si en algún momento quieres cambiar de proveedor (por ejemplo Mapbox o
MapTiler para más estilos o mejor rendimiento a nivel de zoom alto), solo
hay que tocar el array `mapLayers` en `frontend/src/App.vue` — el resto de
la app no cambia.

## Empaquetar para distribución (`.exe` / `.app` / `.AppImage`)

Esto todavía no está calibrado del todo — falta un paso importante:

```bash
npm run dist
```

Ahora mismo Electron lanza el backend llamando a `python3 server.py`
directamente, lo cual **solo funciona si el ordenador donde se instale la
app también tiene Python 3 instalado**. Para una distribución real a otro
ordenador (por ejemplo, si algún día quieres compartir la app con más
gente del mundo del enduro), lo correcto es "congelar" el backend con
`PyInstaller` en un ejecutable standalone y cambiar `electron/main.js` para
lanzar ese ejecutable en vez de `python3`. Mientras la uses tú en tu propio
ordenador de desarrollo, no hace falta — lo dejo anotado para cuando
llegue el momento de distribuirla.

## Siguiente paso (cuando llegue el hardware)

La detección de tramos técnicos vive en `backend/analysis.py`, función
`_detect_technical_zones`. Cuando tengas el ESP32 con GPS+IMU, esa es la
única función que habrá que sustituir por una versión con fuerzas G reales
— ni el frontend Vue ni el resto del backend necesitan cambios.
