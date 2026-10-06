# Seismic Data Visualization Web App - Specification

## 1. Project Overview

**Project Name:** SeisViz - Seismic Data Visualization Platform  
**Type:** Web Application  
**Core Functionality:** Load, analyze, and visualize SEG-Y (SGY) seismic data files  
**Target Users:** Geophysicists, seismic data analysts, and oil & gas professionals

## 2. Architecture

- **Backend:** Python with FastAPI
- **Frontend:** React with Vite
- **Connection:** REST API via HTTP

## 3. UI/UX Specification

### Layout Structure
- **Header:** App title and navigation (50px height)
- **Main Content:** Two-column layout
  - Left sidebar (300px): File upload and statistics panel
  - Right area (flex-grow): Visualization canvas
- **Responsive:** Desktop-first (min 1024px width)

### Visual Design

#### Color Palette
- **Background:** `#0a0e14` (deep navy black)
- **Surface:** `#151b24` (dark blue-gray)
- **Surface Elevated:** `#1e2630` (lighter blue-gray)
- **Primary:** `#00d4aa` (teal/cyan accent)
- **Primary Hover:** `#00f5c4`
- **Secondary:** `#ff6b35` (orange accent for warnings/highlights)
- **Text Primary:** `#e6edf3` (off-white)
- **Text Secondary:** `#8b949e` (muted gray)
- **Border:** `#30363d` (subtle gray)
- **Positive:** `#3fb950` (green)
- **Negative:** `#f85149` (red)

#### Typography
- **Font Family:** `"JetBrains Mono", "Fira Code", monospace` for data, `"Inter", sans-serif` for UI
- **Heading (H1):** 24px, weight 600
- **Heading (H2):** 18px, weight 600
- **Body:** 14px, weight 400
- **Data/Stats:** 13px, monospace

#### Spacing System
- **Base unit:** 8px
- **Padding small:** 8px
- **Padding medium:** 16px
- **Padding large:** 24px
- **Gap:** 12px
- **Border radius:** 6px

#### Visual Effects
- **Card shadow:** `0 4px 12px rgba(0, 0, 0, 0.4)`
- **Hover transitions:** 150ms ease-out
- **Button hover:** brightness increase + subtle scale

### Components

#### Header
- App logo/title on left
- Status indicator on right (connected/disconnected)

#### File Upload Panel
- Drag-and-drop zone with dashed border
- File icon and instructional text
- Click to browse button
- Supported format label: ".sgy, .segy"

#### Statistics Panel
- Collapsible card showing:
  - File name
  - File size
  - Number of traces
  - Number of samples per trace
  - Sample rate
  - Min/Max amplitude values
  - Mean amplitude
  - Standard deviation

#### Visualization Canvas
- Full-width seismic image display
- Wiggle trace display option
- Variable area display option
- Color scale legend
- Zoom controls
- Navigation markers

#### Control Buttons
- "Analyze" - analyze uploaded file
- "Visualize" - generate visualization
- "Clear" - reset/clear data

## 4. Functionality Specification

### Core Features

#### File Upload
- Accept SGY files via drag-drop or file picker
- Validate file extension (.sgy, .segy)
- Show upload progress
- Handle upload errors gracefully

#### Statistics Analysis
- Parse SGY file header
- Extract binary header fields
- Calculate trace statistics
- Display formatted results
- Cache results for session

#### Visualization
- Generate seismic image from traces
- Support wiggle trace format
- Auto-scale amplitude
- Apply color mapping
- Interactive zoom/pan

### User Interactions
1. User drags SGY file onto upload zone
2. Backend receives and processes file
3. Statistics panel populates with analysis
4. User clicks "Visualize"
5. Canvas displays seismic image

### API Endpoints

```
POST /api/upload
  - Upload SGY file
  - Response: { file_id, file_name, status }

GET /api/analyze/{file_id}
  - Get statistics for uploaded file
  - Response: { statistics object }

GET /api/visualize/{file_id}
  - Generate visualization data
  - Response: { image_data, dimensions }

DELETE /api/files/{file_id}
  - Remove file from session
  - Response: { status }
```

### Edge Cases
- Invalid file format → Show error message
- Corrupted SGY file → Show warning, partial data if possible
- Very large files (>100MB) → Show processing indicator
- Empty file → Show appropriate message

## 5. Acceptance Criteria

### Visual Checkpoints
- [ ] Dark theme application with specified colors
- [ ] File upload zone visible with dashed border
- [ ] Statistics panel shows formatted numbers
- [ ] Visualization canvas renders seismic data
- [ ] All buttons have hover states

### Functional Checkpoints
- [ ] SGY file uploads successfully
- [ ] Statistics calculated and displayed
- [ ] Visualization generates without errors
- [ ] Error states handled gracefully
- [ ] API endpoints respond correctly

## 6. Tech Stack

### Backend Dependencies
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `python-multipart` - File uploads
- `numpy` - Numerical processing
- `segyio` - SGY file handling

### Frontend Dependencies
- `react` - UI library
- `react-dom` - React DOM
- `vite` - Build tool
- `axios` - HTTP client

## 7. Project Structure

```
seis-app/
├── backend/
│   ├── main.py           # FastAPI application
│   ├── requirements.txt  # Python dependencies
│   └── sgy_handler.py   # SGY file processing
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── FileUpload.jsx
│   │   │   ├── StatisticsPanel.jsx
│   │   │   └── Visualization.jsx
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── SPEC.md
```