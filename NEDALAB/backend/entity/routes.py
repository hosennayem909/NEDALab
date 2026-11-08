import json
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from entity.models import EntityRule
from entity.schemas import (
    EntityRuleCreate, EntityRuleUpdate, EntityRuleOut,
    TestMatchIn, TestMatchOut, TestMatchResult,
    ApplyMappingIn, ApplyMappingOut,
)
from entity.engine import apply_mapping, test_values

router = APIRouter(prefix="/api/entity", tags=["entity"])

UPLOAD_DIR = Path("uploads")


def _rule_to_dict(r: EntityRule) -> dict:
    try:
        kws = json.loads(r.keywords_json or "[]")
    except Exception:
        kws = []
    return {
        "id": r.id,
        "name": r.name,
        "standard_value": r.standard_value,
        "keywords": kws,
        "match_threshold": r.match_threshold,
        "match_type": r.match_type,
        "column_hint": r.column_hint,
        "case_sensitive": r.case_sensitive,
        "active": r.active,
        "created_at": r.created_at,
    }


def _rule_to_out(r: EntityRule) -> EntityRuleOut:
    return EntityRuleOut(**_rule_to_dict(r))


@router.get("/rules", response_model=list[EntityRuleOut])
def list_rules(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(EntityRule).order_by(EntityRule.created_at.desc())
    if user.role != "admin":
        q = q.filter(EntityRule.user_id == user.id)
    return [_rule_to_out(r) for r in q.all()]


@router.post("/rules", response_model=EntityRuleOut, status_code=201)
def create_rule(payload: EntityRuleCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not payload.keywords or not any(k.strip() for k in payload.keywords):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "At least one keyword required")
    r = EntityRule(
        user_id=user.id,
        name=payload.name.strip(),
        standard_value=payload.standard_value.strip(),
        keywords_json=json.dumps([k.strip() for k in payload.keywords if k.strip()]),
        match_threshold=payload.match_threshold,
        match_type=payload.match_type,
        column_hint=payload.column_hint,
        case_sensitive=payload.case_sensitive,
        active=payload.active,
    )
    db.add(r); db.commit(); db.refresh(r)
    return _rule_to_out(r)


@router.put("/rules/{rule_id}", response_model=EntityRuleOut)
def update_rule(rule_id: int, payload: EntityRuleUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = db.query(EntityRule).filter(EntityRule.id == rule_id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    if user.role != "admin" and r.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your rule")

    if payload.name is not None: r.name = payload.name.strip()
    if payload.standard_value is not None: r.standard_value = payload.standard_value.strip()
    if payload.keywords is not None: r.keywords_json = json.dumps([k.strip() for k in payload.keywords if k.strip()])
    if payload.match_threshold is not None: r.match_threshold = payload.match_threshold
    if payload.match_type is not None: r.match_type = payload.match_type
    if payload.column_hint is not None: r.column_hint = payload.column_hint
    if payload.case_sensitive is not None: r.case_sensitive = payload.case_sensitive
    if payload.active is not None: r.active = payload.active

    db.commit(); db.refresh(r)
    return _rule_to_out(r)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = db.query(EntityRule).filter(EntityRule.id == rule_id).first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    if user.role != "admin" and r.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your rule")
    db.delete(r); db.commit()
    return None


@router.post("/test", response_model=TestMatchOut)
def test_match(payload: TestMatchIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.rules is not None:
        rules = [r.model_dump() for r in payload.rules]
    else:
        q = db.query(EntityRule).filter(EntityRule.active == True)  # noqa: E712
        if user.role != "admin":
            q = q.filter(EntityRule.user_id == user.id)
        rules = [_rule_to_dict(r) for r in q.all()]

    results = test_values(payload.values, rules)
    matched = sum(1 for r in results if r["matched"])
    return TestMatchOut(
        total=len(results),
        matched_count=matched,
        results=[TestMatchResult(**r) for r in results],
    )


@router.post("/apply", response_model=ApplyMappingOut)
def apply_to_dataset(payload: ApplyMappingIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ds = db.query(Dataset).filter(Dataset.id == payload.dataset_id).first()
    if not ds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your dataset")
    if not ds.cleaned_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No cleaned file")

    p = Path(ds.cleaned_path)
    if not p.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cleaned file missing on disk")

    q = db.query(EntityRule).filter(EntityRule.active == True)  # noqa: E712
    if user.role != "admin":
        q = q.filter(EntityRule.user_id == user.id)
    rules = [_rule_to_dict(r) for r in q.all()]

    if not rules:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No active entity rules found")

    df = pd.read_csv(p)
    try:
        new_df, summary = apply_mapping(df, payload.column, rules)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(ds.filename).stem if ds.filename else f"dataset_{ds.id}"
    out_name = payload.output_name or f"mapped_{base}.csv"
    out_path = UPLOAD_DIR / f"{stamp}_{out_name}"
    new_df.to_csv(out_path, index=False)

    new_ds = Dataset(
        user_email=user.email,
        filename=out_name,
        row_count=int(new_df.shape[0]),
        column_count=int(new_df.shape[1]),
        status="mapped",
        cleaned_path=str(out_path),
    )
    db.add(new_ds); db.commit(); db.refresh(new_ds)

    return ApplyMappingOut(
        dataset_id=ds.id,
        column=payload.column,
        total_rows=summary["total_rows"],
        changed_rows=summary["changed_rows"],
        mapping_summary=summary["summary"],
        output_dataset_id=new_ds.id,
        output_filename=new_ds.filename,
    )
