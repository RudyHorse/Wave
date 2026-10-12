"""Additive SQLite migration. Velocity files are actual JSON BLOBs, not paths."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from .schemas import VelocityDocument

class ConflictError(ValueError):
    pass

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')

class Repository:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS wave_velocity_files (
                id TEXT PRIMARY KEY, series_id TEXT NOT NULL, revision INTEGER NOT NULL,
                parent_id TEXT REFERENCES wave_velocity_files(id), name TEXT NOT NULL,
                source_file_id TEXT NOT NULL, source_fingerprint TEXT NOT NULL,
                filename TEXT NOT NULL, sha256 TEXT NOT NULL, payload BLOB NOT NULL,
                created_at TEXT NOT NULL, UNIQUE(series_id, revision)
            );
            CREATE INDEX IF NOT EXISTS wave_velocity_source ON wave_velocity_files(source_file_id);
            CREATE TABLE IF NOT EXISTS wave_cmp_jobs (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0,
                request_json TEXT NOT NULL, velocity_sha256 TEXT,
                result_id TEXT, error TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS wave_cmp_outputs (
                id TEXT PRIMARY KEY, job_id TEXT NOT NULL UNIQUE, source_file_id TEXT NOT NULL,
                velocity_source_fingerprint TEXT NOT NULL, kind TEXT NOT NULL,
                metadata_json TEXT NOT NULL, created_at TEXT NOT NULL
            );
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def save_velocity(self, document: VelocityDocument, parent_id=None):
        payload = canonical_json(document.model_dump(mode='json'))
        if len(payload) > 16*1024*1024:
            raise ValueError('Velocity JSON exceeds 16 MiB')
        digest = hashlib.sha256(payload).hexdigest()
        file_id = str(uuid.uuid4())
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            revision, series = 1, file_id
            if parent_id is not None:
                parent = db.execute('SELECT * FROM wave_velocity_files WHERE id=?', (parent_id,)).fetchone()
                if parent is None:
                    raise KeyError('Parent velocity file not found')
                if parent['source_file_id'] != document.source_file_id or parent['source_fingerprint'] != document.source_fingerprint:
                    raise ConflictError('A revision cannot change its source dataset')
                latest = db.execute('SELECT MAX(revision) FROM wave_velocity_files WHERE series_id=?', (parent['series_id'],)).fetchone()[0]
                if latest != parent['revision']:
                    raise ConflictError('A newer revision already exists; reload it before saving')
                series, revision = parent['series_id'], parent['revision']+1
            db.execute('INSERT INTO wave_velocity_files (id,series_id,revision,parent_id,name,source_file_id,source_fingerprint,filename,sha256,payload,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (file_id,series,revision,parent_id,document.name,document.source_file_id,document.source_fingerprint,
                 f'velocity-{series}-r{revision}.json',digest,sqlite3.Binary(payload),utcnow()))
        return self.velocity_info(file_id)

    def velocity_info(self, file_id):
        with self.connection() as db:
            row = db.execute('SELECT id,series_id,revision,parent_id,name,source_file_id,source_fingerprint,filename,sha256,created_at FROM wave_velocity_files WHERE id=?',(file_id,)).fetchone()
        if row is None:
            raise KeyError('Velocity file not found')
        return dict(row)

    def velocity_bytes(self, file_id):
        with self.connection() as db:
            row = db.execute('SELECT payload,sha256 FROM wave_velocity_files WHERE id=?',(file_id,)).fetchone()
        if row is None:
            raise KeyError('Velocity file not found')
        payload = bytes(row['payload'])
        if hashlib.sha256(payload).hexdigest() != row['sha256']:
            raise ValueError('Stored velocity file failed SHA-256 integrity check')
        return payload

    def load_velocity(self, file_id):
        return VelocityDocument.model_validate_json(self.velocity_bytes(file_id))

    def list_velocities(self, source_file_id=None):
        with self.connection() as db:
            query = 'SELECT id FROM wave_velocity_files'
            params = ()
            if source_file_id is not None:
                query += ' WHERE source_file_id=?'
                params = (source_file_id,)
            rows = db.execute(query+' ORDER BY created_at DESC',params).fetchall()
        return [self.velocity_info(r['id']) for r in rows]

    def create_job(self, request, velocity_sha=None):
        job_id, now = str(uuid.uuid4()), utcnow()
        with self.connection() as db:
            db.execute('INSERT INTO wave_cmp_jobs(id,status,request_json,velocity_sha256,created_at,updated_at) VALUES (?,?,?,?,?,?)',
                       (job_id,'queued',canonical_json(request).decode(),velocity_sha,now,now))
        return job_id

    def job(self, job_id):
        with self.connection() as db:
            row = db.execute('SELECT * FROM wave_cmp_jobs WHERE id=?',(job_id,)).fetchone()
        if row is None:
            raise KeyError('Job not found')
        result = dict(row)
        result['request'] = json.loads(result.pop('request_json'))
        return result

    def update_job(self, job_id, **fields):
        allowed = {'status','progress','result_id','error','cancel_requested'}
        if not fields.keys() <= allowed:
            raise ValueError('Invalid job fields')
        fields['updated_at'] = utcnow()
        with self.connection() as db:
            db.execute('UPDATE wave_cmp_jobs SET '+','.join(f'{k}=?' for k in fields)+' WHERE id=?',tuple(fields.values())+(job_id,))

    def cancel(self, job_id):
        with self.connection() as db:
            row = db.execute('SELECT status FROM wave_cmp_jobs WHERE id=?',(job_id,)).fetchone()
            if row is None:
                raise KeyError('Job not found')
            if row['status'] in ('queued','running'):
                db.execute('UPDATE wave_cmp_jobs SET cancel_requested=1,updated_at=? WHERE id=?',(utcnow(),job_id))
        return self.job(job_id)

    def recover_interrupted(self):
        with self.connection() as db:
            db.execute("UPDATE wave_cmp_jobs SET status='interrupted',error='Backend stopped before completion; resubmit explicitly',updated_at=? WHERE status IN ('running','queued')",(utcnow(),))

    def output(self, dataset_id):
        with self.connection() as db:
            row = db.execute('SELECT * FROM wave_cmp_outputs WHERE id=?',(dataset_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result['metadata'] = json.loads(result.pop('metadata_json'))
        return result
