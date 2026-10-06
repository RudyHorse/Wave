import os
import numpy as np
from typing import Optional, Dict, Any

STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'files')
os.makedirs(STORAGE_DIR, exist_ok=True)


def file_dir(file_id: str) -> str:
    d = os.path.join(STORAGE_DIR, file_id)
    os.makedirs(d, exist_ok=True)
    return d


def data_path(file_id: str) -> str:
    return os.path.join(file_dir(file_id), 'data.npy')


def inline_path(file_id: str) -> str:
    return os.path.join(file_dir(file_id), 'inline.npy')


def xline_path(file_id: str) -> str:
    return os.path.join(file_dir(file_id), 'xline.npy')


def cdp_path(file_id: str) -> str:
    return os.path.join(file_dir(file_id), 'cdp.npy')


def offset_path(file_id: str) -> str:
    return os.path.join(file_dir(file_id), 'offset.npy')


def ffid_path(file_id: str) -> str:
    return os.path.join(file_dir(file_id), 'ffid.npy')


def processed_dir(file_id: str) -> str:
    d = os.path.join(file_dir(file_id), 'processed')
    os.makedirs(d, exist_ok=True)
    return d


def save_data(file_id: str, data: np.ndarray):
    np.save(data_path(file_id), data.astype(np.float32))


def load_data(file_id: str) -> Optional[np.ndarray]:
    path = data_path(file_id)
    if os.path.exists(path):
        return np.load(path)
    return None


def save_inline_xline(file_id: str, inline: np.ndarray, xline: np.ndarray):
    np.save(inline_path(file_id), inline)
    np.save(xline_path(file_id), xline)


def save_cdp_offset(file_id: str, cdp: np.ndarray, offset: np.ndarray):
    np.save(cdp_path(file_id), cdp)
    np.save(offset_path(file_id), offset)


def load_cdp_offset(file_id: str):
    cp = cdp_path(file_id)
    op = offset_path(file_id)
    cdp = np.load(cp) if os.path.exists(cp) else None
    offset = np.load(op) if os.path.exists(op) else None
    return cdp, offset


def chan_path(file_id: str) -> str:
    return os.path.join(file_dir(file_id), 'chan.npy')


def save_ffid_offset(file_id: str, ffid: np.ndarray, offset: np.ndarray):
    np.save(ffid_path(file_id), ffid)
    np.save(offset_path(file_id), offset)


def save_ffid_chan(file_id: str, ffid: np.ndarray, chan: np.ndarray):
    np.save(ffid_path(file_id), ffid)
    np.save(chan_path(file_id), chan)


def load_ffid_chan(file_id: str):
    fp = ffid_path(file_id)
    cp = chan_path(file_id)
    ffid = np.load(fp) if os.path.exists(fp) else None
    chan = np.load(cp) if os.path.exists(cp) else None
    return ffid, chan


def load_ffid_offset(file_id: str):
    fp = ffid_path(file_id)
    op = offset_path(file_id)
    ffid = np.load(fp) if os.path.exists(fp) else None
    offset = np.load(op) if os.path.exists(op) else None
    return ffid, offset


def load_inline_xline(file_id: str):
    ip = inline_path(file_id)
    xp = xline_path(file_id)
    inline = np.load(ip) if os.path.exists(ip) else None
    xline = np.load(xp) if os.path.exists(xp) else None
    return inline, xline


def save_processed(file_id: str, run_id: str, data: np.ndarray):
    np.save(os.path.join(processed_dir(file_id), f'{run_id}.npy'), data.astype(np.float32))


def load_processed(file_id: str, run_id: str) -> Optional[np.ndarray]:
    path = os.path.join(processed_dir(file_id), f'{run_id}.npy')
    if os.path.exists(path):
        return np.load(path)
    return None


def delete_all(file_id: str):
    import shutil
    d = os.path.join(STORAGE_DIR, file_id)
    if os.path.exists(d):
        shutil.rmtree(d)


def file_exists(file_id: str) -> bool:
    return os.path.exists(data_path(file_id))
