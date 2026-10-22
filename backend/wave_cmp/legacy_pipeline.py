"""Registry for Wave's existing module signatures; no change of public API.

CMP shape-changing processing is mounted separately to avoid corrupting the
legacy viewer's original trace/header arrays after STACK.
"""
from dataclasses import dataclass,field
import threading

@dataclass(frozen=True)
class LegacyProcessor:
    method:str
    required:tuple=()
    defaults:dict=field(default_factory=dict)
    parallel:bool=False

REGISTRY={
 'agc':LegacyProcessor('_apply_agc',('window_ms',),parallel=True),
 'bandpass':LegacyProcessor('_apply_bandpass',('lowcut','lowpass','highpass','highcut'),parallel=True),
 'fxdecon':LegacyProcessor('_apply_fxdecon',('filter_length',),parallel=True),
 'fxdecont':LegacyProcessor('_apply_fxdecont',('pred_order','retro_order','reg','window_size','step','nonlinear_plus','freq_min','freq_max'),parallel=True),
 'decons':LegacyProcessor('_apply_decons',('operator_length','prewhitening','phase_mode','bandwidth_min','bandwidth_max')),
 'psf':LegacyProcessor('_apply_psf',('phase_deg',)),
 'fk3d':LegacyProcessor('_apply_fk3d',defaults=dict(wndw_inline=48,wndw_xline=48,overlap_inline=12,overlap_xline=12,
    min_dip_inline=-12.,max_dip_inline=12.,min_dip_xline=-12.,max_dip_xline=12.,pct_dip_taper=10.,wrap_filt=True)),
 'gain':LegacyProcessor('_apply_gain',defaults=dict(voption=2.,toption=1.,factor=1.,units='feet')),
 'lfaf':LegacyProcessor('_apply_lfaf',defaults=dict(dx=25.,vel=1500.,f1=0.,f2=20.,ftaper=5.,maxmix=0)),
 'lfaf1':LegacyProcessor('_apply_lfaf1',defaults=dict(vel=1500.,f1=0.,f2=20.,ftaper=5.,maxmix=15,min_offset=10.,mute_time=0.,mute_zone_width=50.)),
 'lfafn':LegacyProcessor('_apply_lfafn',defaults=dict(dx=25.,vel=1500.,f1=0.,f2=20.,ftaper=5.,maxmix=0,direction='both',attenuation=1.)),
 'resample':LegacyProcessor('_apply_resample',defaults=dict(sample_interval=None,start_time=None,end_time=None)),
 'dsout':LegacyProcessor('_apply_dsout',defaults=dict(path='',sort_type='none',first_min=None,first_max=None,second_min=None,second_max=None)),
}
_running=set()
_guard=threading.Lock()


def run_sequence(handler,file_id,steps,parallel=False,num_workers=4,*,cancelled_error):
    if file_id not in handler.files:
        return None
    key=(id(handler),file_id)
    with _guard:
        if key in _running:
            raise ValueError('A legacy processing sequence is already running for this file')
        _running.add(key)
    previous=handler.files[file_id].pop('processed',None)
    previous_rate=handler.files[file_id].pop('processed_rate',None)
    previous_start=handler.files[file_id].pop('processed_start',None)
    try:
        # Validate complete sequence before any processor, particularly DSOUT, runs.
        prepared=[]
        for step in steps:
            name=step.get('type')
            if name not in REGISTRY:
                raise ValueError(f'Unknown legacy processing module: {name}')
            spec=REGISTRY[name];p=step.get('params',{})
            missing=set(spec.required)-p.keys()
            if missing:
                raise ValueError(f'{name}: missing parameters {sorted(missing)}')
            prepared.append((name,spec,p))
        outputs=[]
        for name,spec,p in prepared:
            handler._check_cancel(file_id)
            args=[p[k] for k in spec.required]
            kwargs={k:p.get(k,v) for k,v in spec.defaults.items()}
            kwargs['from_processed']=True
            if spec.parallel:
                kwargs.update(parallel=parallel,num_workers=num_workers)
            try:
                result=getattr(handler,spec.method)(file_id,*args,**kwargs)
                if name=='dsout':
                    outputs.append(result)
            except cancelled_error:
                raise
            except Exception as exc:
                raise RuntimeError(f"Step '{name}' failed: {exc}") from exc
        return {'status':'ok','steps':steps,'dsout':outputs}
    except BaseException:
        if file_id in handler.files:
            for key,value in (('processed',previous),('processed_rate',previous_rate),('processed_start',previous_start)):
                if value is None:
                    handler.files[file_id].pop(key,None)
                else:
                    handler.files[file_id][key]=value
        raise
    finally:
        with _guard:
            _running.discard(key)
