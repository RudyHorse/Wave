import segyio
import numpy as np
import os

fname = 'test_mini.sgy'
spec = segyio.spec()
spec.ilines = [1]
spec.xlines = [10]
spec.offsets = [1]
spec.samples = list(range(50))
spec.sorting = 1
spec.format = 1

with segyio.create(fname, spec) as f:
    f.text[0] = 'TEST'*200
    for i, trace in enumerate(f.trace):
        trace[:] = np.sin(np.linspace(0, 2*np.pi*5, 50)) * (i+1)

print(f'Created {fname}, size={os.path.getsize(fname)} bytes')
