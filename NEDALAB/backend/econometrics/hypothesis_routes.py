import traceback
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import pandas as pd

from core.database import get_db
from core.deps import get_current_user
from auth.models import User
from data_hub.models import Dataset
from econometrics.hypothesis_engine import (
    one_sample_ttest, two_sample_ttest, paired_ttest,
    one_way_anova, chi_square_independence,
    mann_whitney, kruskal_wallis,
    shapiro_wilk, levene_test,
    correlation, tukey_hsd,
)
from econometrics.hypothesis_schemas import (
    TTestIn, ANOVAIn, ChiSquareIn, NonParamIn, ShapiroIn, LeveneIn, SuiteIn,
    CorrelationIn, TukeyHSDIn,
)

router = APIRouter(prefix="/api/econometrics/hypothesis", tags=["hypothesis"])


def _get_owned(db, dataset_id, user):
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    if user.role != "admin" and ds.user_email != user.email:
        raise HTTPException(403, "Not your dataset")
    return ds


def _load(ds):
    if not ds.cleaned_path:
        raise HTTPException(400, "No cleaned file")
    p = Path(ds.cleaned_path)
    if not p.exists():
        raise HTTPException(404, "File missing")
    return pd.read_csv(p)


@router.post("/t-test")
def t_test_endpoint(payload: TTestIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)

        if payload.test_variant == "one_sample":
            return one_sample_ttest(df, payload.column, payload.popmean)
        elif payload.test_variant == "two_sample":
            return two_sample_ttest(df, payload.column, payload.group_column, payload.equal_var)
        elif payload.test_variant == "paired":
            return paired_ttest(df, payload.column_a, payload.column_b)
        else:
            raise HTTPException(400, f"Unknown test_variant: {payload.test_variant}")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("T-TEST ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/anova")
def anova_endpoint(payload: ANOVAIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return one_way_anova(df, payload.column, payload.group_column)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("ANOVA ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/chi-square")
def chi_square_endpoint(payload: ChiSquareIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return chi_square_independence(df, payload.column_a, payload.column_b)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("CHI-SQUARE ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/mann-whitney")
def mann_whitney_endpoint(payload: NonParamIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return mann_whitney(df, payload.column, payload.group_column)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("MANN-WHITNEY ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/kruskal-wallis")
def kruskal_endpoint(payload: NonParamIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return kruskal_wallis(df, payload.column, payload.group_column)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("KRUSKAL ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/shapiro")
def shapiro_endpoint(payload: ShapiroIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return shapiro_wilk(df, payload.column)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("SHAPIRO ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/levene")
def levene_endpoint(payload: LeveneIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return levene_test(df, payload.column, payload.group_column)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("LEVENE ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


# ✅ নতুন ২টি এন্ডপয়েন্ট
@router.post("/correlation")
def correlation_endpoint(payload: CorrelationIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return correlation(df, payload.column_a, payload.column_b)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("CORRELATION ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/tukey-hsd")
def tukey_hsd_endpoint(payload: TukeyHSDIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)
        return tukey_hsd(df, payload.column, payload.group_column)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("TUKEY HSD ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")


@router.post("/suite")
def suite_endpoint(payload: SuiteIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Run all applicable tests on given columns."""
    try:
        ds = _get_owned(db, payload.dataset_id, user)
        df = _load(ds)

        results = {}

        if payload.column_a and payload.column_a in df.columns:
            try:
                results["shapiro_a"] = shapiro_wilk(df, payload.column_a)
            except ValueError as e:
                results["shapiro_a"] = {"error": str(e)}

        if payload.column_b and payload.column_b in df.columns:
            try:
                results["shapiro_b"] = shapiro_wilk(df, payload.column_b)
            except ValueError as e:
                results["shapiro_b"] = {"error": str(e)}

        if payload.column_a and payload.column_b:
            try:
                results["paired_ttest"] = paired_ttest(df, payload.column_a, payload.column_b)
            except ValueError as e:
                results["paired_ttest"] = {"error": str(e)}

        if payload.column_a and payload.popmean is not None:
            try:
                results["one_sample_ttest"] = one_sample_ttest(df, payload.column_a, payload.popmean)
            except ValueError as e:
                results["one_sample_ttest"] = {"error": str(e)}

        if payload.group_column and payload.column_a:
            try:
                results["anova"] = one_way_anova(df, payload.column_a, payload.group_column)
            except ValueError as e:
                results["anova"] = {"error": str(e)}
            try:
                results["levene"] = levene_test(df, payload.column_a, payload.group_column)
            except ValueError as e:
                results["levene"] = {"error": str(e)}
            try:
                results["kruskal_wallis"] = kruskal_wallis(df, payload.column_a, payload.group_column)
            except ValueError as e:
                results["kruskal_wallis"] = {"error": str(e)}
            try:
                results["mann_whitney"] = mann_whitney(df, payload.column_a, payload.group_column)
            except ValueError as e:
                results["mann_whitney"] = {"error": str(e)}

        return {"dataset_id": ds.id, "results": results}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print("SUITE ERROR:", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {str(e)}")