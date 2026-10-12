"""Explicit units and strict, JSON-serializable processing contracts."""
from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Geometry(StrictModel):
    offset_units: Literal['m', 'ft'] = 'm'
    offset_convention: Literal['full', 'half'] = 'full'
    start_time_ms: float = Field(default=0, ge=0, le=32767)

    @property
    def offset_factor(self):
        return (0.3048 if self.offset_units == 'ft' else 1.0) * (2 if self.offset_convention == 'half' else 1)

class Pick(StrictModel):
    time_ms: float = Field(ge=0, le=1e6)
    velocity_mps: float = Field(gt=0, le=30000)

class VelocityFunction(StrictModel):
    inline: int = 0
    cdp: int
    picks: list[Pick] = Field(min_length=1, max_length=2000)

    @model_validator(mode='after')
    def ordered(self):
        if any(a.time_ms >= b.time_ms for a, b in zip(self.picks, self.picks[1:])):
            raise ValueError('Pick times must be strictly increasing; duplicates are not permitted')
        return self

class VelocityDocument(StrictModel):
    schema_version: Literal[1] = 1
    type: Literal['stacking_velocity'] = 'stacking_velocity'
    name: str = Field(min_length=1, max_length=160)
    source_file_id: str = Field(min_length=1, max_length=128)
    source_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    geometry: Geometry = Field(default_factory=Geometry)
    time_interpolation: Literal['linear', 'pchip'] = 'linear'
    spatial_extrapolation: Literal['error', 'constant'] = 'error'
    time_extrapolation: Literal['error', 'constant'] = 'constant'
    supergather_size: int = Field(default=5, ge=1, le=101)
    functions: list[VelocityFunction] = Field(min_length=1, max_length=20000)
    comment: str = Field(default='', max_length=4000)

    @model_validator(mode='after')
    def keys_unique(self):
        if not self.supergather_size % 2:
            raise ValueError('Supergather size must be odd and includes the center CMP')
        keys = [(f.inline, f.cdp) for f in self.functions]
        if len(set(keys)) != len(keys):
            raise ValueError('Duplicate (inline, CDP) velocity functions')
        if not self.name.strip():
            raise ValueError('Name must not be blank')
        return self

class SaveVelocity(StrictModel):
    document: VelocityDocument
    parent_id: str | None = None

class Selection(StrictModel):
    inline: int = 0
    cdp: int
    supergather_size: int = Field(default=1, ge=1, le=101)
    min_offset_m: float = Field(default=0, ge=0)
    max_offset_m: float | None = Field(default=None, gt=0)
    geometry: Geometry = Field(default_factory=Geometry)

    @model_validator(mode='after')
    def limits(self):
        if not self.supergather_size % 2:
            raise ValueError('Supergather size must be odd')
        if self.max_offset_m is not None and self.max_offset_m < self.min_offset_m:
            raise ValueError('max_offset_m must be >= min_offset_m')
        return self

class NMOParams(StrictModel):
    interpolation: Literal['linear', 'sinc'] = 'linear'
    sinc_half_width: int = Field(default=8, ge=2, le=16)
    stretch_limit: float = Field(default=0.30, gt=0, le=10)
    stretch_taper: float = Field(default=0.05, ge=0, le=1)

    @model_validator(mode='after')
    def taper_limits(self):
        if self.stretch_taper > self.stretch_limit:
            raise ValueError('stretch_taper must not exceed stretch_limit')
        return self

class SpectrumRequest(StrictModel):
    selection: Selection
    velocity_min: float = Field(default=1200, gt=0, le=30000)
    velocity_max: float = Field(default=5000, gt=0, le=30000)
    velocity_step: float = Field(default=25, gt=0)
    time_min_ms: float = Field(default=0, ge=0)
    time_max_ms: float | None = Field(default=None, ge=0)
    time_stride: int = Field(default=2, ge=1, le=128)
    window_ms: float = Field(default=24, gt=0, le=1000)
    min_fold: int = Field(default=2, ge=2)
    nmo: NMOParams = Field(default_factory=NMOParams)

    @model_validator(mode='after')
    def ranges(self):
        if self.velocity_max <= self.velocity_min:
            raise ValueError('velocity_max must be > velocity_min')
        if (self.velocity_max - self.velocity_min) / self.velocity_step > 511:
            raise ValueError('At most 512 trial velocities; increase velocity_step')
        if self.time_max_ms is not None and self.time_max_ms < self.time_min_ms:
            raise ValueError('Invalid time range')
        return self

class PreviewRequest(StrictModel):
    selection: Selection
    velocity_file_id: str | None = None
    document: VelocityDocument | None = None
    nmo: NMOParams = Field(default_factory=NMOParams)

    @model_validator(mode='after')
    def one_model(self):
        if (self.velocity_file_id is None) == (self.document is None):
            raise ValueError('Supply exactly one of velocity_file_id or document')
        return self

class AGCParams(StrictModel):
    window_ms: float = Field(default=500, gt=0, le=60000)

class BandpassParams(StrictModel):
    lowcut: float = Field(default=5, ge=0)
    lowpass: float = Field(default=10, gt=0)
    highpass: float = Field(default=80, gt=0)
    highcut: float = Field(default=100, gt=0)

    @model_validator(mode='after')
    def order(self):
        if not self.lowcut < self.lowpass <= self.highpass < self.highcut:
            raise ValueError('Require 0 <= lowcut < lowpass <= highpass < highcut')
        return self

class StackParams(StrictModel):
    method: Literal['mean', 'sum', 'median', 'trimmed_mean'] = 'mean'
    trim_fraction: float = Field(default=0.1, ge=0, lt=0.5)
    min_fold: int = Field(default=1, ge=1)

class AGCStep(StrictModel):
    type: Literal['agc']
    params: AGCParams = Field(default_factory=AGCParams)
class BandpassStep(StrictModel):
    type: Literal['bandpass']
    params: BandpassParams = Field(default_factory=BandpassParams)
class NMOStep(StrictModel):
    type: Literal['nmo']
    params: NMOParams = Field(default_factory=NMOParams)
class StackStep(StrictModel):
    type: Literal['stack']
    params: StackParams = Field(default_factory=StackParams)
Step = Annotated[Union[AGCStep, BandpassStep, NMOStep, StackStep], Field(discriminator='type')]

class RunRequest(StrictModel):
    dataset_id: str = Field(min_length=1, max_length=128)
    output_name: str = Field(min_length=1, max_length=160)
    velocity_file_id: str | None = None
    geometry: Geometry = Field(default_factory=Geometry)
    inline: int | None = None
    cdp_min: int | None = None
    cdp_max: int | None = None
    min_offset_m: float = Field(default=0, ge=0)
    max_offset_m: float | None = Field(default=None, gt=0)
    input_already_nmo: bool = False
    steps: list[Step] = Field(min_length=1, max_length=20)

    @model_validator(mode='after')
    def sequence(self):
        names = [s.type for s in self.steps]
        if names.count('nmo') > 1 or names.count('stack') > 1:
            raise ValueError('NMO and STACK may occur at most once')
        if 'nmo' in names and self.velocity_file_id is None:
            raise ValueError('NMO requires a saved velocity file')
        if 'stack' in names and names[-1] != 'stack':
            raise ValueError('STACK must be the last step')
        if 'nmo' in names and any(s in ('agc','bandpass') for s in names[names.index('nmo') + 1:]):
            raise ValueError('Place AGC/bandpass before NMO (weights must remain consistent)')
        if self.cdp_min is not None and self.cdp_max is not None and self.cdp_min > self.cdp_max:
            raise ValueError('cdp_min must be <= cdp_max')
        if self.max_offset_m is not None and self.min_offset_m > self.max_offset_m:
            raise ValueError('Invalid offset range')
        return self
