"""Read Wave's existing SQLite / .npy storage without changing source arrays."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import struct
import threading
import numpy as np
from .gathers import GatherIndex
from .repository import canonical_json

_SAFE_ID = re.compile(r'^[A-Za-z0-9_-]{1,128}$')

def safe_path(root, dataset_id):
    if not _SAFE_ID.fullmatch(dataset_id):
        raise ValueError('Invalid dataset ID')
    root = Path(root).resolve()
    path = (root/dataset_id).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Dataset path escapes storage root')
    return path


def load_array(path, required=True):
    if not path.exists():
        if required:
            raise ValueError(f'Missing stored array: {path.name}')
        return None
    return np.load(path,mmap_mode='r',allow_pickle=False)


def source_header_view(path, trace_count):
    """Conservative raw header preservation for big-endian fixed-record SEG-Y.

    Unknown/variable layouts return None rather than guessing trace positions.
    """
    if not path or not Path(path).is_file():
        return None, 1
    try:
        with open(path,'rb') as fh:
            fh.seek(3200)
            binary = fh.read(400)
        if len(binary) != 400:
            return None,1
        ns, fmt = struct.unpack_from('>HH', binary,20)[0], struct.unpack_from('>H',binary,24)[0]
        ext = struct.unpack_from('>h',binary,304)[0]
        measurement = struct.unpack_from('>H',binary,54)[0]
        sample_bytes = {1:4,2:4,3:2,5:4,8:1}.get(fmt)
        if sample_bytes is None or ns==0 or ext<0 or ext>10000:
            return None,1
        start, stride = 3600+3200*ext, 240+ns*sample_bytes
        if Path(path).stat().st_size != start+stride*trace_count:
            return None,1
        mm = np.memmap(path,dtype=np.uint8,mode='r')
        return np.ndarray((trace_count,240),dtype=np.uint8,buffer=mm,offset=start,strides=(stride,1)), (2 if measurement==2 else 1)
    except (OSError,ValueError,struct.error):
        return None,1

@dataclass
class Dataset:
    id: str
    directory: Path
    meta: dict
    data: np.ndarray
    cdp: np.ndarray
    offsets: np.ndarray
    inline: np.ndarray
    xline: np.ndarray
    weights: np.ndarray | None
    index: GatherIndex
    fingerprint: str
    velocity_fingerprint: str
    kind: str
    output_info: dict | None
    headers: np.ndarray | None = None
    measurement_system: int = 1

    @property
    def dt_ms(self):
        return float(self.meta['sample_rate'])

    def read(self, indices):
        data = np.asarray(self.data[indices],dtype=np.float32)
        weights = np.ones(data.shape,dtype=np.float32) if self.weights is None else np.asarray(self.weights[indices],dtype=np.float32)
        # SEG-Y TraceIdentificationCode=2 is dead. Zero amplitude is NOT a mute.
        headers = self.trace_headers(indices)
        if headers is not None:
            dead = np.frombuffer(headers[:,28:30].copy().tobytes(),dtype='>i2') == 2
            weights[dead] = 0
        return data,weights

    def trace_headers(self, indices):
        if self.headers is None:
            return None
        headers = np.array(self.headers[indices],dtype=np.uint8,copy=True)
        # Reject templates with an index order different from Wave's arrays.
        cp = np.frombuffer(headers[:,20:24].copy().tobytes(),dtype='>i4')
        il = np.frombuffer(headers[:,188:192].copy().tobytes(),dtype='>i4')
        if not np.array_equal(cp,self.cdp[indices]) or not np.array_equal(il,self.inline[indices]):
            return None
        return headers

    def info(self):
        return {'id':self.id,'name':self.meta.get('name',self.id),'kind':self.kind,
                'trace_count':int(self.data.shape[0]),'samples':int(self.data.shape[1]),'dt_ms':self.dt_ms,
                'fingerprint':self.fingerprint,'velocity_fingerprint':self.velocity_fingerprint,
                'inlines':list(self.index.lines),'headers_available':self.headers is not None,
                'geometry':self.output_info['metadata'].get('geometry') if self.output_info else None}

class DatasetStore:
    def __init__(self, repository, root):
        self.repo,self.root = repository,Path(root).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self._cache = {}
        self._lock = threading.RLock()

    def list(self):
        with self.repo.connection() as db:
            rows = db.execute('SELECT id,name,trace_count,samples_per_trace,sample_rate FROM files ORDER BY created_at DESC').fetchall()
        return [dict(r) for r in rows]

    def open(self,dataset_id):
        directory = safe_path(self.root,dataset_id)
        with self.repo.connection() as db:
            row = db.execute('SELECT * FROM files WHERE id=?',(dataset_id,)).fetchone()
        if row is None:
            raise KeyError('Dataset not found in Wave database; save it to the database first')
        meta = dict(row)
        paths = sorted(directory.glob('*.npy'))
        stamp = tuple((p.name,p.stat().st_size,p.stat().st_mtime_ns) for p in paths)
        source_path = Path(meta['file_path']) if meta.get('file_path') else None
        source_stamp = None
        if source_path is not None and source_path.is_file():
            st = source_path.stat()
            source_stamp = (str(source_path.resolve()),st.st_size,st.st_mtime_ns)
        key = (dataset_id,stamp,source_stamp,meta.get('file_hash'),meta.get('sample_rate'))
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        data = load_array(directory/'data.npy')
        if data.ndim != 2 or min(data.shape)<1 or data.dtype.kind != 'f':
            raise ValueError('Invalid seismic data.npy; expected nonempty float matrix')
        if not np.isfinite(meta['sample_rate']) or meta['sample_rate']<=0:
            raise ValueError('Invalid dataset sample interval')
        output_info = self.repo.output(dataset_id)
        kind = output_info['kind'] if output_info else 'prestack'
        raw = load_array(directory/'raw.npy',False)
        if raw is not None and raw.shape != data.shape:
            raise ValueError('raw.npy/data.npy shape mismatch')
        raw = data if raw is None else raw
        weights = load_array(directory/'weights.npy',False)
        if weights is not None and weights.shape != data.shape:
            raise ValueError('weights.npy/data.npy shape mismatch')
        cdp,offsets = load_array(directory/'cdp.npy'),load_array(directory/'offset.npy')
        inline,xline = load_array(directory/'inline.npy',False),load_array(directory/'xline.npy',False)
        n = data.shape[0]
        inline = np.zeros(n,dtype=np.int32) if inline is None else inline
        xline = np.zeros(n,dtype=np.int32) if xline is None else xline
        if any(np.shape(a)!=(n,) for a in (cdp,offsets,inline,xline)):
            raise ValueError('Header lengths do not match stored traces')
        for arr in (cdp,inline,xline):
            if not np.isfinite(arr).all() or not np.equal(arr,np.floor(arr)).all() or (arr < -2147483648).any() or (arr > 2147483647).any():
                raise ValueError('Grouping headers must be signed 32-bit integers')
        index = GatherIndex(cdp,offsets,inline)
        digest = hashlib.sha256(canonical_json({'id':dataset_id,'dt_ms':meta['sample_rate'],'shape':data.shape}))
        # Hash source content once, cached against size/mtime. No sampled-hash collisions.
        for name in ('data.npy','raw.npy','cdp.npy','offset.npy','inline.npy','xline.npy','weights.npy','headers.npy'):
            p = directory/name
            if p.exists():
                digest.update(name.encode())
                with p.open('rb') as fh:
                    for block in iter(lambda:fh.read(4*1024*1024),b''):
                        digest.update(block)
        headers = load_array(directory/'headers.npy',False)
        measurement=1
        if headers is not None and (headers.shape!=(n,240) or headers.dtype!=np.uint8):
            raise ValueError('headers.npy must be uint8 (ntraces,240)')
        if headers is None:
            headers,measurement=source_header_view(meta.get('file_path'),n)
        if headers is not None and not (directory/'headers.npy').exists():
            digest.update(b'source_trace_headers')
            for first in range(0,n,4096):
                digest.update(headers[first:first+4096].tobytes())
        fp = digest.hexdigest()
        if output_info:
            measurement=output_info['metadata'].get('measurement_system',1)
        ds = Dataset(dataset_id,directory,meta,raw,cdp,offsets,inline,xline,weights,index,fp,
                     output_info['velocity_source_fingerprint'] if output_info and kind!='prestack' else fp,kind,output_info,headers,measurement)
        with self._lock:
            if len(self._cache)>=4:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key]=ds
        return ds
