import sys
import socket
import pytest
from pathlib import Path

# Ensure root directory is always on sys.path
root = Path(__file__).resolve().parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

@pytest.fixture(autouse=True)
def block_network_for_gates(monkeypatch, request):
    """
    게이트 테스트 등에서 의도치 않은 네트워크 호출을 원천 차단하는 autouse 픽스처.
    socket.socket, socket.create_connection, socket.getaddrinfo를 모두 차단한다.
    @pytest.mark.allow_network 가 붙어있으면 차단을 건너뛴다 (opt-out).
    """
    if request.node.get_closest_marker("allow_network"):
        return

    # stop_gate 관련 테스트 실행 시 항상 강력한 네트워크 차단 적용
    if "stop_gate" in request.node.nodeid:
        def guarded(*args, **kwargs):
            raise RuntimeError("네트워크 호출 시도 감지! 게이트는 순수 파일 읽기 전용이어야 합니다.")
        monkeypatch.setattr(socket, "socket", guarded)
        monkeypatch.setattr(socket, "create_connection", guarded)
        monkeypatch.setattr(socket, "getaddrinfo", guarded)
