"""SCRUM-37/38 — standards reference corpus and per-BOM-line compliance check.

The corpus (data/standards_corpus.json) is a small, hand-curated set of
paraphrased rule summaries. It is a triage aid: every finding carries the
corpus label telling the reader to verify against the official standard.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

CORPUS_PATH = Path(__file__).parent / "data" / "standards_corpus.json"

# Which BOM row fields each applies_to key is matched against. BomRow has no
# dedicated finish column, so finishes are read from spec/description/process.
SCOPE_FIELDS = {
    "material": ("material",),
    "finish": ("spec", "description", "process", "material"),
    "part_type": ("part_number", "description"),
    "keywords": ("part_number", "description", "material", "process", "spec"),
}
OUTCOMES = ("pass", "warning", "needs_info")
SEVERITIES = ("info", "low", "medium", "high")
STATUS_RANK = {"pass": 0, "needs_info": 1, "warning": 2}


@dataclass(frozen=True)
class StandardRule:
    id: str
    title: str
    citation: str
    applies_to: dict[str, tuple[str, ...]]
    outcome: str
    severity: str
    explanation: str
    requires: dict | None = None

    def matches(self, row: dict) -> bool:
        for scope, patterns in self.applies_to.items():
            text = " ".join(str(row.get(f) or "") for f in SCOPE_FIELDS[scope])
            if any(re.search(p, text, re.IGNORECASE) for p in patterns):
                return True
        return False

    def missing_requirement(self, row: dict) -> str | None:
        if not self.requires:
            return None
        text = " ".join(str(row.get(f) or "") for f in self.requires["fields"])
        return None if re.search(self.requires["pattern"], text, re.IGNORECASE) else self.requires["missing"]

    def as_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "citation": self.citation,
            "applies_to": {k: list(v) for k, v in self.applies_to.items()},
            "outcome": self.outcome, "severity": self.severity, "explanation": self.explanation,
        }


@dataclass(frozen=True)
class Corpus:
    label: str
    version: str
    notes: str
    rules: tuple[StandardRule, ...] = field(default_factory=tuple)


def parse_corpus(data: dict) -> Corpus:
    rules = []
    for raw in data["rules"]:
        applies = {k: tuple(v) for k, v in raw["applies_to"].items()}
        if not applies or set(applies) - set(SCOPE_FIELDS):
            raise ValueError(f"Rule {raw.get('id')}: applies_to keys must be among {sorted(SCOPE_FIELDS)}")
        if raw["outcome"] not in OUTCOMES or raw["severity"] not in SEVERITIES:
            raise ValueError(f"Rule {raw['id']}: bad outcome or severity")
        for p in (*[p for ps in applies.values() for p in ps], *([raw["requires"]["pattern"]] if raw.get("requires") else [])):
            re.compile(p)
        rules.append(StandardRule(
            id=raw["id"], title=raw["title"], citation=raw["citation"], applies_to=applies,
            outcome=raw["outcome"], severity=raw["severity"], explanation=raw["explanation"],
            requires=raw.get("requires"),
        ))
    ids = [r.id for r in rules]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate rule ids in the standards corpus")
    return Corpus(label=data["label"], version=data["version"], notes=data.get("notes", ""), rules=tuple(rules))


@lru_cache(maxsize=1)
def load_corpus() -> Corpus:
    return parse_corpus(json.loads(CORPUS_PATH.read_text()))


def check_row(row: dict, corpus: Corpus | None = None) -> dict:
    """Findings for one BOM row (a dict with BomRow's fields)."""
    corpus = corpus or load_corpus()
    findings = []
    if not (row.get("material") or "").strip():
        findings.append({
            "status": "needs_info", "rule": None, "severity": "medium",
            "message": "No material stated — material and finish rules can't be checked.",
        })
    for rule in corpus.rules:
        if not rule.matches(row):
            continue
        missing = rule.missing_requirement(row)
        status = "needs_info" if missing else rule.outcome
        findings.append({
            "status": status,
            "rule": {"id": rule.id, "title": rule.title, "citation": rule.citation, "explanation": rule.explanation},
            "severity": rule.severity,
            "message": missing or rule.title,
        })
    if not findings:
        findings.append({
            "status": "needs_info", "rule": None, "severity": "info",
            "message": "No rule in the reference corpus covers this line — check it manually.",
        })
    status = max((f["status"] for f in findings), key=STATUS_RANK.__getitem__)
    return {"status": status, "findings": findings}


def check_bom(bom) -> dict:
    corpus = load_corpus()
    lines, summary = [], {s: 0 for s in OUTCOMES}
    for row in bom.rows.all():
        data = {f: getattr(row, f) for f in ("part_number", "description", "material", "process", "spec")}
        result = check_row(data, corpus)
        summary[result["status"]] += 1
        lines.append({"row_id": row.pk, "line_no": row.line_no, "part_number": row.part_number, **result})
    return {
        "bom_id": bom.pk, "reference": bom.reference,
        "corpus": {"label": corpus.label, "version": corpus.version},
        "summary": summary, "lines": lines,
    }
