"""
server.py — Backend local para EnduroData Desktop.

Este servidor lo lanza Electron como proceso hijo al arrancar la app.
Escucha solo en localhost, no está pensado para exponerse a internet.
"""
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from analysis import analyze_route

app = FastAPI(title="EnduroData Backend")

# Electron/Vue corren en otro puerto (Vite en dev, file:// en producción),
# así que hace falta CORS para que el fetch() del frontend funcione.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # backend solo escucha en localhost, no hay riesgo real
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Electron usa esto para saber cuándo el backend ya está listo."""
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".gpx"):
        raise HTTPException(400, "El archivo debe ser un .gpx")

    with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        a = analyze_route(tmp_path)
    except Exception as exc:
        raise HTTPException(400, f"No se pudo analizar el GPX: {exc}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {
        "points": [{"lat": p.lat, "lon": p.lon, "ele": p.ele} for p in a.points],
        "zones": [
            {
                "start_idx": z.start_idx,
                "end_idx": z.end_idx,
                "dist": z.dist,
                "avg_speed": z.avg_speed,
            }
            for z in a.zones
        ],
        "stats": {
            "total_dist_m": a.total_dist_m,
            "total_time_s": a.total_time_s,
            "elev_gain_m": a.elev_gain_m,
            "avg_speed_kmh": a.avg_speed_kmh,
            "max_speed_kmh": a.max_speed_kmh,
            "tech_pct": a.tech_pct,
        },
    }


if __name__ == "__main__":
    import uvicorn
    # puerto fijo para que Electron sepa siempre dónde encontrarlo
    uvicorn.run(app, host="127.0.0.1", port=8731)
