# Wave

Local seismic processing and QC app for SEG-Y data: load, sort, process, stack and export.

## Quick start (Windows)

Double-click `start_app.bat` (or run manually):

```powershell
# backend  -> http://localhost:8010
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8010

# frontend -> http://localhost:5173
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Processing modules

- **Input/Output**: DSIN (load from disk, trace-length and sample-rate control), DSOUT (export SEG-Y), Input sort with two-key ranges, Resample (interval / start / end, zero-padded extension), Output (save to database)
- **Signal**: AGC, Bandpass, FX-Decon, FX-Decon-T, DeconS, PSF, GAIN
- **Noise suppression**: LFAF, LFAF-1, LFAFN (f-k velocity filter), SUPPRES (band-limited envelope suppression), AMPSCAL (lateral amplitude median)
- **Velocity / CMP**: velocity picking with semblance, NMO (stretch mute), CMP STACK (mean/sum/median/trimmed, fold QC), SEG-Y export

## Display

- Heatmap, wiggle and heatmap+wiggle modes
- Sort views: Inline/Xline, CDP/Offset, FFID/Offset, FFID/Chan, time slice
- Time axis in ms, zoom/pan sync, spectrum / FX / autocorrelation / S/N analysis on selection

## Data

- SEG-Y upload and per-project SQLite storage (metadata + velocity files)
- `sgy_cutter.html` — standalone browser tool: cut SEG-Y by first/second header key ranges, time cut and resampling, no server needed

## Stack

FastAPI + NumPy/SciPy/segyio (Python) · React + Vite + Plotly (frontend)
