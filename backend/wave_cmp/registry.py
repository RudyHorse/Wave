"""Typed gather pipeline, separate from HTTP and persistence."""
from dataclasses import dataclass
import numpy as np
from .filters import agc, bandpass
from .nmo import apply_nmo
from .stack import stack_gather

@dataclass
class GatherState:
    data: np.ndarray
    weights: np.ndarray
    offsets_m: np.ndarray
    inline: int
    cdp: int
    dt_ms: float
    start_time_ms: float
    velocity_model: object = None
    nmo_applied: bool = False
    stack_result: object = None

PROCESSORS = {}

def processor(name):
    def register(fn):
        if name in PROCESSORS:
            raise ValueError(f'Duplicate processor {name}')
        PROCESSORS[name]=fn
        return fn
    return register

@processor('agc')
def _agc(state, params, cancel):
    state.data=agc(np.where(state.weights>0,state.data,0),state.dt_ms,params.window_ms,check_cancel=cancel)

@processor('bandpass')
def _bandpass(state, params, cancel):
    state.data=bandpass(np.where(state.weights>0,state.data,0),state.dt_ms,params,check_cancel=cancel)

@processor('nmo')
def _nmo(state,params,cancel):
    if state.nmo_applied:
        raise ValueError('NMO already applied; inverse/repeated NMO is not supported')
    if state.velocity_model is None:
        raise ValueError('NMO requires a velocity model')
    t=(state.start_time_ms+np.arange(state.data.shape[1])*state.dt_ms)/1000
    vel,dv=state.velocity_model.evaluate(state.inline,state.cdp,t)
    result=apply_nmo(state.data,state.offsets_m,state.dt_ms/1000,vel,params,
        start_time_s=state.start_time_ms/1000,input_weights=state.weights,
        velocity_derivative=dv,check_cancel=cancel)
    state.data,state.weights=result.data,result.weights
    state.nmo_applied=True

@processor('stack')
def _stack(state,params,cancel):
    if not state.nmo_applied:
        raise ValueError('STACK requires NMO or explicit input_already_nmo acknowledgement')
    cancel()
    state.stack_result=stack_gather(state.data,state.weights,params)


def run_gather(state,steps,check_cancel=lambda:None):
    for step in steps:
        check_cancel()
        fn=PROCESSORS.get(step.type)
        if fn is None:
            raise ValueError(f'Unknown processor {step.type}')
        fn(state,step.params,check_cancel)
    return state
