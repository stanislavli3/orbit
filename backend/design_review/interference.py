"""Bounding-box interference check (SCRUM-56 prototype).

APPROXIMATION: every part is reduced to an axis-aligned bounding box (AABB)
built from its placement origin and its box extents. This is NOT an exact
B-rep intersection — rotations are ignored and any shape is treated as its
enclosing box, so results can contain false positives. Validation against
real CAD is tracked in SCRUM-67.

Geometry source: a STEP file whose parts are CSG ``BLOCK`` primitives,
e.g. ``#10=BLOCK('ORB-1042',#11,40.,30.,5.);`` with ``#11`` an
``AXIS2_PLACEMENT_3D`` whose location is a ``CARTESIAN_POINT``. A plain JSON
list of ``{"id", "origin": [x,y,z], "size": [dx,dy,dz]}`` is also accepted.
"""
import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

APPROXIMATION_NOTE = (
    "Axis-aligned bounding-box approximation from placement + box extents; "
    "not an exact B-rep intersection (rotations ignored)."
)

SAMPLE_LAYOUT = Path(settings.BASE_DIR).parent / "samples" / "bracket_assembly_layout.step"

_ENTITY = re.compile(r"#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*?)\)\s*;", re.S)
_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


@dataclass(frozen=True)
class Box:
    id: str
    min: tuple
    max: tuple

    @classmethod
    def from_origin_size(cls, id, origin, size):
        o = tuple(float(v) for v in origin)
        s = tuple(float(v) for v in size)
        if len(o) != 3 or len(s) != 3 or any(v <= 0 for v in s):
            raise ValueError(f"Part {id}: origin and size need 3 values, sizes > 0")
        return cls(str(id), o, tuple(a + b for a, b in zip(o, s)))


def parse_step_boxes(text):
    entities = {int(m.group(1)): (m.group(2), m.group(3)) for m in _ENTITY.finditer(text)}

    def point(ref):
        kind, args = entities[int(ref)]
        if kind != "CARTESIAN_POINT":
            raise ValueError(f"#{ref} is not a CARTESIAN_POINT")
        return [float(v) for v in re.findall(_NUM, args.split(",", 1)[1])]

    boxes = []
    for kind, args in entities.values():
        if kind != "BLOCK":
            continue
        m = re.match(rf"\s*'([^']*)'\s*,\s*#(\d+)\s*,\s*({_NUM})\s*,\s*({_NUM})\s*,\s*({_NUM})\s*$", args)
        if not m:
            raise ValueError(f"Unsupported BLOCK syntax: {args}")
        name, placement = m.group(1), int(m.group(2))
        pkind, pargs = entities[placement]
        if pkind != "AXIS2_PLACEMENT_3D":
            raise ValueError(f"#{placement} is not an AXIS2_PLACEMENT_3D")
        loc_ref = re.findall(r"#(\d+)", pargs)[0]
        boxes.append(Box.from_origin_size(name, point(loc_ref), [m.group(3), m.group(4), m.group(5)]))
    return boxes


def load_layout(parts=None):
    """Return (boxes, source). ``parts`` is an optional JSON list overriding the sample."""
    if parts:
        return [Box.from_origin_size(p["id"], p["origin"], p["size"]) for p in parts], "request"
    return parse_step_boxes(SAMPLE_LAYOUT.read_text()), f"samples/{SAMPLE_LAYOUT.name}"


def overlap_volume(a, b):
    vol = 1.0
    for i in range(3):
        d = min(a.max[i], b.max[i]) - max(a.min[i], b.min[i])
        if d <= 0:  # separated or only touching faces
            return 0.0
        vol *= d
    return vol


def check(boxes, changed, neighbours=None):
    by_id = {b.id: b for b in boxes}
    if changed not in by_id:
        raise KeyError(changed)
    ids = neighbours or [i for i in by_id if i != changed]
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise KeyError(", ".join(missing))
    target = by_id[changed]
    results = []
    for nid in ids:
        if nid == changed:
            continue
        vol = overlap_volume(target, by_id[nid])
        results.append({"part_a": changed, "part_b": nid, "interferes": vol > 0, "overlap_volume": round(vol, 6)})
    return results
