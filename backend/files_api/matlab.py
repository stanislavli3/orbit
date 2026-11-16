"""
MATLAB file metadata parsers (no SciPy dependency).

* ``.mat`` — a minimal MAT-file Level 5 reader: walks the top-level data
  elements (inflating ``miCOMPRESSED`` ones) and reports each variable's
  name, MATLAB class and shape. Values are never decoded.
* ``.m`` — function signatures (incl. local functions) and the leading
  ``%`` help-comment block.

Malformed input raises :class:`MatlabParseError` with a human-readable reason.
"""

import re
import struct
import zlib
from datetime import datetime, timezone


class MatlabParseError(ValueError):
    pass


MI_INT8, MI_UINT32, MI_INT32, MI_MATRIX, MI_COMPRESSED = 1, 6, 5, 14, 15

MX_CLASSES = {
    1: "cell", 2: "struct", 3: "object", 4: "char", 5: "sparse",
    6: "double", 7: "single", 8: "int8", 9: "uint8", 10: "int16",
    11: "uint16", 12: "int32", 13: "uint32", 14: "int64", 15: "uint64",
}

MAX_VARIABLES = 500


def _read_tag(buf: bytes, pos: int, endian: str) -> tuple[int, int, int, bool]:
    """Return (type, nbytes, data_start, is_small)."""
    if pos + 8 > len(buf):
        raise MatlabParseError("Truncated data element tag.")
    first, second = struct.unpack_from(endian + "II", buf, pos)
    if first >> 16:  # small data element: 2-byte size + 2-byte type, data inline
        return first & 0xFFFF, first >> 16, pos + 4, True
    return first, second, pos + 8, False


def _sub_element(buf: bytes, pos: int, endian: str) -> tuple[int, bytes, int]:
    """Read one sub-element; return (type, payload, next_pos) with 8-byte padding."""
    dtype, nbytes, start, small = _read_tag(buf, pos, endian)
    end = start + nbytes
    if end > len(buf):
        raise MatlabParseError("Data element runs past end of file.")
    nxt = pos + 8 if small else start + ((nbytes + 7) // 8) * 8
    return dtype, buf[start:end], nxt


def _parse_matrix(body: bytes, endian: str) -> dict:
    """Parse the header sub-elements of an miMATRIX element body."""
    if not body:
        return {"name": "", "class": "empty", "shape": [0, 0]}
    dtype, flags, pos = _sub_element(body, 0, endian)
    if dtype != MI_UINT32 or len(flags) < 4:
        raise MatlabParseError("miMATRIX element is missing its array-flags sub-element.")
    flag_word = struct.unpack_from(endian + "I", flags, 0)[0]
    class_id = flag_word & 0xFF
    dtype, dims_raw, pos = _sub_element(body, pos, endian)
    if dtype != MI_INT32 or len(dims_raw) % 4:
        raise MatlabParseError("miMATRIX element has an invalid dimensions sub-element.")
    shape = list(struct.unpack(endian + "i" * (len(dims_raw) // 4), dims_raw))
    dtype, name_raw, pos = _sub_element(body, pos, endian)
    if dtype != MI_INT8:
        raise MatlabParseError("miMATRIX element has an invalid name sub-element.")
    info = {
        "name": name_raw.decode("ascii", errors="replace"),
        "class": MX_CLASSES.get(class_id, f"unknown({class_id})"),
        "shape": shape,
    }
    if flag_word & 0x800:
        info["complex"] = True
    if flag_word & 0x200:
        info["logical"] = True
    return info


def parse_mat(file_bytes: bytes) -> dict:
    if len(file_bytes) < 128:
        raise MatlabParseError("File is too small to be a MAT-file (header is 128 bytes).")
    header_text = file_bytes[:116].decode("latin-1").rstrip("\x00 ")
    if not header_text.startswith("MATLAB"):
        raise MatlabParseError(
            "Not a MAT-file v5 header (MAT v4 or non-MATLAB data is not supported)."
        )
    if "7.3" in header_text[:20] or file_bytes[512:516] == b"\x89HDF":
        raise MatlabParseError(
            "MAT v7.3 files are HDF5 containers and are not supported; re-save with -v7."
        )
    endian_marker = file_bytes[126:128]
    if endian_marker == b"IM":
        endian = "<"
    elif endian_marker == b"MI":
        endian = ">"
    else:
        raise MatlabParseError("Invalid endian indicator in MAT-file header.")

    variables: list[dict] = []
    warnings: list[str] = []
    pos = 128
    while pos < len(file_bytes) and len(variables) < MAX_VARIABLES:
        if len(file_bytes) - pos < 8:
            break  # trailing padding
        dtype, payload, nxt = _sub_element(file_bytes, pos, endian)
        if dtype == MI_COMPRESSED:
            try:
                inner = zlib.decompressobj().decompress(payload)
            except zlib.error as exc:
                raise MatlabParseError(f"Compressed variable could not be inflated: {exc}")
            itype, ipayload, _ = _sub_element(inner, 0, endian)
            if itype == MI_MATRIX:
                variables.append(_parse_matrix(ipayload, endian))
        elif dtype == MI_MATRIX:
            variables.append(_parse_matrix(payload, endian))
        else:
            warnings.append(f"Skipped top-level element of type {dtype}.")
        # MATLAB does not pad compressed elements to 8 bytes.
        pos = pos + 8 + len(payload) if dtype == MI_COMPRESSED else nxt
    if len(variables) >= MAX_VARIABLES:
        warnings.append(f"Stopped after {MAX_VARIABLES} variables.")

    return {
        "format": "matlab_mat",
        "mat_header": header_text,
        "variables": variables,
        "file_description": ", ".join(
            f"{v['name']} ({v['class']} {'x'.join(map(str, v['shape']))})" for v in variables[:10]
        ) or "MAT-file with no variables",
        "schema": None,
        "units_hint": None,
        "confidence": 0.9 if variables else 0.5,
        "warnings": warnings,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }


_FUNC_RE = re.compile(
    r"^\s*function\s+(?:(\[[^\]]*\]|\w+)\s*=\s*)?([A-Za-z]\w*(?:\.\w+)?)\s*(\([^)]*\))?",
    re.MULTILINE,
)


def parse_m(file_bytes: bytes) -> dict:
    if b"\x00" in file_bytes[:4096]:
        raise MatlabParseError("File contains binary data; not a MATLAB .m text file.")
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    functions = []
    for m in _FUNC_RE.finditer(text):
        outputs = (m.group(1) or "").strip("[] ")
        inputs = (m.group(3) or "").strip("() ")
        functions.append({
            "name": m.group(2),
            "inputs": [a.strip() for a in inputs.split(",") if a.strip()],
            "outputs": [a.strip() for a in re.split(r"[,\s]+", outputs) if a.strip()],
            "signature": m.group(0).strip(),
        })

    # Help text: first contiguous block of % comments (after an optional function line).
    header: list[str] = []
    started = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("%"):
            started = True
            header.append(s.lstrip("%").strip())
        elif started or (s and not s.startswith("function")):
            break
    header_comment = "\n".join(header).strip()

    if not functions and not header_comment and not text.strip():
        raise MatlabParseError("Empty .m file.")
    return {
        "format": "matlab_m",
        "kind": "function" if functions else "script",
        "functions": functions,
        "header_comment": header_comment,
        "file_description": (header_comment.splitlines() or [""])[0] or (
            functions[0]["signature"] if functions else "MATLAB script"
        ),
        "schema": None,
        "units_hint": None,
        "confidence": 0.85 if functions or header_comment else 0.5,
        "warnings": [],
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }


def write_mat_v5(variables: dict[str, list[list[float]]], compress: bool = False) -> bytes:
    """Write a tiny MAT v5 file of 2-D double matrices (used for samples/tests)."""
    def element(dtype: int, data: bytes) -> bytes:
        pad = (-len(data)) % 8
        return struct.pack("<II", dtype, len(data)) + data + b"\x00" * pad

    out = bytearray(b"MATLAB 5.0 MAT-file, Platform: Orbit sample".ljust(116, b" "))
    out += b"\x00" * 8 + struct.pack("<H", 0x0100) + b"IM"
    for name, rows in variables.items():
        nrows, ncols = len(rows), len(rows[0]) if rows else 0
        values = [rows[r][c] for c in range(ncols) for r in range(nrows)]  # column-major
        body = (
            element(MI_UINT32, struct.pack("<II", 6, 0))
            + element(MI_INT32, struct.pack("<ii", nrows, ncols))
            + element(MI_INT8, name.encode())
            + element(9, struct.pack("<" + "d" * len(values), *values))  # miDOUBLE
        )
        matrix = element(MI_MATRIX, body)
        if compress:
            z = zlib.compress(matrix)
            out += struct.pack("<II", MI_COMPRESSED, len(z)) + z
        else:
            out += matrix
    return bytes(out)
