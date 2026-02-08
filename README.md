# Orbit

> Agentic metadata extraction for mechanical engineering files.

## Overview
Orbit transforms raw engineering artifacts (CAD models, drawings, PDFs) into structured, verifiable metadata using an agent-based extraction and reconciliation pipeline.

## What It Does
- Extracts geometry, units, and identifiers from CAD
- Reads drawings for materials, revisions, notes
- Cross-validates data and flags conflicts
- Outputs canonical JSON + human-readable reports

## Supported Files
- CAD: STEP, IGES  
- Drawings: PDF, DXF  
- Scanned documents (OCR)

## Architecture
1. Tool-based extraction (CAD, PDF, OCR)  
2. Agentic merging and validation  
3. Structured outputs with provenance

## Output
- Engineering Profile Report
- Canonical JSON Profile (with confidence scores)

## Tech Stack
Python · OpenCascade · PDFPlumber · Tesseract · OpenCV · LLM (constrained)

## Status
MVP — single-part workflow

## Context
Built for CSB310 to explore agentic AI systems for engineering data.

## License
MIT
