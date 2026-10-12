"""Bounded previews and a single-process, disk-backed CMP job service."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import threading
import uuid
import numpy as np
from .datasets import DatasetStore,safe_path
from .gathers import GatherSelection
from .repository import Repository,canonical_json,utcnow,ConflictError
from .schemas import RunRequest,Selection,NMOParams
from .velocity import VelocityModel
from .nmo import apply_nmo
from .semblance import scan_semblance
from .registry import GatherState,run_gather
from .segy import write_segy

class JobCancelled(Exception):
    pass

class CMPService:
    MAX_PREVIEW_TRACES=512
    MAX_SPECTRUM_SAMPLES=4096
    MAX_SPECTRUM_WORK=120_000_000  # velocities * traces * native time samples
    MAX_GATHER_BYTES=512*1024*1024

    def __init__(self,db_path,storage_root):
        self.repo=Repository(db_path)
        self.datasets=DatasetStore(self.repo,storage_root)
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='wave-cmp')
        self._lock=threading.RLock()
        self._preview_lock=threading.BoundedSemaphore(1)
        self._futures={}
        self._closed=False

    def startup(self):
        self.repo.recover_interrupted()

    def close(self):
        self._closed=True
        with self._lock:
            pending=list(self._futures)
        for job_id in pending:
            self.repo.cancel(job_id)
        self.executor.shutdown(wait=True,cancel_futures=False)

    @staticmethod
    def _check_geometry(ds,geometry):
        known=ds.output_info['metadata'].get('geometry') if ds.output_info else None
        if known is not None and geometry.model_dump()!=known:
            raise ValueError('Geometry differs from the recorded geometry of this processed dataset')

    @staticmethod
    def _check_header_time(ds,indices,geometry):
        headers=ds.trace_headers(indices)
        if headers is None:
            return
        def values(start,dtype):
            return np.frombuffer(headers[:,start:start+2].copy().tobytes(),dtype=dtype)
        delay=values(108,'>i2')
        if np.any(np.abs(delay-geometry.start_time_ms)>1e-6):
            raise ValueError('SEG-Y recording delay differs from start_time_ms, or delays vary between traces; regularize input first')
        samples=values(114,'>u2');dt=values(116,'>u2')
        if np.any((samples!=0)&(samples!=ds.data.shape[1])) or np.any((dt!=0)&(np.abs(dt-ds.dt_ms*1000)>1e-6)):
            raise ValueError('SEG-Y trace sample count/interval differs from Wave arrays; regularize input before CMP processing')

    def _select(self,ds,selection):
        self._check_geometry(ds,selection.geometry)
        sel=ds.index.select(selection.inline,selection.cdp,selection.supergather_size,
            selection.geometry.offset_factor,selection.min_offset_m,selection.max_offset_m)
        if len(sel.indices)==0:
            raise ValueError('No traces in the requested offset aperture')
        self._check_header_time(ds,sel.indices,selection.geometry)
        return sel

    def _preview_selection(self,ds,selection):
        sel=self._select(ds,selection)
        if len(sel.indices)>self.MAX_PREVIEW_TRACES:
            raise ValueError('Preview exceeds 512 traces; reduce supergather/aperture. No traces were silently dropped')
        if len(sel.indices)*ds.data.shape[1]*32>self.MAX_GATHER_BYTES:
            raise ValueError('Gather exceeds preview memory limit')
        return sel

    @staticmethod
    def _display(data,offsets,times_ms,max_traces=512,max_samples=1600):
        ts=max(1,math.ceil(data.shape[0]/max_traces))
        ss=max(1,math.ceil(data.shape[1]/max_samples))
        a=np.nan_to_num(data[::ts,::ss],nan=0,posinf=0,neginf=0)
        return {'data':a.T.tolist(),'offsets_m':np.asarray(offsets)[::ts].tolist(),
                'times_ms':np.asarray(times_ms)[::ss].tolist(),
                'display_trace_stride':ts,'display_sample_stride':ss}

    def gather(self,dataset_id,selection):
        ds=self.datasets.open(dataset_id)
        sel=self._preview_selection(ds,selection)
        data,w=ds.read(sel.indices)
        offsets=ds.offsets[sel.indices]*selection.geometry.offset_factor
        times=selection.geometry.start_time_ms+np.arange(data.shape[1])*ds.dt_ms
        return {**self._display(data*w,offsets,times),'members':sel.members,'actual_trace_count':len(sel.indices)}

    def spectrum(self,dataset_id,request):
        if not self._preview_lock.acquire(blocking=False):
            raise ConflictError('Another spectrum/preview is being calculated; retry after completion')
        try:
            ds=self.datasets.open(dataset_id)
            if ds.kind in ('nmo','stack'):
                raise ValueError('Velocity analysis requires prestack data before NMO')
            sel=self._preview_selection(ds,request.selection)
            velocities=np.arange(request.velocity_min,request.velocity_max+request.velocity_step*1e-8,request.velocity_step)
            ns=ds.data.shape[1]
            if len(velocities)*len(sel.indices)*ns>self.MAX_SPECTRUM_WORK:
                raise ValueError('Spectrum work budget exceeded; reduce supergather or velocity range / increase velocity_step')
            times=request.selection.geometry.start_time_ms+np.arange(ns)*ds.dt_ms
            high=times[-1] if request.time_max_ms is None else request.time_max_ms
            keep=np.flatnonzero((times>=request.time_min_ms)&(times<=high))[::request.time_stride]
            if len(keep)==0 or len(keep)>self.MAX_SPECTRUM_SAMPLES:
                raise ValueError('Select 1..4096 spectrum time samples using range/time_stride')
            data,w=ds.read(sel.indices)
            offsets=ds.offsets[sel.indices]*request.selection.geometry.offset_factor
            spectrum=scan_semblance(data,offsets,ds.dt_ms/1000,velocities,window_ms=request.window_ms,
                min_fold=request.min_fold,start_time_s=request.selection.geometry.start_time_ms/1000,
                input_weights=w,nmo_params=request.nmo,time_indices=keep)
            return {'times_ms':times[keep].tolist(),'velocities_mps':velocities.tolist(),
                    'semblance':spectrum.tolist(),'members':sel.members,'actual_trace_count':len(sel.indices),
                    'gather':self._display(data*w,offsets,times)}
        finally:
            self._preview_lock.release()

    def _model(self,ds,doc,geometry):
        if doc.source_fingerprint!=ds.velocity_fingerprint:
            raise ConflictError('Velocity file does not match this dataset fingerprint')
        if ds.kind=='prestack' and doc.source_file_id!=ds.id:
            raise ConflictError('Velocity file belongs to another dataset')
        if doc.geometry!=geometry:
            raise ValueError('Velocity picking geometry and NMO geometry must be identical')
        return VelocityModel(doc)

    def preview(self,dataset_id,request):
        if not self._preview_lock.acquire(blocking=False):
            raise ConflictError('Another spectrum/preview is being calculated')
        try:
            ds=self.datasets.open(dataset_id)
            if ds.kind in ('nmo','stack'):
                raise ValueError('NMO preview expects uncorrected prestack input')
            sel=self._preview_selection(ds,request.selection)
            if request.selection.supergather_size!=1:
                raise ValueError('NMO QC must use one CMP, not a mixed supergather')
            doc=request.document or self.repo.load_velocity(request.velocity_file_id)
            model=self._model(ds,doc,request.selection.geometry)
            data,w=ds.read(sel.indices)
            offsets=ds.offsets[sel.indices]*request.selection.geometry.offset_factor
            times=request.selection.geometry.start_time_ms+np.arange(data.shape[1])*ds.dt_ms
            vel,dv=model.evaluate(request.selection.inline,request.selection.cdp,times/1000)
            corrected=apply_nmo(data,offsets,ds.dt_ms/1000,vel,request.nmo,
                start_time_s=request.selection.geometry.start_time_ms/1000,input_weights=w,velocity_derivative=dv)
            return {'before':self._display(data*w,offsets,times),
                    'after':self._display(corrected.display(),offsets,times),
                    'fold':np.count_nonzero(corrected.weights>0,axis=0).tolist(),'times_ms':times.tolist()}
        finally:
            self._preview_lock.release()

    def save_velocity(self,request):
        ds=self.datasets.open(request.document.source_file_id)
        if ds.kind!='prestack':
            raise ValueError('Pick velocities on prestack data before NMO')
        self._model(ds,request.document,request.document.geometry)
        for f in request.document.functions:
            if (f.inline,f.cdp) not in ds.index.ranges:
                raise ValueError(f'No CMP ({f.inline},{f.cdp}) in source dataset')
        return self.repo.save_velocity(request.document,request.parent_id)

    def _plan(self,ds,request):
        self._check_geometry(ds,request.geometry)
        names=[s.type for s in request.steps]
        if ds.kind=='stack' and any(s in ('nmo','stack') for s in names):
            raise ValueError('Cannot NMO/STACK a stacked section')
        if ds.kind=='nmo' and any(s!='stack' for s in names):
            raise ValueError('An NMO output can only be stacked here; do not apply NMO twice')
        aligned=ds.kind=='nmo' or request.input_already_nmo
        if aligned and 'nmo' in names:
            raise ValueError('Input is already NMO corrected')
        if 'stack' in names and 'nmo' not in names and not aligned:
            raise ValueError('STACK requires NMO or explicit input_already_nmo=true')
        keys=ds.index.keys(request.inline,request.cdp_min,request.cdp_max)
        plan=[]
        for line,cdp in keys:
            sel=ds.index.select(line,cdp,1,request.geometry.offset_factor,request.min_offset_m,request.max_offset_m)
            if len(sel.indices):
                self._check_header_time(ds,sel.indices,request.geometry)
                if len(sel.indices)*ds.data.shape[1]*64>self.MAX_GATHER_BYTES:
                    raise ValueError('A CMP exceeds the 512 MiB gather work budget; reduce offset aperture')
                if len(np.unique(ds.xline[sel.indices]))>1:
                    raise ValueError(f'Ambiguous CMP ({line},{cdp}): multiple crosslines; fix grouping headers')
                plan.append((line,cdp,len(sel.indices)))
        if not plan:
            raise ValueError('No CMP gathers selected')
        for step in request.steps:
            if step.type=='bandpass' and step.params.highcut>500/ds.dt_ms:
                raise ValueError('Bandpass highcut exceeds Nyquist')
        return plan

    def submit(self,request:RunRequest):
        if self._closed:
            raise ConflictError('Processing service is stopping')
        ds=self.datasets.open(request.dataset_id)
        plan=self._plan(ds,request)
        doc=self.repo.load_velocity(request.velocity_file_id) if request.velocity_file_id else None
        if doc:
            model=self._model(ds,doc,request.geometry)
            times=(request.geometry.start_time_ms+np.arange(ds.data.shape[1])*ds.dt_ms)/1000
            # Check coverage before creating output or accepting a job.
            for line,cdp,_ in plan:
                model.evaluate(line,cdp,times)
        sha=hashlib.sha256(canonical_json(doc.model_dump())).hexdigest() if doc else None
        with self._lock:
            if sum(not f.done() for f in self._futures.values())>=3:
                raise ConflictError('Processing queue is full (one worker, two queued jobs)')
            self._futures={k:v for k,v in self._futures.items() if not v.done()}
            job_id=self.repo.create_job(request.model_dump(mode='json'),sha)
            self._futures[job_id]=self.executor.submit(self._execute,job_id,ds,request,doc,plan)
        return self.repo.job(job_id)

    def _execute(self,job_id,ds,request,doc,plan):
        result_id=str(uuid.uuid4())
        final=safe_path(self.datasets.root,result_id)
        stage=self.datasets.root/('.cmp-'+job_id+'.partial')
        mapped=[]
        published=False
        input_stat=(ds.directory/'data.npy').stat()
        def cancel():
            if self._closed or self.repo.job(job_id)['cancel_requested']:
                raise JobCancelled()
        def make(name,shape,dtype):
            arr=np.lib.format.open_memmap(stage/(name+'.npy'),mode='w+',dtype=dtype,shape=shape)
            mapped.append(arr)
            return arr
        try:
            cancel()
            self.repo.update_job(job_id,status='running')
            stage.mkdir()
            is_stack=request.steps[-1].type=='stack'
            has_nmo=any(s.type=='nmo' for s in request.steps) or ds.kind=='nmo'
            kind='stack' if is_stack else 'nmo' if has_nmo else ds.kind
            nout=len(plan) if is_stack else sum(n for _,_,n in plan)
            ns=ds.data.shape[1]
            output=make('data',(nout,ns),'float32')
            raw=None if is_stack else make('raw',(nout,ns),'float32')
            weights=None if is_stack else make('weights',(nout,ns),'float32')
            fold=make('fold',(nout,ns),'int32') if is_stack else None
            input_fold=make('input_fold',(nout,ns),'int32') if is_stack else None
            weight_sum=make('weight_sum',(nout,ns),'float32') if is_stack else None
            cp=make('cdp',(nout,),'int32');il=make('inline',(nout,),'int32')
            xl=make('xline',(nout,),'int32');off=make('offset',(nout,),'float64')
            hh=make('headers',(nout,240),'uint8') if ds.headers is not None else None
            headers_ok=hh is not None
            model=VelocityModel(doc) if doc else None
            first=0;minimum=np.inf;maximum=-np.inf
            for number,(line,cdp,_) in enumerate(plan):
                cancel()
                sel=ds.index.select(line,cdp,1,request.geometry.offset_factor,request.min_offset_m,request.max_offset_m)
                ids=sel.indices
                data,w=ds.read(ids)
                offsets=ds.offsets[ids]*request.geometry.offset_factor
                state=run_gather(GatherState(data,w,offsets,line,cdp,ds.dt_ms,request.geometry.start_time_ms,
                    model,ds.kind=='nmo' or request.input_already_nmo),request.steps,cancel)
                headers=ds.trace_headers(ids)
                headers_ok &= headers is not None
                if is_stack:
                    stacked=state.stack_result
                    output[first]=stacked.data
                    fold[first]=stacked.fold;input_fold[first]=stacked.input_fold;weight_sum[first]=stacked.weight_sum
                    cp[first]=cdp;il[first]=line;xl[first]=ds.xline[ids[0]];off[first]=0
                    if hh is not None and headers is not None:
                        hh[first]=headers[np.argmin(np.abs(offsets))]
                    visible=stacked.data
                    first+=1
                else:
                    count=len(ids)
                    raw[first:first+count]=state.data
                    weights[first:first+count]=state.weights
                    visible=state.data*state.weights
                    output[first:first+count]=visible
                    cp[first:first+count]=ds.cdp[ids];il[first:first+count]=ds.inline[ids]
                    xl[first:first+count]=ds.xline[ids];off[first:first+count]=offsets
                    if hh is not None and headers is not None:
                        hh[first:first+count]=headers
                    first+=count
                minimum=min(minimum,float(np.min(visible)));maximum=max(maximum,float(np.max(visible)))
                self.repo.update_job(job_id,progress=(number+1)/len(plan)*0.95)
            cancel()
            stat_now=(ds.directory/'data.npy').stat()
            if (input_stat.st_size,input_stat.st_mtime_ns)!=(stat_now.st_size,stat_now.st_mtime_ns):
                raise ConflictError('Input changed during processing; result discarded')
            # Minimal compatibility headers for Wave's existing database viewer.
            np.save(stage/'ffid.npy',np.zeros(nout,dtype=np.int32))
            np.save(stage/'chan.npy',np.ones(nout,dtype=np.int32))
            metadata={'schema_version':1,'source_fingerprint':ds.fingerprint,
                'request':request.model_dump(mode='json'),'geometry':{'offset_units':'m','offset_convention':'full',
                'start_time_ms':request.geometry.start_time_ms},'measurement_system':ds.measurement_system,
                'headers_preserved':bool(headers_ok),'sample_weights':'raw.npy is unweighted; data.npy is display/export',
                'velocity_sha256':self.repo.job(job_id)['velocity_sha256'],'source_kind':ds.kind,
                'selected_gathers':len(plan),'created_at':utcnow()}
            (stage/'manifest.json').write_bytes(canonical_json(metadata))
            values={'id':result_id,'name':request.output_name,'file_path':'','file_size':sum(p.stat().st_size for p in stage.iterdir()),
                    'trace_count':nout,'samples_per_trace':ns,'sample_rate':ds.dt_ms,'min_amplitude':minimum,'max_amplitude':maximum,
                    'is_processed':1,'source_file_id':ds.id,'processing_desc':json.dumps([s.model_dump() for s in request.steps]),
                    'created_at':utcnow(),'file_hash':None,'shot_min':0,'shot_max':0,'ffid_min':0,'ffid_max':0,'chan_min':1,'chan_max':1}
            for prefix,arr in [('cdp',cp),('offset',off),('inline',il),('xline',xl)]:
                values[prefix+'_min']=int(np.floor(arr.min()));values[prefix+'_max']=int(np.ceil(arr.max()))
            for arr in mapped:
                arr.flush()
                arr._mmap.close()
            mapped.clear()
            if hh is not None and not headers_ok:
                (stage/'headers.npy').unlink()
            os.replace(stage,final)
            with self.repo.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT cancel_requested FROM wave_cmp_jobs WHERE id=?',(job_id,)).fetchone()
                if row['cancel_requested']:
                    raise JobCancelled()
                columns={r['name'] for r in db.execute('PRAGMA table_info(files)').fetchall()}
                values={k:v for k,v in values.items() if k in columns}
                db.execute('INSERT INTO files ('+','.join(values)+') VALUES ('+','.join('?' for _ in values)+')',tuple(values.values()))
                db.execute('INSERT INTO wave_cmp_outputs VALUES (?,?,?,?,?,?,?)',
                    (result_id,job_id,ds.id,ds.velocity_fingerprint,kind,canonical_json(metadata).decode(),utcnow()))
                db.execute("UPDATE wave_cmp_jobs SET status='succeeded',progress=1,result_id=?,updated_at=? WHERE id=?",(result_id,utcnow(),job_id))
            published=True
        except JobCancelled:
            self.repo.update_job(job_id,status='cancelled',error='Cancelled; no output dataset published')
        except Exception as exc:
            self.repo.update_job(job_id,status='failed',error=f'{type(exc).__name__}: {exc}')
        finally:
            for arr in mapped:
                try:
                    arr._mmap.close()
                except Exception:
                    pass
            shutil.rmtree(stage,ignore_errors=True)
            if not published:
                shutil.rmtree(final,ignore_errors=True)

    def section(self,dataset_id,inline=None,kind='amplitude',max_traces=1000,max_samples=1600):
        ds=self.datasets.open(dataset_id)
        if ds.kind!='stack':
            raise ValueError('Section QC expects a stack output')
        if kind not in ('amplitude','fold','input_fold','weight_sum'):
            raise ValueError('Invalid QC kind')
        arr=ds.data if kind=='amplitude' else np.load(ds.directory/(kind+'.npy'),mmap_mode='r',allow_pickle=False)
        indices=np.arange(len(arr)) if inline is None else np.flatnonzero(ds.inline==inline)
        if not len(indices):
            raise ValueError('No stack traces on this inline')
        stride=max(1,math.ceil(len(indices)/max_traces))
        ids=indices[::stride]
        ss=max(1,math.ceil(arr.shape[1]/max_samples))
        # Apply sample slice BEFORE fancy trace indexing (do not copy entire section).
        matrix=np.asarray(arr[:,::ss][ids])
        start=ds.output_info['metadata']['geometry']['start_time_ms']
        return {'kind':kind,'data':matrix.T.tolist(),'cdps':ds.cdp[ids].tolist(),
                'inlines':ds.inline[ids].tolist(),'times_ms':(start+np.arange(0,arr.shape[1],ss)*ds.dt_ms).tolist(),
                'display_trace_stride':stride,'display_sample_stride':ss}

    def export(self,dataset_id):
        ds=self.datasets.open(dataset_id)
        if ds.output_info is None:
            raise ValueError('Export endpoint is for CMP outputs; use Wave DSOUT for original data')
        manifest=ds.output_info['metadata']
        path=ds.directory/'output.sgy'
        with self._lock:
            if not path.exists():
                displayed=np.load(ds.directory/'data.npy',mmap_mode='r',allow_pickle=False)
                fold=np.load(ds.directory/'fold.npy',mmap_mode='r',allow_pickle=False) if ds.kind=='stack' else None
                # Output raw-header rows were written in exactly the same order.
                headers=ds.headers if manifest['headers_preserved'] else None
                write_segy(path,displayed,ds.dt_ms,ds.cdp,ds.inline,ds.xline,ds.offsets,
                    start_time_ms=manifest['geometry']['start_time_ms'],fold=fold,headers=headers,
                    stack=ds.kind=='stack',measurement_system=ds.measurement_system,
                    provenance='VELOCITY SHA256 '+str(manifest.get('velocity_sha256','none')))
        return path
