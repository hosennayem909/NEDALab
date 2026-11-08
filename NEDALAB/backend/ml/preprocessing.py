"""Preprocessing: auto-detect types, split, scale, encode."""
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder, LabelEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer


def _detect_task_type(y: pd.Series) -> str:
    """Auto-detect classification vs regression from target."""
    if pd.api.types.is_numeric_dtype(y):
        unique = y.nunique()
        # Heuristic: small number of unique integer values -> classification
        if unique <= 20 and (y.dropna() % 1 == 0).all():
            return "classification"
        return "regression"
    return "classification"


def prepare_data(
    df: pd.DataFrame,
    target_column: str,
    feature_columns: list,
    task_type: str = "auto",
    test_size: float = 0.2,
    random_state: int = 42,
):
    """Split + preprocess. Returns everything needed for training."""
    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' not found")
    for c in feature_columns:
        if c not in df.columns:
            raise ValueError(f"Feature column '{c}' not found")
    if target_column in feature_columns:
        raise ValueError("Target column cannot be in feature columns")

    sub = df[[target_column] + feature_columns].copy()
    sub = sub.dropna(subset=[target_column])

    if len(sub) < 20:
        raise ValueError(f"Need at least 20 rows, got {len(sub)}")

    y_raw = sub[target_column]
    X_raw = sub[feature_columns]

    # Detect task type
    if task_type == "auto":
        task_type = _detect_task_type(y_raw)

    # Prepare y
    label_encoder = None
    if task_type == "classification":
        # Encode labels to integer
        label_encoder = LabelEncoder()
        y = pd.Series(label_encoder.fit_transform(y_raw.astype(str)), index=y_raw.index)
    else:
        y = pd.to_numeric(y_raw, errors="coerce")
        valid = y.notna()
        X_raw = X_raw[valid]
        y = y[valid]

    if len(y) < 20:
        raise ValueError("Too few valid rows after preprocessing")

    # Detect numeric vs categorical features
    numeric_cols = X_raw.select_dtypes(include=np.number).columns.tolist()
    categorical_cols = [c for c in feature_columns if c not in numeric_cols]

    # Cap categorical cardinality (warn if too many unique)
    for c in categorical_cols:
        if X_raw[c].nunique() > 50:
            # Treat as categorical still but warn
            pass

    # Build preprocessor
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="mean")),
        ("scaler", StandardScaler()),
    ])
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    transformers = []
    if numeric_cols:
        transformers.append(("num", numeric_pipeline, numeric_cols))
    if categorical_cols:
        transformers.append(("cat", categorical_pipeline, categorical_cols))

    if not transformers:
        raise ValueError("No valid features found")

    preprocessor = ColumnTransformer(transformers=transformers, remainder="drop")

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X_raw, y,
        test_size=test_size,
        random_state=random_state,
        stratify=y if (task_type == "classification" and y.nunique() <= 20) else None,
    )

    # Fit preprocessor on train, transform both
    X_train_t = preprocessor.fit_transform(X_train)
    X_test_t = preprocessor.transform(X_test)

    # =========================================================================
    # ফিচার নেম বের করার আপডেট করা অংশ (Sklearn-এর বিল্ট-ইন মেথড)
    # এখানেই আগের বার এরর হচ্ছিল, এখন এটি ফিট হওয়া প্রিপ্রসেসর থেকে নাম নিবে
    # =========================================================================
    feature_names = list(preprocessor.get_feature_names_out())

    return {
        "X_train": X_train_t,
        "X_test": X_test_t,
        "y_train": y_train.to_numpy(),
        "y_test": y_test.to_numpy(),
        "preprocessor": preprocessor,
        "feature_names": feature_names,
        "task_type": task_type,
        "label_encoder": label_encoder,
        "n_features": X_train_t.shape[1],
        "n_train": len(y_train),
        "n_test": len(y_test),
        "n_original_features": len(feature_columns),
        "numeric_features": numeric_cols,
        "categorical_features": categorical_cols,
    }