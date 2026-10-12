"""Mount these routes in the ORIGINAL Wave FastAPI app via install(app, ...)."""
from functools import wraps
from fastapi import APIRouter,HTTPException,Query
from fastapi.responses import FileResponse,Response
from .schemas import SaveVelocity,Selection,SpectrumRequest,PreviewRequest,RunRequest
from .repository import ConflictError
from .service import CMPService


def guarded(fn):
    @wraps(fn)
    def wrapper(*args,**kwargs):
        try:
            return fn(*args,**kwargs)
        except ConflictError as exc:
            raise HTTPException(409,str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(404,str(exc)) from exc
        except (ValueError,FileNotFoundError) as exc:
            raise HTTPException(400,str(exc)) from exc
    return wrapper


def create_router(service):
    router=APIRouter(prefix='/api/cmp',tags=['CMP / velocity / NMO / stack'])

    @router.get('/datasets')
    @guarded
    def datasets():
        return service.datasets.list()

    @router.get('/datasets/{dataset_id}')
    @guarded
    def dataset(dataset_id:str):
        return service.datasets.open(dataset_id).info()

    @router.get('/datasets/{dataset_id}/cdps')
    @guarded
    def cdps(dataset_id:str,inline:int=0,offset:int=Query(0,ge=0),limit:int=Query(1000,ge=1,le=10000)):
        line=service.datasets.open(dataset_id).index.lines.get(inline,[])
        return {'cdps':line[offset:offset+limit],'total':len(line),'offset':offset}

    @router.post('/datasets/{dataset_id}/gather')
    @guarded
    def gather(dataset_id:str,request:Selection):
        return service.gather(dataset_id,request)

    @router.post('/datasets/{dataset_id}/spectrum')
    @guarded
    def spectrum(dataset_id:str,request:SpectrumRequest):
        return service.spectrum(dataset_id,request)

    @router.post('/datasets/{dataset_id}/nmo-preview')
    @guarded
    def preview(dataset_id:str,request:PreviewRequest):
        return service.preview(dataset_id,request)

    @router.get('/velocity-files')
    @guarded
    def list_velocities(source_file_id:str|None=None):
        return service.repo.list_velocities(source_file_id)

    @router.post('/velocity-files',status_code=201)
    @guarded
    def save_velocity(request:SaveVelocity):
        return service.save_velocity(request)

    @router.get('/velocity-files/{file_id}')
    @guarded
    def velocity(file_id:str):
        return {'file':service.repo.velocity_info(file_id),'document':service.repo.load_velocity(file_id).model_dump()}

    @router.get('/velocity-files/{file_id}/download')
    @guarded
    def download_velocity(file_id:str):
        info=service.repo.velocity_info(file_id)
        return Response(service.repo.velocity_bytes(file_id),media_type='application/json',
                        headers={'Content-Disposition':f'attachment; filename="{info["filename"]}"','ETag':'"'+info['sha256']+'"'})

    @router.post('/jobs',status_code=202)
    @guarded
    def submit(request:RunRequest):
        return service.submit(request)

    @router.get('/jobs/{job_id}')
    @guarded
    def job(job_id:str):
        return service.repo.job(job_id)

    @router.post('/jobs/{job_id}/cancel')
    @guarded
    def cancel(job_id:str):
        return service.repo.cancel(job_id)

    @router.get('/outputs/{dataset_id}/section')
    @guarded
    def section(dataset_id:str,inline:int|None=None,kind:str='amplitude',max_traces:int=Query(1000,ge=1,le=1600),max_samples:int=Query(1600,ge=1,le=2000)):
        return service.section(dataset_id,inline,kind,max_traces,max_samples)

    @router.get('/outputs/{dataset_id}/segy')
    @guarded
    def export(dataset_id:str):
        path=service.export(dataset_id)
        return FileResponse(path,filename=f'wave-{dataset_id}.sgy',media_type='application/octet-stream')

    @router.get('/outputs/{dataset_id}/qc/{name}')
    @guarded
    def qc_download(dataset_id:str,name:str):
        if name not in ('fold','input_fold','weight_sum','weights'):
            raise ValueError('Unknown QC array')
        ds=service.datasets.open(dataset_id)
        if ds.output_info is None or not (ds.directory/(name+'.npy')).is_file():
            raise KeyError('QC array not found')
        return FileResponse(ds.directory/(name+'.npy'),filename=f'{dataset_id}-{name}.npy')
    return router


def install(app,db_path,storage_root):
    if getattr(app.state,'wave_cmp',None) is not None:
        return app.state.wave_cmp
    service=CMPService(db_path,storage_root)
    app.state.wave_cmp=service
    app.include_router(create_router(service))
    app.add_event_handler('startup',service.startup)
    app.add_event_handler('shutdown',service.close)
    return service
