"""Bounded-memory SEG-Y rev1 IEEE writer; no extra dependency.

The application still uses segyio for general SEG-Y import. This deliberately
narrow exporter also works when a platform's segyio wheel is unavailable.
Raw-header preservation is optional and explicitly reported to the caller.
"""
from pathlib import Path
import os
import struct
import uuid
import numpy as np


def write_segy(path, data, dt_ms, cdp, inline, xline, offsets_m, *, start_time_ms=0,
               fold=None, headers=None, stack=False, measurement_system=1,
               provenance='', check_cancel=lambda: None):
    path=Path(path)
    n,ns=data.shape
    dt_us=int(round(dt_ms*1000))
    if n<1 or not 1<=ns<=65535 or not 1<=dt_us<=65535 or abs(dt_us-dt_ms*1000)>1e-6:
        raise ValueError('SEG-Y rev1 export requires 1..65535 samples and integer 1..65535 us interval')
    if not 0<=start_time_ms<=32767 or abs(start_time_ms-round(start_time_ms))>1e-6:
        raise ValueError('SEG-Y delay header requires integer start_time_ms in 0..32767')
    if measurement_system not in (1,2):
        raise ValueError('measurement_system must be 1 (m) or 2 (ft)')
    for name,arr in [('CDP',cdp),('inline',inline),('xline',xline),('offset',offsets_m)]:
        if np.shape(arr)!=(n,) or not np.isfinite(arr).all():
            raise ValueError(f'Invalid {name} array')
    for arr in (cdp,inline,xline):
        if (np.abs(arr)>2147483647).any():
            raise ValueError('Header integer exceeds signed 32-bit range')
    if headers is not None and (headers.shape!=(n,240) or headers.dtype!=np.uint8):
        raise ValueError('Invalid raw header templates')
    if fold is not None and np.shape(fold) not in ((n,), (n,ns)):
        raise ValueError('Fold must be per trace or per sample')
    binary=bytearray(400)
    for off,val in ((16,dt_us),(18,dt_us),(20,ns),(22,ns),(24,5),(28,2),(54,measurement_system),(300,0x100),(302,1),(304,0)):
        struct.pack_into('>H',binary,off,val)
    lines=['WAVE CMP - SEG-Y REV1 / IEEE FLOAT32 / BIG ENDIAN',
           'STACK' if stack else 'NMO/PRESTACK',
           'FULL SOURCE-RECEIVER OFFSET; BINARY MEASUREMENT SYSTEM DEFINES UNITS',
           'PER-SAMPLE FOLD AND WEIGHT_SUM ARE IN NPY QC FILES; HEADER FOLD IS MAX',
           'RAW HEADER TEMPLATES PRESERVED' if headers is not None else 'MINIMAL HEADERS: SOURCE XY NOT AVAILABLE; COORDINATES NOT INVENTED',
           provenance]
    text=''.join((f'C{i+1:02d} '+(lines[i] if i<len(lines) else ''))[:80].ljust(80) for i in range(40)).encode('ascii','replace')
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.partial')
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with temp.open('xb') as fh:
            fh.write(text);fh.write(binary)
            for i in range(n):
                if i%64==0:
                    check_cancel()
                h=bytearray(240) if headers is None else bytearray(headers[i].tobytes())
                off=float(offsets_m[i])/(0.3048 if measurement_system==2 else 1)
                if abs(off)>2147483647:
                    raise ValueError('Offset exceeds SEG-Y signed 32-bit range')
                for pos,value in ((0,i+1),(4,i+1),(20,int(cdp[i])),(24,1 if stack else i+1),
                                  (36,0 if stack else int(round(off))),(188,int(inline[i])),(192,int(xline[i]))):
                    struct.pack_into('>i',h,pos,value)
                scalar_fold=1 if fold is None else int(np.max(fold[i]))
                struct.pack_into('>h',h,28,1 if scalar_fold>0 else 2)
                struct.pack_into('>h',h,32,min(scalar_fold,32767))
                struct.pack_into('>h',h,34,1)
                struct.pack_into('>h',h,108,int(round(start_time_ms)))
                struct.pack_into('>hh',h,110,0,0)  # irregular sample mask cannot be encoded in two mute times
                struct.pack_into('>HH',h,114,ns,dt_us)
                if stack:
                    # A source/receiver pair is not meaningful for a stack trace.
                    # Preserve CDP_X/Y and scalar; set S/G coordinates to that CMP when available.
                    h[72:76]=h[180:184];h[76:80]=h[184:188]
                    h[80:84]=h[180:184];h[84:88]=h[184:188]
                samples=np.asarray(data[i],dtype='>f4')
                if not np.isfinite(samples).all():
                    raise ValueError('Cannot export nonfinite samples')
                fh.write(h);fh.write(samples.tobytes())
            fh.flush();os.fsync(fh.fileno())
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)
    return {'path':str(path),'traces':n,'samples':ns,'headers_preserved':headers is not None,
            'format':'SEG-Y rev1 IEEE big-endian','fold_header':'maximum sample fold, saturated at 32767'}
