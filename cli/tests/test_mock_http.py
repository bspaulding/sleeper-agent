from __future__ import annotations

import requests

from tests.support.mock_http import Request, Response, mock_http_server


def test_round_trips_a_scripted_response() -> None:
    def handler(request: Request) -> Response:
        assert request.method == "GET"
        assert request.path == "/ping"
        return Response(
            status=200, headers={"Content-Type": "text/plain"}, body=b"pong"
        )

    with mock_http_server(handler) as base_url:
        response = requests.get(f"{base_url}/ping", timeout=5)

    assert response.status_code == 200
    assert response.text == "pong"


def test_server_shuts_down_cleanly_and_reports_request_body() -> None:
    received: list[Request] = []

    def handler(request: Request) -> Response:
        received.append(request)
        return Response(status=201, body=b"{}")

    with mock_http_server(handler) as base_url:
        response = requests.post(f"{base_url}/things", data=b"hello", timeout=5)
        assert response.status_code == 201

    assert len(received) == 1
    assert received[0].method == "POST"
    assert received[0].path == "/things"
    assert received[0].body == b"hello"
