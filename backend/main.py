from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Any, Dict, List
import os
import uuid
import tempfile

from sgy_handler import sgy_handler, CancelledError
from database import list_files as db_list_files

app = FastAPI(title="SeisViz API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "backend/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class UploadResponse(BaseModel):
    file_id: str
    file_name: str
    status: str


class StatisticsResponse(BaseModel):
    file_name: str
    file_size: int
    trace_count: int
    samples_per_trace: int
    sample_rate: float
    min_amplitude: float
    max_amplitude: float
    ffid_min: int
    ffid_max: int
    shot_min: int
    shot_max: int
    cdp_min: int
    cdp_max: int
    offset_min: int
    offset_max: int
    inline_min: int
    inline_max: int
    xline_min: int
    xline_max: int
    chan_min: int = 0
    chan_max: int = 0


class DeleteResponse(BaseModel):
    status: str


class StepModel(BaseModel):
    type: str
    params: Dict[str, Any]


class SequenceRequest(BaseModel):
    steps: List[StepModel]
    parallel: bool = False
    num_workers: int = 4


class SpectrumRequest(BaseModel):
    trace_start: int
    trace_end: int
    sample_start: int
    sample_end: int
    use_processed: bool = False


@app.get("/")
async def root():
    return {"message": "SeisViz API is running"}


@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    if file.filename is None or not file.filename.lower().endswith(('.sgy', '.segy')):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload a .sgy or .segy file")
    
    try:
        file_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        sgy_handler.load_file(file_path, file.filename)
        
        stored_id = str(len(sgy_handler.files) - 1)
        
        return UploadResponse(
            file_id=stored_id,
            file_name=file.filename,
            status="uploaded"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@app.get("/api/analyze/{file_id}")
async def analyze_file(file_id: str):
    stats = sgy_handler.get_statistics(file_id)
    
    if stats is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    return JSONResponse(content={
        "file_name": stats["file_name"],
        "file_size": stats["file_size"],
        "trace_count": stats["trace_count"],
        "samples_per_trace": stats["samples_per_trace"],
        "sample_rate": stats["sample_rate"],
        "min_amplitude": round(stats["min_amplitude"], 4),
        "max_amplitude": round(stats["max_amplitude"], 4),
        "ffid_min": stats["ffid_min"],
        "ffid_max": stats["ffid_max"],
        "shot_min": stats["shot_min"],
        "shot_max": stats["shot_max"],
        "cdp_min": stats["cdp_min"],
        "cdp_max": stats["cdp_max"],
        "offset_min": stats["offset_min"],
        "offset_max": stats["offset_max"],
        "inline_min": stats["inline_min"],
        "inline_max": stats["inline_max"],
        "xline_min": stats["xline_min"],
        "xline_max": stats["xline_max"],
        "chan_min": stats.get("chan_min", 0),
        "chan_max": stats.get("chan_max", 0),
    })


@app.get("/api/visualize/{file_id}")
async def get_visualization(file_id: str, sort_mode: str = 'none', inline: int = None, crossline: int = None, num_gathers: int = 1):
    viz_data = sgy_handler.get_visualization_data(file_id, sort_mode=sort_mode, inline=inline, crossline=crossline, num_gathers=num_gathers)
    
    if viz_data is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    return JSONResponse(content=viz_data)


@app.get("/api/time-slice/{file_id}")
async def get_time_slice(file_id: str, sample: int):
    ts_data = sgy_handler.get_time_slice(file_id, sample)
    
    if ts_data is None:
        raise HTTPException(status_code=404, detail="Time slice not available")
    
    return JSONResponse(content=ts_data)


@app.post("/api/process/agc/{file_id}")
async def process_agc(file_id: str, window_ms: float = 100.0):
    if window_ms <= 0:
        raise HTTPException(status_code=400, detail="Window length must be positive")

    result = sgy_handler.apply_agc(file_id, window_ms)

    if result is None:
        raise HTTPException(status_code=404, detail="File not found")

    return JSONResponse(content=result)


@app.post("/api/process/bandpass/{file_id}")
async def process_bandpass(file_id: str, lowcut: float = 5.0, lowpass: float = 10.0, highpass: float = 80.0, highcut: float = 100.0):
    if not (0 < lowcut < lowpass < highpass < highcut):
        raise HTTPException(status_code=400, detail="Frequencies must satisfy: 0 < lowcut < lowpass < highpass < highcut")

    result = sgy_handler.apply_bandpass(file_id, lowcut, lowpass, highpass, highcut)

    if result is None:
        raise HTTPException(status_code=404, detail="File not found")

    return JSONResponse(content=result)


@app.post("/api/process/run/{file_id}")
async def process_run(file_id: str, req: SequenceRequest):
    try:
        result = sgy_handler.run_sequence(file_id, [s.model_dump() for s in req.steps], parallel=req.parallel, num_workers=req.num_workers)
    except CancelledError:
        return JSONResponse(content={"status": "cancelled"})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Processing failed: {str(e)}")

    if result is None:
        raise HTTPException(status_code=404, detail="File not found")

    return JSONResponse(content=result)


@app.post("/api/process/cancel/{file_id}")
async def cancel_processing(file_id: str):
    sgy_handler.set_cancel(file_id)
    return JSONResponse(content={"status": "cancelling"})


@app.get("/api/visualize/processed/{file_id}")
async def get_processed_visualization(file_id: str, sort_mode: str = 'none', inline: int = None, crossline: int = None, num_gathers: int = 1):
    viz_data = sgy_handler.get_processed_visualization(file_id, sort_mode=sort_mode, inline=inline, crossline=crossline, num_gathers=num_gathers)

    if viz_data is None:
        raise HTTPException(status_code=404, detail="Processed data not found")

    return JSONResponse(content=viz_data)


@app.post("/api/spectrum/{file_id}")
async def compute_spectrum(file_id: str, req: SpectrumRequest):
    result = sgy_handler.compute_spectrum(
        file_id, req.trace_start, req.trace_end,
        req.sample_start, req.sample_end, req.use_processed
    )

    if result is None:
        raise HTTPException(status_code=404, detail="No data in selected region")

    return JSONResponse(content=result)


@app.post("/api/autocorrelation/{file_id}")
async def compute_autocorrelation(file_id: str, req: SpectrumRequest):
    result = sgy_handler.compute_autocorrelation(
        file_id, req.trace_start, req.trace_end,
        req.sample_start, req.sample_end, req.use_processed
    )

    if result is None:
        raise HTTPException(status_code=404, detail="No data in selected region")

    return JSONResponse(content=result)


@app.post("/api/fx-spectrum/{file_id}")
async def compute_fx_spectrum(file_id: str, req: SpectrumRequest):
    result = sgy_handler.compute_fx_spectrum(
        file_id, req.trace_start, req.trace_end,
        req.sample_start, req.sample_end, req.use_processed
    )

    if result is None:
        raise HTTPException(status_code=404, detail="No data in selected region")

    return JSONResponse(content=result)


@app.post("/api/signal-noise/{file_id}")
async def compute_signal_noise(file_id: str, req: SpectrumRequest):
    result = sgy_handler.compute_signal_noise(
        file_id, req.trace_start, req.trace_end,
        req.sample_start, req.sample_end, req.use_processed
    )

    if result is None:
        raise HTTPException(status_code=404, detail="No data in selected region")

    return JSONResponse(content=result)


@app.post("/api/fk-spectrum/{file_id}")
async def compute_fk_spectrum(file_id: str, req: SpectrumRequest):
    result = sgy_handler.compute_fk_spectrum(
        file_id, req.trace_start, req.trace_end,
        req.sample_start, req.sample_end, req.use_processed
    )

    if result is None:
        raise HTTPException(status_code=404, detail="No data in selected region")

    return JSONResponse(content=result)


@app.get("/api/sort-info/{file_id}")
async def get_sort_info(file_id: str):
    stats = sgy_handler.get_statistics(file_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="File not found")
    f = sgy_handler.files.get(file_id, {})
    has_sort = 'sort_indices' in f
    has_cdp_offset = 'cdp_sort_indices' in f and f['cdp_sort_indices'] is not None
    has_ffid_offset = 'ffid_sort_indices' in f and f['ffid_sort_indices'] is not None
    has_ffid_chan = 'ffid_chan_sort_indices' in f and f['ffid_chan_sort_indices'] is not None
    return JSONResponse(content={
        'has_inline_xline': has_sort,
        'has_crossline_xline': 'xline_sort_indices' in f,
        'has_cdp_offset': has_cdp_offset,
        'has_ffid_offset': has_ffid_offset,
        'has_ffid_chan': has_ffid_chan,
        'chan_min': stats.get('chan_min', 0),
        'chan_max': stats.get('chan_max', 0),
        'inline_min': stats['inline_min'],
        'inline_max': stats['inline_max'],
        'xline_min': stats['xline_min'],
        'xline_max': stats['xline_max'],
    })


@app.get("/api/inline-list/{file_id}")
async def get_inline_list(file_id: str):
    result = sgy_handler.get_inline_list(file_id)
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")
    return JSONResponse(content=result)


@app.get("/api/crossline-list/{file_id}")
async def get_crossline_list(file_id: str):
    result = sgy_handler.get_crossline_list(file_id)
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")
    return JSONResponse(content=result)


@app.get("/api/cdp-list/{file_id}")
async def get_cdp_list(file_id: str):
    result = sgy_handler.get_cdp_list(file_id)
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")
    return JSONResponse(content=result)


@app.get("/api/ffid-list/{file_id}")
async def get_ffid_list(file_id: str):
    result = sgy_handler.get_ffid_list(file_id)
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")
    return JSONResponse(content=result)


@app.get("/api/chan-list/{file_id}")
async def get_chan_list(file_id: str):
    result = sgy_handler.get_chan_list(file_id)
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")
    return JSONResponse(content=result)


@app.get("/api/stored-files")
async def get_stored_files():
    files = sgy_handler.list_stored_files()
    result = []
    for f in files:
        result.append({
            'id': f['id'],
            'name': f['name'],
            'file_size': f['file_size'],
            'trace_count': f['trace_count'],
            'samples_per_trace': f['samples_per_trace'],
            'sample_rate': f['sample_rate'],
            'min_amplitude': f['min_amplitude'],
            'max_amplitude': f['max_amplitude'],
            'ffid_min': f['ffid_min'], 'ffid_max': f['ffid_max'],
            'shot_min': f['shot_min'], 'shot_max': f['shot_max'],
            'cdp_min': f['cdp_min'], 'cdp_max': f['cdp_max'],
            'offset_min': f['offset_min'], 'offset_max': f['offset_max'],
            'inline_min': f['inline_min'], 'inline_max': f['inline_max'],
            'xline_min': f['xline_min'], 'xline_max': f['xline_max'],
            'chan_min': f.get('chan_min', 0), 'chan_max': f.get('chan_max', 0),
            'is_processed': bool(f['is_processed']),
            'source_file_id': f['source_file_id'],
            'processing_desc': f['processing_desc'],
            'created_at': f['created_at'],
            'file_hash': f.get('file_hash', ''),
        })
    return JSONResponse(content=result)


class LoadFromDbRequest(BaseModel):
    file_id: str
    sort_type: Optional[str] = None
    first_min: Optional[float] = None
    first_max: Optional[float] = None
    second_min: Optional[float] = None
    second_max: Optional[float] = None


class DsinRequest(BaseModel):
    path: str
    trace_len: Optional[int] = None
    sample_rate: Optional[float] = None
    sort_type: Optional[str] = None
    first_min: Optional[float] = None
    first_max: Optional[float] = None
    second_min: Optional[float] = None
    second_max: Optional[float] = None


class SaveToDbRequest(BaseModel):
    name: str


@app.post("/api/load-from-db")
async def load_from_db(req: LoadFromDbRequest):
    file_id = sgy_handler.load_from_db(req.file_id)
    if file_id is None:
        raise HTTPException(status_code=404, detail="File not found in storage")
    if req.sort_type:
        try:
            sgy_handler.apply_input_sort(
                file_id,
                req.sort_type,
                first_min=req.first_min,
                first_max=req.first_max,
                second_min=req.second_min,
                second_max=req.second_max,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    stats = sgy_handler.get_statistics(file_id)
    viz_data = sgy_handler.get_visualization_data(file_id)
    return JSONResponse(content={
        'file_id': file_id,
        'file_name': stats['file_name'],
        'statistics': stats,
        'visualization': viz_data,
    })


@app.post("/api/dsin")
async def dsin(req: DsinRequest):
    if not req.path or not req.path.strip():
        raise HTTPException(status_code=400, detail="Path must not be empty")
    if not os.path.exists(req.path):
        raise HTTPException(status_code=400, detail=f"File not found on disk: {req.path}")
    try:
        file_id = sgy_handler.load_file(
            req.path,
            os.path.basename(req.path),
            trace_len=req.trace_len,
            sample_rate=req.sample_rate,
            dedup=False,
            persist=False,
        )
        if req.sort_type:
            sgy_handler.apply_input_sort(
                file_id,
                req.sort_type,
                first_min=req.first_min,
                first_max=req.first_max,
                second_min=req.second_min,
                second_max=req.second_max,
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    stats = sgy_handler.get_statistics(file_id)
    viz_data = sgy_handler.get_visualization_data(file_id)
    return JSONResponse(content={
        'file_id': file_id,
        'file_name': stats['file_name'],
        'statistics': stats,
        'visualization': viz_data,
    })


@app.post("/api/save-to-db/{file_id}")
async def save_to_db(file_id: str, req: SaveToDbRequest):
    new_id = sgy_handler.save_processed_to_db(file_id, req.name)
    if new_id is None:
        raise HTTPException(status_code=404, detail="File not found")
    return JSONResponse(content={'file_id': new_id, 'name': req.name, 'status': 'saved'})


@app.delete("/api/files/{file_id}", response_model=DeleteResponse)
async def delete_file(file_id: str):
    success = sgy_handler.delete_file(file_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    
    return DeleteResponse(status="deleted")