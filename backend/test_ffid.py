import segyio
import numpy as np
import os
import json
import requests
import sys

import sys
API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5006"
filepath = "test_ffid.sgy"

spec = segyio.spec()
spec.format = 1
spec.iline = 1
spec.xline = 2
spec.sorting = 2
spec.tracecount = 40
spec.samples = range(20)

with segyio.create(filepath, spec) as f:
    f.trace = np.random.randn(40, 20)
    for i in range(10):
        f.header[i] = {segyio.TraceField.INLINE_3D: 100, segyio.TraceField.CROSSLINE_3D: i+1}
    for i in range(10, 20):
        f.header[i] = {segyio.TraceField.INLINE_3D: 101, segyio.TraceField.CROSSLINE_3D: i-9}
    for i in range(20, 30):
        f.header[i] = {segyio.TraceField.INLINE_3D: 102, segyio.TraceField.CROSSLINE_3D: i-19}
    for i in range(30, 40):
        f.header[i] = {segyio.TraceField.INLINE_3D: 103, segyio.TraceField.CROSSLINE_3D: i-29}
    for i in range(40):
        f.header[i][segyio.TraceField.FieldRecord] = 1000 + (i // 10)
    for i in range(40):
        f.header[i][segyio.TraceField.CDP] = 500 + (i // 10)
    for i in range(40):
        f.header[i][segyio.TraceField.offset] = (i % 10) * 100

print("Created test file", filepath)

with open(filepath, "rb") as fp:
    r = requests.post(API + "/api/upload", files={"file": fp})
upload_data = r.json()
fid = upload_data["file_id"]
print("Uploaded file ID:", fid)
print("FFID range:", upload_data.get("ffid_min"), "-", upload_data.get("ffid_max"))

r = requests.get(API + "/api/sort-info/" + fid)
sort_info = r.json()
print("Sort info:", json.dumps(sort_info, indent=2))

r = requests.get(API + "/api/ffid-list/" + fid)
ffid_info = r.json()
print("FFID list:", json.dumps(ffid_info, indent=2))

r = requests.get(API + "/api/visualize/" + fid, params={"sort_mode": "ffid_offset", "inline": 1000, "num_gathers": 1})
viz = r.json()
print("FFID 1000, gather 1:", viz["traces"], "traces (expected 10)")
assert viz["traces"] == 10, f"Expected 10, got {viz['traces']}"

r = requests.get(API + "/api/visualize/" + fid, params={"sort_mode": "ffid_offset", "inline": 1000, "num_gathers": 2})
viz = r.json()
print("FFID 1000, gather 2:", viz["traces"], "traces (expected 20)")
assert viz["traces"] == 20, f"Expected 20, got {viz['traces']}"

r = requests.get(API + "/api/visualize/" + fid, params={"sort_mode": "ffid_offset", "inline": 1003, "num_gathers": 1})
viz = r.json()
print("FFID 1003, gather 1:", viz["traces"], "traces (expected 10)")
assert viz["traces"] == 10, f"Expected 10, got {viz['traces']}"

os.remove(filepath)
print("ALL TESTS PASSED")
