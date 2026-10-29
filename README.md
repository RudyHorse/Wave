# Wave

Local seismic processing and QC app for SEG-Y data: load, sort, process, stack and export.

## About

Wave is a lightweight, local-first seismic processing workbench for SEG-Y gathers and lines. It grew out of a simple viewer and now covers the common land-processing chain: importing data from disk (DSIN) or upload, sorting and cropping by header keys, amplitude and frequency processing (AGC, bandpass, deconvolution, phase and gain corrections), ground-roll and noise suppression (LFAF family, f-k filtering, envelope and median-based suppressors), velocity picking with semblance, NMO correction and CMP stacking with fold control, and exporting back to SEG-Y (DSOUT) or the built-in SQLite database.

Everything runs on your machine — the FastAPI backend stores datasets and velocity files in a local SQLite database, the React/Plotly frontend provides heatmap/wiggle visualization, sort views and inline analysis (spectrum, FX, autocorrelation, signal/noise), and a standalone `sgy_cutter.html` file allows cutting SEG-Y volumes without starting the app at all.

Wave is an independent implementation and does not claim bit-for-bit compatibility with any commercial seismic package. Vendor-derived algorithms included here (LFAFN, SUPPRES, AMPSCAL) are manual-based independent implementations, included with their respective licenses.

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
