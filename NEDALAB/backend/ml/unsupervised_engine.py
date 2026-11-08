"""Unsupervised learning: K-Means, DBSCAN, PCA, Isolation Forest."""
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.metrics import silhouette_score, davies_bouldin_score


def _to_py(v):
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        f = float(v)
        return None if (np.isnan(f) or np.isinf(f)) else round(f, 6)
    if isinstance(v, np.ndarray):
        return [_to_py(x) for x in v.tolist()]
    if isinstance(v, list):
        return [_to_py(x) for x in v]
    if isinstance(v, dict):
        return {k: _to_py(val) for k, val in v.items()}
    if isinstance(v, float):
        return None if (np.isnan(v) or np.isinf(v)) else round(v, 6)
    return v


def _prepare(df, columns, sample_size=None):
    """Coerce numeric, impute, scale. Returns scaled matrix + cleaned df."""
    if not columns:
        raise ValueError("Select at least one column")
    for c in columns:
        if c not in df.columns:
            raise ValueError(f"Column '{c}' not found")

    sub = df[columns].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 10:
        raise ValueError(f"Need at least 10 valid rows, got {len(sub)}")

    if sample_size and len(sub) > sample_size:
        sub = sub.sample(n=sample_size, random_state=42).reset_index(drop=True)

    X = sub.to_numpy(dtype=float)
    X = SimpleImputer(strategy="mean").fit_transform(X)
    X_scaled = StandardScaler().fit_transform(X)

    return sub.reset_index(drop=True), X_scaled, columns


# ============================================================
# K-MEANS with elbow method
# ============================================================
def kmeans_cluster(df, columns, n_clusters=3, sample_size=5000, elbow_max=10):
    """K-Means clustering + elbow method + silhouette."""
    sub, X_scaled, cols = _prepare(df, columns, sample_size)

    # Elbow: compute inertia for K=2..elbow_max
    elbow = []
    max_k = min(elbow_max, max(2, len(sub) // 3))
    for k in range(2, max_k + 1):
        try:
            km = KMeans(n_clusters=k, n_init=10, random_state=42)
            km.fit(X_scaled)
            elbow.append({"k": k, "inertia": _to_py(km.inertia_)})
        except Exception:
            continue

    # Final fit
    n_clusters = max(2, min(int(n_clusters), len(sub) - 1))
    model = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
    labels = model.fit_predict(X_scaled)

    # Quality metrics
    quality = {}
    try:
        quality["silhouette"] = _to_py(silhouette_score(X_scaled, labels))
    except Exception:
        quality["silhouette"] = None
    try:
        quality["davies_bouldin"] = _to_py(davies_bouldin_score(X_scaled, labels))
    except Exception:
        quality["davies_bouldin"] = None

    # Cluster sizes
    unique, counts = np.unique(labels, return_counts=True)
    sizes = [{"cluster": int(u), "count": int(c)} for u, c in zip(unique, counts)]

    # Centroids (in original scale)
    centroids = []
    for i, c in enumerate(model.cluster_centers_):
        centroids.append({
            "cluster": i,
            "center": {col: _to_py(round(float(v), 4)) for col, v in zip(cols, c)},
        })

    # PCA 2D for visualization
    vis_points = _pca_project(X_scaled, labels, sample_size=2000)

    return {
        "n_samples": int(len(sub)),
        "n_clusters": n_clusters,
        "n_features": len(cols),
        "labels": [_to_py(l) for l in labels.tolist()[:2000]],
        "cluster_sizes": sizes,
        "centroids": centroids,
        "elbow": elbow,
        "quality": quality,
        "vis_points": vis_points,
    }


# ============================================================
# DBSCAN
# ============================================================
def dbscan_cluster(df, columns, eps=0.5, min_samples=5, sample_size=5000):
    """Density-based clustering."""
    sub, X_scaled, cols = _prepare(df, columns, sample_size)

    eps = float(eps)
    min_samples = max(2, int(min_samples))

    model = DBSCAN(eps=eps, min_samples=min_samples)
    labels = model.fit_predict(X_scaled)

    unique, counts = np.unique(labels, return_counts=True)
    sizes = [{"cluster": int(u), "count": int(c)} for u, c in zip(unique, counts)]
    n_clusters = int(len([u for u in unique if u >= 0]))
    n_noise = int((labels == -1).sum())

    quality = {}
    mask = labels != -1
    if mask.sum() > 10 and len(set(labels[mask])) > 1:
        try:
            quality["silhouette"] = _to_py(silhouette_score(X_scaled[mask], labels[mask]))
        except Exception:
            quality["silhouette"] = None
    else:
        quality["silhouette"] = None

    vis_points = _pca_project(X_scaled, labels, sample_size=2000)

    return {
        "n_samples": int(len(sub)),
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "eps": eps,
        "min_samples": min_samples,
        "cluster_sizes": sizes,
        "quality": quality,
        "vis_points": vis_points,
    }


# ============================================================
# PCA
# ============================================================
def pca_analysis(df, columns, n_components=None, sample_size=5000):
    """PCA dimensionality reduction + variance explained."""
    sub, X_scaled, cols = _prepare(df, columns, sample_size)

    max_comp = min(len(cols), len(sub))
    if n_components is None:
        n_components = max_comp
    n_components = max(1, min(int(n_components), max_comp))

    model = PCA(n_components=n_components, random_state=42)
    X_pca = model.fit_transform(X_scaled)

    explained = model.explained_variance_ratio_
    cumulative = np.cumsum(explained)

    # Loadings (how much each original feature contributes)
    loadings = []
    for i in range(n_components):
        loading = {"pc": f"PC{i+1}", "variance_pct": _to_py(round(explained[i] * 100, 2))}
        loadings.append({
            **loading,
            "weights": {col: _to_py(round(float(w), 4)) for col, w in zip(cols, model.components_[i])},
        })

    # 2D projections for visualization
    vis_points = []
    if n_components >= 2:
        step = max(1, len(X_pca) // 2000)
        for i in range(0, len(X_pca), step):
            vis_points.append({
                "pc1": _to_py(X_pca[i, 0]),
                "pc2": _to_py(X_pca[i, 1]),
            })

    return {
        "n_samples": int(len(sub)),
        "n_features_original": len(cols),
        "n_components": n_components,
        "explained_variance": [_to_py(x) for x in explained.tolist()],
        "cumulative_variance": [_to_py(x) for x in cumulative.tolist()],
        "loadings": loadings,
        "vis_points": vis_points,
    }


# ============================================================
# ANOMALY DETECTION
# ============================================================
def detect_anomalies(df, columns, contamination=0.05, sample_size=10000):
    """Isolation Forest anomaly detection."""
    sub, X_scaled, cols = _prepare(df, columns, sample_size)

    contamination = max(0.001, min(float(contamination), 0.5))

    model = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100,
        n_jobs=-1,
    )
    preds = model.fit_predict(X_scaled)  # -1 = anomaly, 1 = normal
    scores = model.score_samples(X_scaled)  # lower = more anomalous

    anomaly_mask = preds == -1
    n_anomalies = int(anomaly_mask.sum())
    n_normal = int(len(preds) - n_anomalies)

    # Top anomalies (lowest scores)
    top_idx = np.argsort(scores)[:min(20, n_anomalies if n_anomalies > 0 else 20)]
    anomalies = []
    for i in top_idx:
        if not anomaly_mask[i]:
            continue
        row = sub.iloc[i]
        anomalies.append({
            "row_index": int(i),
            "score": _to_py(scores[i]),
            "values": {col: _to_py(row[col]) for col in cols},
        })

    # PCA for visualization
    vis_points = _pca_project(X_scaled, preds, sample_size=2000)

    return {
        "n_samples": int(len(sub)),
        "n_anomalies": n_anomalies,
        "n_normal": n_normal,
        "contamination": contamination,
        "anomaly_pct": round(n_anomalies / len(sub) * 100, 2),
        "top_anomalies": anomalies,
        "vis_points": vis_points,
    }


# ============================================================
# PCA helper for 2D projection
# ============================================================
def _pca_project(X_scaled, labels, sample_size=2000):
    """Project to 2D via PCA for visualization."""
    try:
        pca = PCA(n_components=2, random_state=42)
        X_2d = pca.fit_transform(X_scaled)
    except Exception:
        return []

    n = len(X_2d)
    step = max(1, n // sample_size)
    points = []
    for i in range(0, n, step):
        points.append({
            "x": _to_py(X_2d[i, 0]),
            "y": _to_py(X_2d[i, 1]),
            "label": int(labels[i]),
        })
    return points
