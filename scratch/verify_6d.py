import pandas as pd

df = pd.read_csv("exports/stop_candidates.csv")
print("=== 6D Candidate Summary ===")
print(f"Total rows: {len(df)}")
print(f"Unique clusters: {df['cluster_id'].nunique()}")
print(f"Columns: {list(df.columns)}")
print(f"Review status: {df['review_status'].value_counts().to_dict()}")
print(f"Reference missing count: {df['reference_missing'].sum()}")
print("\nSample rows (Top 2):")
print(df[['cluster_id', 'citycode', 'nodeid', 'nodenm', 'recomputed_dist_m', 'coord_delta_m', 'review_status']].head(5).to_string())

# Check nearest stop distribution
first_candidates = df.groupby('cluster_id').first().reset_index()
print("\nNearest stop distance stats:")
print(first_candidates['recomputed_dist_m'].describe())

gap_clusters = first_candidates[first_candidates['recomputed_dist_m'] > 800]
print(f"\nClusters with nearest stop > 800m (Gap Finding): {len(gap_clusters)}")
for _, r in gap_clusters.iterrows():
    print(f"  {r['cluster_id']} | nearest={r['nodenm']} ({r['nodeid']}) | dist={r['recomputed_dist_m']:.1f}m")
