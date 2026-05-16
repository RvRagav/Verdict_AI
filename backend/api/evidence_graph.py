"""Evidence Graph API — visual provenance map for one evaluation cell.

Returns the complete chain of evidence: criterion → bidder → source docs →
extracted values → branches → verdict → dissent → anomalies → officer decision.

Each node has: id, type, label, data (type-specific payload).
Each edge has: source, target, label.

The frontend renders this as an interactive graph.
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import get_db


router = APIRouter(prefix="/evaluations/{evaluation_id}/evidence-graph", tags=["evidence-graph"])


@router.get("")
def get_evidence_graph(evaluation_id: str, conn=Depends(get_db)):
    """Assemble the full provenance graph for one evaluation cell."""

    # Load the evaluation
    ev = conn.execute(
        """SELECT e.*, c.criterion_text, c.criterion_type, c.threshold_value,
                  c.is_mandatory, c.source_clause_ref, c.source_page as criterion_page,
                  b.company_name, b.pan_number, b.gstin
           FROM evaluations e
           JOIN criteria c ON c.id = e.criterion_id
           JOIN bidders b ON b.id = e.bidder_id
           WHERE e.id = ?""",
        (evaluation_id,),
    ).fetchone()

    if not ev:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    ev = dict(ev)
    nodes = []
    edges = []

    # ─── Node 1: Criterion ───────────────────────────────────────────
    nodes.append({
        "id": "criterion",
        "type": "criterion",
        "label": ev["criterion_text"][:80],
        "data": {
            "full_text": ev["criterion_text"],
            "type": ev["criterion_type"],
            "mandatory": bool(ev["is_mandatory"]),
            "threshold": _safe_json(ev.get("threshold_value")),
            "clause_ref": ev.get("source_clause_ref"),
            "page": ev.get("criterion_page"),
        },
    })

    # ─── Node 2: Bidder ──────────────────────────────────────────────
    nodes.append({
        "id": "bidder",
        "type": "bidder",
        "label": ev["company_name"],
        "data": {
            "pan": ev.get("pan_number"),
            "gstin": ev.get("gstin"),
        },
    })
    edges.append({"source": "criterion", "target": "bidder", "label": "evaluated against"})

    # ─── Node 3: Source Document ─────────────────────────────────────
    if ev.get("source_doc_id"):
        doc = conn.execute(
            "SELECT id, filename, doc_type, page_count, avg_ocr_conf FROM documents WHERE id = ?",
            (ev["source_doc_id"],),
        ).fetchone()
        if doc:
            nodes.append({
                "id": "source_doc",
                "type": "document",
                "label": f"{doc['filename']} (p.{ev.get('source_page', '?')})",
                "data": {
                    "doc_id": doc["id"],
                    "filename": doc["filename"],
                    "doc_type": doc["doc_type"],
                    "page": ev.get("source_page"),
                    "ocr_confidence": doc["avg_ocr_conf"],
                    "bbox": _safe_json(ev.get("source_bbox")),
                },
            })
            edges.append({"source": "bidder", "target": "source_doc", "label": "evidence from"})

    # ─── Node 4: Extracted Value ─────────────────────────────────────
    extracted = _safe_json(ev.get("extracted_value"))
    if extracted:
        figures = extracted.get("figures") if isinstance(extracted, dict) else None
        if figures:
            label_parts = []
            for fig in figures[:3]:
                if isinstance(fig, dict) and fig.get("rupees"):
                    label_parts.append(f"{fig.get('period_label', '')}: ₹{fig['rupees']/1e7:.1f} Cr")
            label = " · ".join(label_parts) if label_parts else str(extracted)[:60]
        else:
            label = str(extracted)[:60]

        nodes.append({
            "id": "extracted_value",
            "type": "value",
            "label": label,
            "data": extracted,
        })
        edges.append({"source": "source_doc", "target": "extracted_value", "label": "extracted"})
    else:
        nodes.append({
            "id": "extracted_value",
            "type": "value",
            "label": "No value extracted",
            "data": {"missing": True},
        })
        if ev.get("source_doc_id"):
            edges.append({"source": "source_doc", "target": "extracted_value", "label": "not found in"})
        else:
            edges.append({"source": "bidder", "target": "extracted_value", "label": "no evidence"})

    # ─── Node 5: Rules Branch ────────────────────────────────────────
    rules = _safe_json(ev.get("rules_branch"))
    if rules:
        nodes.append({
            "id": "rules_branch",
            "type": "branch",
            "label": f"Rules: {rules.get('method', 'regex')} → {rules.get('verdict', '?')}",
            "data": rules,
        })
        edges.append({"source": "extracted_value", "target": "rules_branch", "label": "rules analysis"})

    # ─── Node 6: LLM Branch ─────────────────────────────────────────
    llm = _safe_json(ev.get("llm_branch"))
    if llm:
        nodes.append({
            "id": "llm_branch",
            "type": "branch",
            "label": f"LLM: {llm.get('verdict', '?')} ({int(llm.get('confidence', 0)*100)}%)",
            "data": llm,
        })
        edges.append({"source": "extracted_value", "target": "llm_branch", "label": "LLM analysis"})

    # ─── Node 7: Verdict ─────────────────────────────────────────────
    conf = int(ev["confidence"] * 100)
    nodes.append({
        "id": "verdict",
        "type": "verdict",
        "label": f"{ev['verdict']} ({conf}%)",
        "data": {
            "verdict": ev["verdict"],
            "confidence": ev["confidence"],
            "route": ev["route"],
            "breakdown": _safe_json(ev.get("confidence_breakdown")),
        },
    })
    if rules:
        edges.append({"source": "rules_branch", "target": "verdict", "label": "contributes"})
    if llm:
        edges.append({"source": "llm_branch", "target": "verdict", "label": "contributes"})
    if not rules and not llm:
        edges.append({"source": "extracted_value", "target": "verdict", "label": "determines"})

    # ─── Node 8: Dissent ─────────────────────────────────────────────
    dissent = _safe_json(ev.get("dissent_branch"))
    if dissent and dissent.get("dissent"):
        nodes.append({
            "id": "dissent",
            "type": "dissent",
            "label": f"Dissent ({dissent.get('severity', '?')})",
            "data": {
                "text": dissent["dissent"][:200],
                "severity": dissent.get("severity"),
                "suggested_check": dissent.get("suggested_check"),
            },
        })
        edges.append({"source": "verdict", "target": "dissent", "label": "challenged by"})

    # ─── Node 9: Anomalies ───────────────────────────────────────────
    anomalies = conn.execute(
        "SELECT flag_type, severity, message FROM anomaly_flags "
        "WHERE evaluation_id = ? OR (tender_id = ? AND bidder_id = ?)",
        (evaluation_id, ev["tender_id"], ev["bidder_id"]),
    ).fetchall()
    if anomalies:
        for i, a in enumerate(anomalies[:5]):
            node_id = f"anomaly_{i}"
            nodes.append({
                "id": node_id,
                "type": "anomaly",
                "label": f"{a['flag_type'].replace('_', ' ')} ({a['severity']})",
                "data": {
                    "flag_type": a["flag_type"],
                    "severity": a["severity"],
                    "message": a["message"][:150],
                },
            })
            edges.append({"source": "verdict", "target": node_id, "label": "flagged"})

    # ─── Node 10: Officer Decision ───────────────────────────────────
    if ev.get("officer_decision"):
        officer = conn.execute(
            "SELECT name, role FROM officers WHERE id = ?",
            (ev.get("officer_id"),),
        ).fetchone()
        nodes.append({
            "id": "officer_decision",
            "type": "decision",
            "label": f"{ev['officer_decision'].title()} by {officer['name'] if officer else ev.get('officer_id')}",
            "data": {
                "decision": ev["officer_decision"],
                "officer": officer["name"] if officer else ev.get("officer_id"),
                "role": officer["role"] if officer else None,
                "reason": ev.get("reason_text"),
                "decided_at": ev.get("decided_at"),
            },
        })
        edges.append({"source": "verdict", "target": "officer_decision", "label": "decided"})

    # ─── Node 11: Comments ───────────────────────────────────────────
    comments = conn.execute(
        "SELECT c.body, c.created_at, o.name FROM officer_comments c "
        "JOIN officers o ON o.id = c.officer_id "
        "WHERE c.evaluation_id = ? ORDER BY c.created_at",
        (evaluation_id,),
    ).fetchall()
    if comments:
        nodes.append({
            "id": "comments",
            "type": "comments",
            "label": f"{len(comments)} officer note(s)",
            "data": {
                "count": len(comments),
                "latest": comments[-1]["body"][:100] if comments else None,
                "by": comments[-1]["name"] if comments else None,
            },
        })
        edges.append({"source": "officer_decision" if ev.get("officer_decision") else "verdict", "target": "comments", "label": "annotated"})

    return {
        "evaluation_id": evaluation_id,
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "tender_id": ev["tender_id"],
            "bidder_id": ev["bidder_id"],
            "criterion_id": ev["criterion_id"],
            "pipeline_signature": ev.get("pipeline_signature_hash"),
        },
    }


def _safe_json(val):
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None
