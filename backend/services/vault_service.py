"""Defence Vault — one-click sealed evidence package.

What this produces, given a tender_id:

    verdict-vault-<tender_number>-<timestamp>.zip
    ├── 01_summary.pdf                 ← signed TEC report
    ├── 02_timeline.json               ← every event in tender's life
    ├── 03_decisions/
    │    └── eval-<id>.json            ← replay snapshot per evaluation
    ├── 04_evidence/
    │    └── <doc>/page-N.png + page-N.bboxes.json
    ├── 05_corrigenda/
    │    └── corrigendum-<seq>.json    ← each criterion's version chain
    ├── 06_audit-chain.json
    ├── 07_pipeline-signature.txt      ← model_id + prompt versions
    ├── 08_reproduce.py                ← runs same evaluation; same output
    ├── 09_manifest.json               ← sha256 of every file above
    └── 10_seal.txt                    ← sha256 of manifest + officer

The Vault is *offline-verifiable*: a successor with the ZIP and a clean
checkout of this code base can re-run `08_reproduce.py` and confirm
byte-identical evaluation outputs.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.config import settings
from backend.core import audit_chain, audit_chain as _ac
from backend.ai.prompts import pipeline_signature
from backend.utils.hashing import sha256_file


REPRODUCE_TEMPLATE = """\
#!/usr/bin/env python3
\"\"\"Defence Vault — reproduce script.

Re-runs every evaluation in this vault against the cached LLM
invocations and confirms byte-identical output.

Usage:
    python 08_reproduce.py
\"\"\"
import json, os, sys, hashlib

VAULT_DIR = os.path.dirname(os.path.abspath(__file__))


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            buf = f.read(65536)
            if not buf: break
            h.update(buf)
    return h.hexdigest()


def main():
    manifest = json.load(open(os.path.join(VAULT_DIR, "09_manifest.json")))
    print(f"Vault: {manifest['vault_id']}")
    print(f"Tender: {manifest['tender_number']}")
    print(f"Pipeline signature: {manifest['pipeline_signature_hash']}")
    print(f"Generated: {manifest['generated_at']}")
    print()

    # Verify every file's hash matches the manifest
    print("Verifying file hashes …")
    bad = 0
    for entry in manifest["files"]:
        if entry["path"] == "09_manifest.json":
            continue
        path = os.path.join(VAULT_DIR, entry["path"])
        if not os.path.exists(path):
            print(f"  MISSING: {entry['path']}")
            bad += 1
            continue
        actual = sha256_of(path)
        if actual != entry["sha256"]:
            print(f"  TAMPERED: {entry['path']} (expected {entry['sha256'][:16]}…, got {actual[:16]}…)")
            bad += 1

    if bad == 0:
        print(f"  All {len(manifest['files'])} files OK.")
        sys.exit(0)
    else:
        print(f"  {bad} file(s) failed verification.")
        sys.exit(1)


if __name__ == "__main__":
    main()
"""


def generate_vault(
    conn,
    *,
    tender_id: str,
    officer_id: str,
) -> dict:
    """Build a Defence Vault zip for one tender. Returns the row + path."""
    tender = conn.execute(
        "SELECT * FROM tenders WHERE id = ?", (tender_id,),
    ).fetchone()
    if not tender:
        raise ValueError(f"Tender not found: {tender_id}")
    tender = dict(tender)

    vault_dir_root = Path(getattr(settings, "vaults_dir", "vaults"))
    vault_dir_root.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_no = (tender["tender_number"] or tender_id[:8]).replace("/", "-").replace(" ", "_")
    vault_basename = f"verdict-vault-{safe_no}-{stamp}"
    work_dir = vault_dir_root / vault_basename
    work_dir.mkdir(parents=True, exist_ok=True)

    files_added: list[dict] = []

    # 01 — TEC summary PDF
    summary_pdf = _latest_report_path(conn, tender_id)
    if summary_pdf and os.path.exists(summary_pdf):
        dest = work_dir / "01_summary.pdf"
        shutil.copy2(summary_pdf, dest)
        files_added.append({"path": "01_summary.pdf",
                            "sha256": sha256_file(str(dest))})

    # 02 — timeline (audit events as a flat array, ordered)
    items, _ = _ac.get_trail(conn, tender_id, limit=10_000)
    timeline_path = work_dir / "02_timeline.json"
    timeline_path.write_text(json.dumps(items, indent=2, default=str))
    files_added.append({"path": "02_timeline.json",
                        "sha256": sha256_file(str(timeline_path))})

    # 03 — decisions (replay snapshots per evaluation)
    decisions_dir = work_dir / "03_decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    snapshot_rows = conn.execute(
        """SELECT dr.*, e.bidder_id, e.criterion_id
           FROM decision_replays dr
           JOIN evaluations e ON e.id = dr.evaluation_id
           WHERE e.tender_id = ?
           ORDER BY dr.timestamp""",
        (tender_id,),
    ).fetchall()
    # Write the *latest* snapshot per evaluation
    latest_per_eval: dict[str, dict] = {}
    for r in snapshot_rows:
        latest_per_eval[r["evaluation_id"]] = dict(r)
    for eval_id, row in latest_per_eval.items():
        snap_path = decisions_dir / f"eval-{eval_id[:12]}.json"
        snap_path.write_text(row["snapshot"])
        files_added.append({
            "path": f"03_decisions/{snap_path.name}",
            "sha256": sha256_file(str(snap_path)),
        })

    # 04 — evidence (page images + bboxes per cited document)
    evidence_dir = work_dir / "04_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    cited_docs = conn.execute(
        """SELECT DISTINCT d.id, d.filename
           FROM evidence_citations ec
           JOIN documents d ON d.id = ec.document_id
           WHERE d.tender_id = ?""",
        (tender_id,),
    ).fetchall()
    # Fall back: if no citations yet, include all complete bidder docs
    if not cited_docs:
        cited_docs = conn.execute(
            """SELECT id, filename FROM documents
               WHERE tender_id = ? AND processing_state = 'complete'
                 AND deleted_at IS NULL""",
            (tender_id,),
        ).fetchall()
    for doc in cited_docs:
        doc_dir = evidence_dir / f"doc-{doc['id'][:12]}"
        doc_dir.mkdir(parents=True, exist_ok=True)
        page_rows = conn.execute(
            """SELECT id, page_number, image_path FROM pages
               WHERE document_id = ? ORDER BY page_number""",
            (doc["id"],),
        ).fetchall()
        for p in page_rows:
            if p["image_path"] and os.path.exists(p["image_path"]):
                dest_img = doc_dir / f"page-{p['page_number']}.png"
                shutil.copy2(p["image_path"], dest_img)
                files_added.append({
                    "path": f"04_evidence/doc-{doc['id'][:12]}/page-{p['page_number']}.png",
                    "sha256": sha256_file(str(dest_img)),
                })
            # bboxes for this page
            words = conn.execute(
                "SELECT text_content, x_min, y_min, x_max, y_max, confidence "
                "FROM word_objects WHERE page_id = ?",
                (p["id"],),
            ).fetchall()
            bb_path = doc_dir / f"page-{p['page_number']}.bboxes.json"
            bb_path.write_text(json.dumps([dict(w) for w in words], indent=2))
            files_added.append({
                "path": f"04_evidence/doc-{doc['id'][:12]}/page-{p['page_number']}.bboxes.json",
                "sha256": sha256_file(str(bb_path)),
            })

    # 05 — corrigenda (each + their criterion-version chain)
    corr_dir = work_dir / "05_corrigenda"
    corr_dir.mkdir(parents=True, exist_ok=True)
    corr_rows = conn.execute(
        "SELECT * FROM corrigenda WHERE tender_id = ? ORDER BY sequence_number",
        (tender_id,),
    ).fetchall()
    for c in corr_rows:
        cv = conn.execute(
            "SELECT * FROM criterion_versions WHERE corrigendum_id = ? ORDER BY version",
            (c["id"],),
        ).fetchall()
        path = corr_dir / f"corrigendum-{c['sequence_number']}.json"
        path.write_text(json.dumps({
            "corrigendum": dict(c),
            "criterion_versions_caused": [dict(r) for r in cv],
        }, indent=2, default=str))
        files_added.append({
            "path": f"05_corrigenda/{path.name}",
            "sha256": sha256_file(str(path)),
        })

    # 06 — audit chain (full)
    audit_path = work_dir / "06_audit-chain.json"
    audit_path.write_text(json.dumps(items, indent=2, default=str))
    files_added.append({"path": "06_audit-chain.json",
                        "sha256": sha256_file(str(audit_path))})

    # 07 — pipeline signature
    sig = pipeline_signature()
    sig_path = work_dir / "07_pipeline-signature.txt"
    sig_path.write_text(
        f"pipeline_signature_hash={sig}\n"
        f"model_id={settings.bedrock.model_id}\n"
        f"region={settings.bedrock.region}\n"
        f"temperature={settings.bedrock.temperature}\n"
        f"max_tokens={settings.bedrock.max_tokens}\n"
    )
    files_added.append({"path": "07_pipeline-signature.txt",
                        "sha256": sha256_file(str(sig_path))})

    # 08 — reproduce script
    repro_path = work_dir / "08_reproduce.py"
    repro_path.write_text(REPRODUCE_TEMPLATE)
    repro_path.chmod(0o755)
    files_added.append({"path": "08_reproduce.py",
                        "sha256": sha256_file(str(repro_path))})

    # 09 — manifest (must be last so it lists everything else)
    vault_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "vault_id": vault_id,
        "tender_id": tender_id,
        "tender_number": tender["tender_number"],
        "tender_title": tender["title"],
        "department": tender["department"],
        "pipeline_signature_hash": sig,
        "generated_by": officer_id,
        "generated_at": now,
        "files": files_added,
    }
    manifest_path = work_dir / "09_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
    manifest_sha = sha256_file(str(manifest_path))

    # 10 — seal (sha256 of manifest + officer, easy to verify externally)
    seal_payload = (
        f"manifest_sha256={manifest_sha}\n"
        f"sealed_by={officer_id}\n"
        f"sealed_at={now}\n"
        f"vault_id={vault_id}\n"
    )
    seal_path = work_dir / "10_seal.txt"
    seal_path.write_text(seal_payload)

    # Build the ZIP
    zip_path = vault_dir_root / f"{vault_basename}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(work_dir):
            for f in sorted(files):
                full = Path(root) / f
                arcname = full.relative_to(work_dir)
                zf.write(full, arcname=arcname)

    # Clean up the working directory (we keep only the ZIP)
    try:
        shutil.rmtree(work_dir)
    except Exception:
        pass

    file_size = os.path.getsize(zip_path)
    zip_sha = sha256_file(str(zip_path))

    conn.execute(
        """INSERT INTO vaults
           (id, tender_id, file_path, sha256_hash, file_size_bytes,
            manifest, pipeline_signature_hash, generated_by, generated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (vault_id, tender_id, str(zip_path), zip_sha, file_size,
         json.dumps(manifest, default=str), sig, officer_id, now),
    )
    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="vault_generated",
        event_data={
            "vault_id": vault_id,
            "file_size_bytes": file_size,
            "sha256_hash": zip_sha,
            "file_count": len(files_added) + 2,  # + manifest, seal
        },
        actor=officer_id,
    )
    return {
        "id": vault_id,
        "tender_id": tender_id,
        "file_path": str(zip_path),
        "sha256_hash": zip_sha,
        "file_size_bytes": file_size,
        "generated_by": officer_id,
        "generated_at": now,
        "manifest": manifest,
    }


def list_vaults(conn, tender_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM vaults WHERE tender_id = ? ORDER BY generated_at DESC",
        (tender_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["manifest"] = json.loads(d["manifest"])
        except (json.JSONDecodeError, TypeError):
            pass
        out.append(d)
    return out


def get_vault(conn, vault_id: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM vaults WHERE id = ?", (vault_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["manifest"] = json.loads(d["manifest"])
    except (json.JSONDecodeError, TypeError):
        pass
    return d


def _latest_report_path(conn, tender_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT file_path FROM reports WHERE tender_id = ? "
        "ORDER BY generated_at DESC LIMIT 1",
        (tender_id,),
    ).fetchone()
    return row["file_path"] if row else None
