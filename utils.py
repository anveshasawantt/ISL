import numpy as np

def extract_hands(results):
    """Raw features: [left hand 63, right hand 63] (x,y,z per landmark)."""
    left, right = np.zeros(63), np.zeros(63)
    if results.multi_hand_landmarks and results.multi_handedness:
        for lm, hd in zip(results.multi_hand_landmarks, results.multi_handedness):
            arr = np.array([[p.x, p.y, p.z] for p in lm.landmark]).flatten()
            if hd.classification[0].label == "Left":
                left = arr
            else:
                right = arr
    return np.concatenate([left, right])

def _hand_feats(h):
    if np.allclose(h, 0):
        return np.zeros(45)
    xy = h.reshape(21, 3)[:, :2]
    wrist = xy[0]
    size = np.linalg.norm(xy[9] - xy[0])      # wrist -> middle finger base
    if size < 1e-4:
        size = 1.0
    shape = ((xy - wrist) / size).flatten()   # 42: finger shape, size/position independent
    return np.concatenate([shape, wrist, [size]])   # + wrist position (2) + size (1) = 45

def normalize_frame(f):
    return np.concatenate([_hand_feats(f[:63]), _hand_feats(f[63:126])])   # 90 features

def normalize_seq(seq):
    return np.array([normalize_frame(f) for f in seq])