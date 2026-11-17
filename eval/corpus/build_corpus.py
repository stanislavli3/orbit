"""Build the SYNTHETIC evaluation corpus files (deterministic; re-running gives identical bytes).

The repo's samples/ hold three STEP files, two MATLAB files and two CSVs but no
PDF. Real drawings are not available (NDA / §11), so this script writes six
synthetic files that restate facts already present in samples/ the way a
drawing or a single-part export would carry them:

  S01  rev B BOM table drawing (from samples/bracket_assembly_rev_b.step)
  S02  pump assembly BOM table, abbreviated headers (parts from part_cost_history_sample.csv)
  S03  title-block-only drawing of ORB-1042 rev B
  S04  title-block-only drawing of ORB-1130 (DWG NO / MATL abbreviations)
  S05  spacer kit BOM with drafter conventions ("2 EA", "A/R", "STAINLESS STEEL 316")
  S06  single-part STEP export of ORB-2002 with material and revision

Limits, stated wherever results are reported: the PDFs are generated text
PDFs (no vector geometry, no scanned images), written by the same person who
read the extractor, so they cannot stand in for a customer's files.

Run:  python eval/corpus/build_corpus.py
"""

from pathlib import Path

OUT = Path(__file__).resolve().parent / "files"


def make_pdf(items, size=(612, 792)) -> bytes:
    """One-page PDF with Helvetica text drawn at (x, y). Byte-for-byte deterministic."""
    esc = lambda t: t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")  # noqa: E731
    content = "BT /F1 9 Tf " + " ".join(f"1 0 0 1 {x} {y} Tm ({esc(t)}) Tj" for x, y, t in items) + " ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {size[0]} {size[1]}] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = "%PDF-1.4\n", []
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF"
    return out.encode("latin-1")


def table(rows, columns, top=700, step=14):
    return [(x, top - i * step, text) for i, row in enumerate(rows) for x, text in zip(columns, row)]


def title_block(lines, x=380, top=130, step=13):
    return [(x, top - i * step, text) for i, text in enumerate(lines)]


def drawing_frame(title):
    """Text a real drawing sheet also carries; the extractor has to ignore it."""
    return [
        (40, 760, "SYNTHETIC EVALUATION DRAWING - ORBIT BIS 372 - NOT A CUSTOMER FILE"),
        (40, 746, title),
        (40, 40, "UNLESS OTHERWISE SPECIFIED DIMENSIONS ARE IN MM. TOLERANCES: X.X +/-0.2  X.XX +/-0.05"),
        (40, 28, "THIRD ANGLE PROJECTION    SCALE 1:1    SHEET 1 OF 1"),
    ]


COLS6 = [40, 80, 160, 330, 380, 470]

FILES = {
    "S01_bracket_rev_b_drawing_bom.pdf": lambda: make_pdf(
        drawing_frame("BRACKET ASSEMBLY ORB-1000 REV B - PARTS LIST")
        + table([
            ("ITEM", "PART NO", "DESCRIPTION", "QTY", "MATERIAL", "REV"),
            ("1", "ORB-1042", "BRACKET, MOUNTING", "1", "AL 7075-T6", "B"),
            ("2", "ORB-1043", "COVER PLATE 16 GA", "1", "CRS", "A"),
            ("3", "SHCS-M6X16", "SCREW SHCS M6X16 ISO 4762", "4", "SS 304", "-"),
            ("4", "ORB-1044", "GUSSET", "1", "AL 6061-T6", "A"),
            ("5", "ORB-1050", "CABLE CLIP", "1", "PA66", "A"),
        ], COLS6)
    ),
    "S02_pump_assembly_bom.pdf": lambda: make_pdf(
        drawing_frame("PUMP ASSEMBLY - BILL OF MATERIALS")
        + table([
            ("ITEM", "P/N", "DESC", "QTY", "MATL"),
            ("1", "ORB-2001", "HOUSING, PUMP", "1", "A380 CAST"),
            ("2", "ORB-2002", "SHAFT", "1", "4140"),
            ("3", "SHCS-M6X20", "SCREW SHCS M6X20 ISO 4762", "6", "SS 304"),
        ], COLS6[:5])
    ),
    "S03_bracket_mounting_title_block.pdf": lambda: make_pdf(
        drawing_frame("DETAIL DRAWING")
        + title_block(["TITLE: BRACKET, MOUNTING", "PART NO: ORB-1042", "MATERIAL: AL 7075-T6",
                       "REV: B", "FINISH: CLEAR ANODIZE"])
    ),
    "S04_cover_plate_title_block.pdf": lambda: make_pdf(
        drawing_frame("DETAIL DRAWING")
        + title_block(["TITLE: COVER PLATE 16 GA", "DWG NO: ORB-1130", "MATL: CRS", "REV: C"])
    ),
    "S05_spacer_kit_bom.pdf": lambda: make_pdf(
        drawing_frame("SPACER KIT - PARTS LIST")
        + table([
            ("ITEM", "PART NUMBER", "DESCRIPTION", "QTY", "MATERIAL"),
            ("1", "ORB-0770", "SPACER, 10 MM", "2 EA", "AL 6061-T6"),
            ("2", "ORB-0771", "SPACER, 12 MM", "2 EA", "AL 6061-T6"),
            ("3", "LT-243", "THREADLOCKER, MEDIUM", "A/R", "-"),
        ], COLS6[:5])
    ),
    "S06_shaft_single_part.step": lambda: (
        "ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('Shaft - synthetic evaluation file'),'2;1');\n"
        "FILE_NAME('S06_shaft_single_part.step','2026-11-17T00:00:00',('Orbit eval'),(''),'','','');\n"
        "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\nENDSEC;\nDATA;\n"
        "#1=APPLICATION_CONTEXT('automotive design');\n#2=PRODUCT_CONTEXT('',#1,'mechanical');\n"
        "#3=PRODUCT_DEFINITION_CONTEXT('part definition',#1,'design');\n"
        "#10=PRODUCT('ORB-2002','Shaft','Drive shaft',(#2));\n"
        "#11=PRODUCT_DEFINITION_FORMATION('C','',#10);\n"
        "#12=PRODUCT_DEFINITION('design','',#11,#3);\n"
        "#13=PRODUCT_DEFINITION_SHAPE('','',#12);\n"
        "#14=MATERIAL_DESIGNATION('AISI 4140',(#13));\nENDSEC;\nEND-ISO-10303-21;\n"
    ).encode(),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, build in FILES.items():
        (OUT / name).write_bytes(build())
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
