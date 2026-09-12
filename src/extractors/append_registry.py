"""Registry manager and candidate staging pipeline.

Consolidates verified candidates into source registry with event_type reclassification
(occupancy_first_actual, occupancy_planned_block, occupancy_first_planned, etc.),
namespace conflict resolution (T1-, T2-), and 2G/3G cohort tagging.
"""

import csv
import pathlib
from typing import Dict, List, Optional
import pandas as pd


# 2nd generation (historical validation cohort) vs 3rd generation (forward observation cohort)
COHORT_MAP = {
    "화성 동탄2": "2G_historical",
    "김포 한강": "2G_historical",
    "위례": "2G_historical",
    "남양주 다산": "2G_historical",
    "하남 미사": "2G_historical",
    "인천 계양": "3G_forward",
    "남양주 왕숙": "3G_forward",
    "하남 교산": "3G_forward",
    "고양 창릉": "3G_forward",
    "부천 대장": "3G_forward",
}


def classify_occupancy_event(cand_id: str, title: str, excerpt: str, notes: str, scope: str) -> str:
    """Classify occupancy events into 3 granular types:

    - occupancy_first_actual: District-level first actual move-in
    - occupancy_planned_block: Block-level scheduled move-in
    - occupancy_first_planned: Early master plan initial target
    """
    text = f"{title} {excerpt} {notes}".lower()
    
    if "개발계획 확정" in title or "이루어지도록 할 계획" in excerpt or "초기 계획" in notes:
        return "occupancy_first_planned"
    
    if any(k in text for k in ["첫 입주 시작", "첫 입주 등", "첫 입주를 시작", "최초 주민입주"]):
        if scope in ["district", "지구 전체"]:
            return "occupancy_first_actual"
            
    if any(k in text for k in ["블록", "bl", "입주자모집공고", "공공분양", "임대주택"]):
        return "occupancy_planned_block"
        
    return "occupancy_first_actual" if scope in ["district", "지구 전체"] else "occupancy_planned_block"


def build_staged_registry(
    base_dir: Optional[pathlib.Path] = None,
    output_csv: Optional[pathlib.Path] = None
) -> pd.DataFrame:
    """Load all *_checked.csv files, apply data governance rules,

    and build the unified staged evidence registry.
    """
    if base_dir is None:
        base_dir = pathlib.Path.cwd()
        
    raw_dir = base_dir / "data" / "raw"
    staged_dir = base_dir / "data" / "staged"
    staged_dir.mkdir(parents=True, exist_ok=True)
    
    if output_csv is None:
        output_csv = staged_dir / "staged_candidates_registry.csv"

    # Candidate checked files
    checked_files = [
        (raw_dir / "historical_validation_candidates_checked.csv", "T1"),
        (raw_dir / "forward_monitoring_candidates_checked.csv", "T2"),
        (raw_dir / "evidence" / "선단지_RAW_checked.csv", "E1"),
        (raw_dir / "evidence" / "후기단지_RAW_checked.csv", "E2"),
    ]

    all_records = []
    seen_ids = set()

    for file_path, prefix in checked_files:
        if not file_path.exists():
            continue
            
        df = pd.read_csv(file_path, encoding="utf-8-sig", dtype=str).fillna("")
        for _, row in df.iterrows():
            rec = row.to_dict()
            
            # Resolve ID collisions with namespace prefix
            raw_id = rec.get("cand_id", "").strip()
            if not raw_id:
                continue
                
            namespaced_id = f"{prefix}-{raw_id}" if not raw_id.startswith(("T1-", "T2-", "E1-", "E2-", "H", "F")) else raw_id
            rec["cand_id_namespaced"] = namespaced_id
            
            dev = rec.get("development", "").strip()
            rec["cohort_type"] = COHORT_MAP.get(dev, "other")
            
            # Reclassify occupancy event types
            event_type = rec.get("event_type", "").strip()
            if event_type == "occupancy_start":
                rec["event_type_refined"] = classify_occupancy_event(
                    cand_id=raw_id,
                    title=rec.get("title", ""),
                    excerpt=rec.get("exact_excerpt", ""),
                    notes=rec.get("notes", ""),
                    scope=rec.get("scope", "")
                )
            else:
                rec["event_type_refined"] = event_type
                
            all_records.append(rec)

    staged_df = pd.DataFrame(all_records)
    staged_df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"[*] Staged registry built: {output_csv} (Total {len(staged_df)} rows)")
    
    return staged_df


if __name__ == "__main__":
    build_staged_registry()
