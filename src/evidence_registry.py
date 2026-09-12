import os
import hashlib
import pandas as pd
from pathlib import Path
from typing import List, Dict

HISTORICAL_PILOTS = [
    "Dongtan2",
    "Gimpo Hangang",
    "Wirye",
    "Namyangju Dasan",
    "Hanam Misa"
]

REQUIRED_EVENTS = ["occupancy_start", "promise_date", "actual_operation"]

def compute_sha256(filepath: str) -> str:
    """Computes SHA-256 for a local file."""
    path = Path(filepath)
    if not path.is_file():
        return ""
    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def validate_registry(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validates required columns, computes hashes, filters human_verified rows.
    """
    required_cols = [
        "candidate_id", "development", "event_type", "event_date",
        "date_precision", "date_lower_bound", "date_upper_bound",
        "source_url", "local_path", "sha256", "review_status"
    ]
    
    # 1. Validate required columns
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
        
    # 2. Compute SHA-256 for local files if missing or empty
    def ensure_hash(row):
        current_hash = row.get("sha256", "")
        if pd.isna(current_hash) or current_hash == "":
            return compute_sha256(row["local_path"])
        return current_hash
        
    df["sha256"] = df.apply(ensure_hash, axis=1)
    
    # 3. Reject metric-eligible rows unless review_status is human_verified
    # We create a metric_eligible flag
    df["metric_eligible"] = df["review_status"].str.strip().str.lower() == "human_verified"
    
    # 4. Preserve date precision and bounds (ensure they are strings, handle NaN as NULL)
    df["date_precision"] = df["date_precision"].fillna("unknown").astype(str)
    
    return df

def generate_gate_report(df: pd.DataFrame, out_path: str = "docs/data_gate_status.md"):
    """
    Evaluates the 3-day data gate for historical pilots and writes a markdown report.
    """
    # Use only metric_eligible rows for the gate
    valid_df = df[df["metric_eligible"]].copy()
    
    pilot_status = {}
    completed_pilots = 0
    high_precision_pilots = 0
    
    for pilot in HISTORICAL_PILOTS:
        pilot_df = valid_df[valid_df["development"] == pilot]
        events_found = {}
        has_high_precision = True
        
        for ev in REQUIRED_EVENTS:
            ev_df = pilot_df[pilot_df["event_type"] == ev]
            if not ev_df.empty:
                row = ev_df.iloc[0]
                prec = row["date_precision"]
                events_found[ev] = {
                    "date": row["event_date"],
                    "precision": prec
                }
                if prec not in ["day", "month"]:
                    has_high_precision = False
            else:
                events_found[ev] = "MISSING"
                has_high_precision = False
                
        has_all_events = all(v != "MISSING" for v in events_found.values())
        
        if has_all_events:
            completed_pilots += 1
            if has_high_precision:
                high_precision_pilots += 1
                
        pilot_status[pilot] = {
            "events": events_found,
            "has_all_events": has_all_events,
            "has_high_precision": has_high_precision
        }
        
    passed_gate = (completed_pilots >= 4) and (high_precision_pilots >= 3)
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# 3-Day Data Gate Status Report\n\n")
        f.write(f"**Gate Decision:** {'PASS' if passed_gate else 'FAIL'}\n")
        f.write(f"- Pilots with all 3 events: {completed_pilots} / 5 (Required: >=4)\n")
        f.write(f"- Pilots with high precision (day/month): {high_precision_pilots} / 5 (Required: >=3)\n\n")
        
        f.write("## Detailed Status\n\n")
        f.write("> **Note**: Missing evidence is marked as `MISSING` and is distinct from a 0-day gap.\n\n")
        
        for pilot, status in pilot_status.items():
            f.write(f"### {pilot}\n")
            for ev in REQUIRED_EVENTS:
                val = status["events"][ev]
                if val == "MISSING":
                    f.write(f"- **{ev}**: MISSING EVIDENCE\n")
                else:
                    f.write(f"- **{ev}**: {val['date']} (Precision: {val['precision']})\n")
            f.write("\n")

def run_gate():
    registry_path = "evidence/candidate_registry.csv"
    if not Path(registry_path).exists():
        print("Registry not found.")
        return
        
    df = pd.read_csv(registry_path)
    df = validate_registry(df)
    
    out_dir = Path("docs")
    out_dir.mkdir(parents=True, exist_ok=True)
    generate_gate_report(df, str(out_dir / "data_gate_status.md"))
    print("Gate report generated at docs/data_gate_status.md")

if __name__ == "__main__":
    run_gate()
