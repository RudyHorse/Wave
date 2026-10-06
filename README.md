# SeisViz - Seismic Data Visualization

Web application for visualizing and analyzing SEG-Y seismic data files.

## Quick Start

### 1. Install Backend Dependencies
```powershell
cd backend
pip install -r requirements.txt
```

### 2. Install Frontend Dependencies
```powershell
cd frontend
npm install
```

### 3. Run the Application

**Terminal 1 (Backend):**
```powershell
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 (Frontend):**
```powershell
cd frontend
npm run dev
```

### 4. Open Browser
Navigate to `http://localhost:5173`

## Features

- **File Upload**: Drag & drop or click to upload .sgy/.segy files
- **Statistics Analysis**: View trace count, sample rate, amplitude statistics
- **Visualization**: Render seismic data as a color-coded image

## Project Structure

```
seis/
├── backend/
│   ├── main.py           # FastAPI application
│   ├── sgy_handler.py   # SGY file processing
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
└── SPEC.md
```