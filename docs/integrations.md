# How enterprise systems expose data to Orbit (SCRUM-49)

Purpose: answer the customer's "how would Orbit get our data?" question for the four
systems named in discovery: **CATIA**, **Teamcenter**, **SharePoint** and **WIRS**.
This is based on well-established public vendor documentation (cited by name below).
Anything marked **To confirm with customer** depends on their version, licensing or IT
policy and must be checked in a technical call before we commit to an approach.

## What Orbit ingests today

Orbit's pipelines already accept these file types (see `bom_agent/bom_extraction.py`,
`part_history/importer.py`):

| Format | Used for |
| --- | --- |
| STEP (`.step`, `.stp`) | CAD geometry + assembly structure -> BOM rows |
| PDF | Drawings / spec sheets -> text extraction, BOM rows |
| XLSX / CSV | Cost history (part numbers, costs, suppliers) via `part_history/importer.py`. BOM spreadsheets are not yet a BOM input — a small mapping step is needed |

So the cheapest integration for every system is: **get the system to produce one of these
files and drop it where Orbit can read it** (a watched folder, Drive/SharePoint folder, or
upload). A live API connector is the second step, once the file path is proven.

## Connector interface (how a source plugs in)

Each source is a per-user `WorkspaceSource` row (`backend/part_history/models.py`,
Settings -> Workspace sources) with a `kind`, a `location` and a free-form `config`.
A connector for a new system only needs to:

1. **List** new or changed items at `location` since the last sync.
2. **Fetch** each item as bytes plus a filename (converting to STEP / PDF / XLSX / CSV
   if the system's native format isn't one Orbit reads).
3. **Hand off** to the existing upload path (`UploadedFile` + `build_bom` /
   `import_costs`), into the project the source is mapped to.
4. Respect `enabled` — disabled sources are skipped.

Credentials belong in the connector's own encrypted store (as Gmail tokens are today in
`bom_agent/gmail_integration.py`), never in `config`.

## CATIA (Dassault Systemes) — V5 and 3DEXPERIENCE

- **How data is exposed**
  - *File exports*: CATIA V5 natively saves `.CATPart` / `.CATProduct` / `.CATDrawing`
    (proprietary). It can export **STEP AP203/AP214 (and AP242 depending on licence)**,
    **IGES**, and drawings to **PDF**. A BOM can be exported from the product structure
    ("Bill of Material" in Assembly Design) to **XLS/TXT**.
  - *Automation*: CATIA V5 exposes a COM **Automation API** (VBA/VBScript/.NET macros,
    Windows only) and the C++ **CAA (Component Application Architecture)** SDK. Both can
    batch-export STEP and BOM files.
  - *3DEXPERIENCE*: data lives in the platform database, not on disk. Dassault documents
    **3DEXPERIENCE web services (REST, "3DSpace" / Enterprise Integration)** for
    reading objects and BOMs; exports to STEP are also available.
- **Auth model**: V5 is a desktop app (runs under the engineer's Windows login + licence
  server). 3DEXPERIENCE web services use the platform's **3DPassport** login (CAS/SSO);
  on-premise vs cloud matters.
- **Formats for Orbit**: STEP (geometry/assembly) + PDF (drawings) + XLSX (BOM).
- **Recommended path**: a scheduled CATIA macro (or manual "Save as STEP") into a watched
  folder -> Orbit `local_folder` source. Later: 3DEXPERIENCE REST connector.
- **To confirm with customer**: V5 vs 3DEXPERIENCE (and release), whether the STEP
  translator licence is installed, cloud vs on-prem, whether IT allows macros.
- **References**: Dassault Systemes *CATIA V5 Automation documentation* / *CAA V5 Encyclopedia*;
  *3DEXPERIENCE Platform web services developer documentation*.

## Teamcenter (Siemens Digital Industries Software)

- **How data is exposed**
  - **Teamcenter Services (SOA)**: the official client API (Java/C#/C++ bindings)
    used to query items, item revisions, BOM windows/BOM lines and datasets.
  - **REST**: newer releases (Active Workspace) expose REST/JSON endpoints for Active
    Workspace services. Availability depends on version — **to confirm with customer**.
  - **Exports**: **PLM XML** (Siemens' XML exchange format for structure + metadata),
    BOM export to **Excel** from Structure Manager / Active Workspace, and attached
    datasets (often STEP, JT, PDF). Siemens' **JT** is the common lightweight 3D
    format; Orbit does not read JT today, so request STEP datasets.
  - **Integration products**: T4S/T4EA (SAP/enterprise connectors) exist at many sites.
- **Auth model**: Teamcenter user/group/role; most enterprises front it with
  **Teamcenter Security Services (TcSS) SSO**. A dedicated service account with
  read-only access to the relevant projects is the normal ask.
- **Formats for Orbit**: BOM as XLSX/CSV (or PLM XML, which we'd convert), STEP and PDF
  datasets.
- **Recommended path**: scheduled BOM + dataset export into a folder -> `local_folder` /
  SharePoint source. Then a `plm` connector using Teamcenter Services to pull BOM lines.
- **To confirm with customer**: Teamcenter version, whether Active Workspace REST is
  enabled, whether a service account will be granted, dataset types stored (STEP vs JT only).
- **References**: Siemens *Teamcenter Services Guide* / *Services Reference*; *PLM XML
  schema documentation*; *Teamcenter Security Services* docs.

## SharePoint (Microsoft 365)

- **How data is exposed**: **Microsoft Graph API** — sites, document libraries (drives),
  drive items (files/folders, with download, delta/change tracking) and lists (list items
  + columns as metadata). Graph **delta queries** let a connector fetch only what changed.
  (The older SharePoint REST API and CSOM still exist; Graph is Microsoft's recommended path.)
- **Auth model**: **Microsoft Entra ID (Azure AD) app registration with OAuth 2.0**.
  Two options:
  - *Delegated* permissions (user signs in, e.g. `Files.Read.All`) — sees what the user sees.
  - *Application* permissions (client-credentials, e.g. `Sites.Read.All`, or the narrower
    **`Sites.Selected`** which limits the app to specific sites an admin grants). Requires
    tenant **admin consent**. `Sites.Selected` is what security teams usually prefer.
- **Formats for Orbit**: whatever is stored — typically PDF drawings, XLSX BOMs/cost
  sheets, STEP files. List metadata (part number, revision, status) maps to project/part fields.
- **Recommended path**: `google_drive`-style folder connector against a SharePoint document
  library using Graph delta; start with delegated permissions for the demo,
  `Sites.Selected` for production.
- **To confirm with customer**: which site/library, whether admin consent for an app
  registration is possible, any DLP / sensitivity-label restrictions.
- **References**: Microsoft Learn — *Microsoft Graph REST API v1.0: driveItem, list,
  listItem, delta*; *Microsoft Graph permissions reference*; *Sites.Selected permission*.

## WIRS (plant / legacy system)

WIRS is the customer's internal plant/legacy system; there is no public documentation, so
**almost everything here is to confirm with customer**.

- **Likely ways data comes out** (in order of preference):
  1. A built-in **report / export to CSV or Excel**.
  2. **Read-only database access** (or a nightly DB export / view) — typical for older
     in-house systems (SQL Server / Oracle are common; to confirm).
  3. A file drop it already produces for another system (e.g. an EDI/flat-file feed).
  4. If none of these exist: the **computer-use proof of concept** in
     [`computer-use-poc.md`](computer-use-poc.md), which clicks through the UI's export.
- **Auth model**: to confirm — likely Windows/AD login or app-local accounts.
- **Formats for Orbit**: CSV/XLSX into the cost-history importer or supplier list.
- **Questions for the customer**: what data in WIRS do they want in Orbit (cost history?
  supplier lists? work orders?), does it have an export button, who owns the database,
  and can we get a sample export.

## Summary

| System | Fastest path (demo) | Live connector (later) | Auth | Main unknowns |
| --- | --- | --- | --- | --- |
| CATIA | STEP/PDF/XLS export -> watched folder | 3DEXPERIENCE REST / CAA batch | Windows + licence; 3DPassport | V5 vs 3DX, STEP licence |
| Teamcenter | BOM XLSX + STEP datasets -> folder | Teamcenter Services (SOA) / AW REST | TcSS SSO, service account | Version, REST enabled, JT-only datasets |
| SharePoint | Sync a library folder | Microsoft Graph + delta | Entra ID OAuth (`Sites.Selected`) | Admin consent |
| WIRS | CSV export -> cost importer | DB view or computer-use agent | To confirm | Everything |
