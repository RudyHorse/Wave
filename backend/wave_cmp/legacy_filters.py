"""Drop-in adapters for the original SGYHandler processing entrypoints."""
from .filters import agc,bandpass
from .schemas import BandpassParams


def apply_agc(handler,file_id,window_ms,from_processed=False,parallel=False,num_workers=4):
    if file_id not in handler.files:
        return None
    f=handler.files[file_id]
    data=f['processed']['data'] if from_processed and 'processed' in f else f['data']
    result=agc(data,handler._effective_sample_rate(f,from_processed),window_ms,check_cancel=lambda:handler._check_cancel(file_id))
    params={'window_ms':window_ms}
    f['processed']={'data':result,'type':'agc','params':params}
    return {'status':'ok','type':'agc','params':params}


def apply_bandpass(handler,file_id,lowcut,lowpass,highpass,highcut,from_processed=False,parallel=False,num_workers=4):
    if file_id not in handler.files:
        return None
    f=handler.files[file_id]
    data=f['processed']['data'] if from_processed and 'processed' in f else f['data']
    params=BandpassParams(lowcut=lowcut,lowpass=lowpass,highpass=highpass,highcut=highcut)
    workers=max(1,min(int(num_workers),8)) if parallel else 1
    result=bandpass(data,handler._effective_sample_rate(f,from_processed),params,workers=workers,check_cancel=lambda:handler._check_cancel(file_id))
    f['processed']={'data':result,'type':'bandpass','params':params.model_dump()}
    return {'status':'ok','type':'bandpass','params':params.model_dump()}
