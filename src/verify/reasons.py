from enum import Enum

class Reason(str, Enum):
    INPUT_NOT_PENDING           = "input_not_pending"
    G1_CITYCODE_MISSING         = "G1_citycode_missing"
    G1_RAW_MISSING              = "G1_raw_missing"
    G1_CITYCODE_NOT_IN_RAW      = "G1_citycode_not_in_raw_response"
    G2_STOP_NOT_FOUND           = "G2_stop_not_found_in_tago"
    G2_COORD_DELTA              = "G2_coord_delta_exceeded"
    G3_CLUSTER_NOT_FOUND        = "G3_cluster_not_found"
    G3_CLUSTER_AMBIGUOUS        = "G3_cluster_ambiguous"
    G3_INVALID_CRS              = "G3_invalid_crs"
    G3_DISTANCE                 = "G3_distance_exceeded"
    G4_NO_BUS_RUNNING_NOW       = "no_bus_running_now"      # 정류소 무효 아님 (ok_empty)
    G4_API_ERROR                = "G4_api_error"
    G4_NOT_WEEKDAY              = "not_weekday"
    G4_OUTSIDE_HOURS            = "outside_business_hours"
    G4_EVIDENCE_MISSING         = "G4_evidence_missing"
    G4_STALE_SMOKE              = "G4_stale_smoke"
    G5_INVALID_METHOD           = "G5_invalid_method"
    G5_MISSING_VERIFIER         = "G5_missing_verifier"
    G5_INVALID_VERIFIED_AT      = "G5_invalid_verified_at"
    G6_NO_DIRECTION             = "G6_direction_label_missing"
    G6_DIRECTION_EQUALS_NODENM  = "G6_direction_equals_nodenm"

ALLOWED = frozenset(Reason)
