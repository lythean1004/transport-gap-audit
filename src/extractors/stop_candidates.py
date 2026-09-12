import sys
import pandas as pd
import polars as pl
from pathlib import Path
import yaml

def main():
    nearby_path = Path("data/staged/tago_stops_nearby.parquet")
    full_path = Path("data/staged/tago_stops_full.parquet")
    
    if not nearby_path.exists():
        print(f"[오류] {nearby_path} 파일이 없습니다. (6C 작업 선행 필요)")
        # 6C에서 좌표가 없어 파일이 생성되지 않은 상태라면 빈 CSV라도 스키마를 맞춰서 출력하도록 해야 합니다.
        df_nearby = pl.DataFrame(schema={
            "cluster_id": pl.Utf8, "citycode": pl.Utf8, "nodeid": pl.Utf8,
            "nodenm": pl.Utf8, "gpslati": pl.Float64, "gpslong": pl.Float64,
            "api_radius_claim_m": pl.Int64, "recomputed_dist_m": pl.Float64,
            "coord_delta_m": pl.Float64
        })
    else:
        df_nearby = pl.read_parquet(nearby_path)
        
    if full_path.exists():
        df_full = pl.read_parquet(full_path)
    else:
        df_full = pl.DataFrame(schema={
            "citycode": pl.Utf8, "nodeid": pl.Utf8, "nodeno": pl.Utf8,
            "gpslati": pl.Float64, "gpslong": pl.Float64
        })

    # Convert to pandas for easier manipulation
    pdf_nearby = df_nearby.to_pandas()
    pdf_full = df_full.to_pandas()
    
    # Clean string keys just in case
    pdf_nearby['citycode'] = pdf_nearby['citycode'].astype(str).str.strip()
    pdf_nearby['nodeid'] = pdf_nearby['nodeid'].astype(str).str.strip()
    
    pdf_full['citycode'] = pdf_full['citycode'].astype(str).str.strip()
    pdf_full['nodeid'] = pdf_full['nodeid'].astype(str).str.strip()

    # Create mapping from full stops
    full_dict = {}
    for _, row in pdf_full.iterrows():
        key = (row['citycode'], row['nodeid'])
        full_dict[key] = {
            "nodeno": row.get("nodeno", ""),
            "list_lat": row.get("gpslati", None),
            "list_lon": row.get("gpslong", None)
        }
        
    records = []
    
    for _, row in pdf_nearby.iterrows():
        cluster_id = row['cluster_id']
        ccode = row['citycode']
        nodeid = row['nodeid']
        key = (ccode, nodeid)
        
        full_info = full_dict.get(key, {})
        
        ref_missing = (key not in full_dict)
        coord_delta = row['coord_delta_m']
        
        # We need to sort by:
        # 1. reference_missing (False first)
        # 2. recomputed_dist_m (ascending)
        # 3. coord_delta_m (ascending, NaN last)
        
        records.append({
            "cluster_id": cluster_id,
            "citycode": ccode,
            "nodeid": nodeid,
            "nodenm": row['nodenm'],
            "nodeno": full_info.get('nodeno', ''),
            "api_lat": row['gpslati'],
            "api_lon": row['gpslong'],
            "list_lat": full_info.get('list_lat', None),
            "list_lon": full_info.get('list_lon', None),
            "coord_delta_m": coord_delta,
            "recomputed_dist_m": row['recomputed_dist_m'],
            "api_radius_claim_m": row['api_radius_claim_m'],
            "reference_missing": ref_missing,
            "direction_label": "",
            "has_trunk_route": "",
            "smoke_test_at": "",
            "smoke_result": "",
            "raw_snapshot_path": "",
            "review_status": "ai_draft",
            "verified_by": "",
            "verified_at": "",
            "reject_reason": ""
        })
        
    if not records:
        print("[알림] 입력 데이터가 없어 빈 형식의 exports/stop_candidates.csv를 생성합니다.")
        df_out = pd.DataFrame(columns=[
            "cluster_id", "citycode", "nodeid", "nodenm", "nodeno",
            "api_lat", "api_lon", "list_lat", "list_lon", "coord_delta_m",
            "recomputed_dist_m", "api_radius_claim_m", "reference_missing",
            "direction_label", "has_trunk_route", "smoke_test_at", "smoke_result",
            "raw_snapshot_path", "review_status", "verified_by", "verified_at", "reject_reason"
        ])
    else:
        df_out = pd.DataFrame(records)
        
        # Fill NA for coord_delta_m so we can sort properly. Using a large number to rank it last.
        df_out['sort_delta'] = df_out['coord_delta_m'].fillna(9999999.0)
        
        # Sort by: reference_missing (asc), recomputed_dist_m (asc), sort_delta (asc)
        df_out = df_out.sort_values(
            by=["cluster_id", "reference_missing", "recomputed_dist_m", "sort_delta"],
            ascending=[True, True, True, True]
        )
        
        # Take top 6 per cluster
        df_out = df_out.groupby("cluster_id").head(6)
        
        # Drop temporary sorting column
        df_out = df_out.drop(columns=["sort_delta"])
        
        # Flag clusters where the nearest stop exceeds 800m
        # Since it's sorted, the first row per cluster is the nearest.
        nearest_stops = df_out.groupby("cluster_id").first().reset_index()
        for _, n_row in nearest_stops.iterrows():
            if n_row['recomputed_dist_m'] > 800:
                print(f"[발견] {n_row['cluster_id']} 클러스터의 최근접 정류소가 800m를 초과합니다 ({n_row['recomputed_dist_m']:.1f}m).")
                print("   -> 이는 분석 결과(Finding)이며, 충족을 위해 좌표를 임의로 옮기지 마십시오.")
                
    out_dir = Path("exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(out_dir / "stop_candidates.csv", index=False, encoding='utf-8-sig')
    
    print(f"\n[완료] 랭킹 생성 완료: exports/stop_candidates.csv (총 {len(df_out)}건)")

if __name__ == "__main__":
    main()
