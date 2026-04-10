import numpy as np

# Create a structured array
dt = np.dtype([('a', 'i4'), ('b', 'f4')])
data = np.array([
    (1, 1.0),
    (2, 2.0),
    (1, 1.0),
    (3, 3.0),
    (2, 2.0)
], dtype=dt)

_, unique_index = np.unique(data, return_index=True)
print("unique_index:", unique_index)
print("sorted unique_index:", np.sort(unique_index))
