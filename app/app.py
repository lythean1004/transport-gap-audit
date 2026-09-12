"""Transport Gap Audit - Main Application Entry Point."""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config import get_pilots_config, get_thresholds_config


def main():
    """Main application runner."""
    print("==========================================")
    print("🚗 Transport Gap Audit System")
    print("==========================================")
    
    thresholds = get_thresholds_config()
    pilots = get_pilots_config()
    
    print(f"[*] 임계치 설정 로드 완료: {len(thresholds)} 개 카테고리")
    print(f"[*] 시범 대상지 로드 완료: {len(pilots.get('pilots', []))} 개 지역")
    print("시스템이 정상적으로 준비되었습니다.")


if __name__ == "__main__":
    main()
