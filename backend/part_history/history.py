"""Writing to and querying part/price history (SCRUM-28)."""

from django.db.models import Q

from .models import Part, Quote, Supplier


def record_research_quote(supplier_quote) -> Quote:
    """Keep a quote found by a BOM research run so the next run can learn from it."""
    item = supplier_quote.line_item
    run = item.run
    owner = run.created_by
    supplier, _ = Supplier.objects.get_or_create(
        workspace_owner=owner, name=supplier_quote.supplier_name.strip()
    )
    if supplier_quote.is_avl and not supplier.is_approved:
        supplier.is_approved = True
        supplier.approval_note = "On the AVL (BOM research)"
        supplier.save(update_fields=["is_approved", "approval_note"])
    part = None
    if item.part_number:
        part, _ = Part.objects.get_or_create(
            workspace_owner=owner,
            part_number=item.part_number,
            defaults={"description": item.part_name, "material": item.material_spec},
        )
    return Quote.objects.create(
        workspace_owner=owner,
        supplier=supplier,
        part=part,
        material=item.material_spec,
        unit_price=supplier_quote.unit_price,
        quantity=supplier_quote.moq,
        lead_time_days=supplier_quote.lead_time_days,
        program=run.project.name,
        source=f"BOM research run #{run.pk}",
    )


def record_bom_parts(bom, owner) -> int:
    """Add an approved BOM's part numbers to history; existing values are only filled in, never overwritten."""
    count = 0
    for row in bom.rows.exclude(part_number=""):
        part, created = Part.objects.get_or_create(
            workspace_owner=owner,
            part_number=row.part_number,
            defaults={"description": row.description, "material": row.material, "process": row.process},
        )
        if not created:
            changed = [f for f in ("description", "material", "process") if not getattr(part, f) and getattr(row, f)]
            for field in changed:
                setattr(part, field, getattr(row, field))
            if changed:
                part.save(update_fields=[*changed, "updated_at"])
        count += 1
    return count


def suppliers_who_quoted(owner, *, material="", tolerance="", certification="", part_number="") -> list[dict]:
    """Answer "which suppliers have quoted this before", with the quotes as evidence."""
    quotes = Quote.objects.filter(workspace_owner=owner).select_related("supplier", "part")
    if material:
        quotes = quotes.filter(material__icontains=material)
    if tolerance:
        quotes = quotes.filter(tolerance__icontains=tolerance)
    if certification:
        quotes = quotes.filter(
            Q(certifications__icontains=certification) | Q(supplier__certifications__icontains=certification)
        )
    if part_number:
        quotes = quotes.filter(part__part_number__iexact=part_number)

    by_supplier: dict[int, dict] = {}
    for q in quotes:
        entry = by_supplier.setdefault(
            q.supplier_id,
            {
                "supplier_id": q.supplier_id,
                "supplier": q.supplier.name,
                "is_approved": q.supplier.is_approved,
                "certifications": q.supplier.certifications,
                "quotes": [],
            },
        )
        entry["quotes"].append(
            {
                "id": q.id,
                "part_number": q.part.part_number if q.part else "",
                "material": q.material,
                "tolerance": q.tolerance,
                "unit_price": str(q.unit_price),
                "currency": q.currency,
                "lead_time_days": q.lead_time_days,
                "quoted_at": q.quoted_at.isoformat(),
                "source": q.source,
            }
        )
    return sorted(by_supplier.values(), key=lambda e: (-len(e["quotes"]), e["supplier"]))
