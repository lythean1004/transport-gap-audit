"""Gate evaluator for 2G historical validation cohort.

Evaluates GO / PIVOT readiness based on:
1. Coverage across 5 historical districts (화성 동탄2, 김포 한강, 위례, 남양주 다산, 하남 미사).
2. Availability of 3 key dates: occupancy_first_actual, promise_date, actual_operation.
3. Date precision (day / month vs year / unknown).
4. Mode consistency (e.g. rail vs rail, tram vs tram).
"""

from typing import Dict, List, Optional
import pathlib
import pandas as pd


HISTORICAL_DISTRICTS = [
    "화성 동탄2",
    "김포 한강",
    "위례",
    "남양주 다산",
    "하남 미사",
]


def evaluate_gate(staged_csv: Optional[pathlib.Path] = None) -> Dict[str, any]:
    """Evaluates the audit gate status on historical districts."""
    if staged_csv is None:
        staged_csv = pathlib.Path("data/staged/staged_candidates_registry.csv")

    if not staged_csv.exists():
        return {
            "status": "DATA_MISSING",
            "message": f"Staged file not found: {staged_csv}",
            "districts_status": {},
        }

    df = pd.read_csv(staged_csv, encoding="utf-8-sig", dtype=str).fillna("")
    
    # Filter 2G historical cohort
    h_df = df[df["cohort_type"] == "2G_historical"].copy()
    
    results = {}
    valid_count = 0
    high_precision_count = 0

    for dist in HISTORICAL_DISTRICTS:
        dist_rows = h_df[h_df["development"] == dist]
        
        # 1. Occupancy first actual
        occ_rows = dist_rows[dist_rows["event_type_refined"] == "occupancy_first_actual"]
        occ_cand = occ_rows.iloc[0]["cand_id_namespaced"] if not occ_rows.empty else None
        occ_date = occ_rows.iloc[0]["event_date_초안"] if not occ_rows.empty else None
        occ_prec = occ_rows.iloc[0]["date_precision"] if not occ_rows.empty else None

        # 2. Promise date
        prom_rows = dist_rows[dist_rows["event_type_refined"].isin(["promise_date", "promise_absent"])]
        prom_cand = prom_rows.iloc[0]["cand_id_namespaced"] if not prom_rows.empty else None
        prom_date = prom_rows.iloc[0]["event_date_초안"] if not prom_rows.empty else None
        prom_mode = prom_rows.iloc[0]["mode"] if not prom_rows.empty else None

        # 3. Actual operation
        act_rows = dist_rows[dist_rows["event_type_refined"] == "actual_operation"]
        act_cand = act_rows.iloc[0]["cand_id_namespaced"] if not act_rows.empty else None
        act_date = act_rows.iloc[0]["event_date_초안"] if not act_rows.empty else None
        act_mode = act_rows.iloc[0]["mode"] if not act_rows.empty else None
        act_prec = act_rows.iloc[0]["date_precision"] if not act_rows.empty else None

        # Mode match check
        mode_match = (
            (prom_mode.lower() in act_mode.lower() or act_mode.lower() in prom_mode.lower())
            if (prom_mode and act_mode)
            else False
        )

        has_all_3 = bool(occ_cand and prom_cand and act_cand)
        is_high_prec = bool(occ_prec in ["day", "month"] and act_prec in ["day", "month"])
        
        if has_all_3:
            valid_count += 1
        if is_high_prec:
            high_precision_count += 1

        results[dist] = {
            "occupancy_first_actual": f"{occ_cand} ({occ_date}, {occ_prec})",
            "promise": f"{prom_cand} ({prom_date}, mode: {prom_mode})",
            "actual_operation": f"{act_cand} ({act_date}, {act_prec}, mode: {act_mode})",
            "mode_match": mode_match,
            "has_all_3": has_all_3,
            "high_precision": is_high_prec,
        }

    # Gate condition: 4+ districts with 3 date types, and 3+ with day/month precision
    gate_passed = (valid_count >= 4 and high_precision_count >= 3)
    gate_decision = "GO (진행)" if gate_passed else "PIVOT / 보완 필요"

    summary = {
        "gate_decision": gate_decision,
        "valid_districts_count": f"{valid_count} / 5",
        "high_precision_count": f"{high_precision_count} / 5",
        "districts_detail": results,
    }
    
    return summary


def print_gate_report():
    report = evaluate_gate()
    print("\n========================================================")
    print(f"[*] 2기 신도시 게이트 판정 결과: {report['gate_decision']}")
    print(f"[*] 3종 날짜 후보 충족 지구: {report['valid_districts_count']}")
    print(f"[*] Day/Month 정밀도 충족 지구: {report['high_precision_count']}")
    print("========================================================")
    for dist, d in report["districts_detail"].items():
        match_str = "[O] 일치" if d["mode_match"] else "[X] 불일치(수단 재검토 필요)"
        print(f"\n[{dist}]")
        print(f"  - 최초 입주: {d['occupancy_first_actual']}")
        print(f"  - 약속 일자: {d['promise']}")
        print(f"  - 실제 개통: {d['actual_operation']}")
        print(f"  - 수단 일치: {match_str}")



if __name__ == "__main__":
    print_gate_report()
