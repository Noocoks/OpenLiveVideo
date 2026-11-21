from unittest.mock import Mock
import requests
import pytest
from shortsfactory.providers.pixabay import PixabayClient, PixabayError

def test_requires_api_key():
    with pytest.raises(PixabayError, match="API key"):
        PixabayClient("")

def test_search_sends_safe_query_and_returns_hits(monkeypatch):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"hits": [{"id": 42}]}
    get = Mock(return_value=response)
    monkeypatch.setattr(requests, "get", get)
    client = PixabayClient("secret")
    assert client.search_videos("dark hallway", per_page=12) == [{"id": 42}]
    assert get.call_args.kwargs["params"]["q"] == "dark hallway"
    assert get.call_args.kwargs["params"]["safesearch"] == "true"

def test_video_quality_fallback():
    url, quality = PixabayClient.choose_video({"videos": {
        "large": {}, "medium": {"url": "https://cdn.example/video.mp4"}}})
    assert (url, quality) == ("https://cdn.example/video.mp4", "medium")

def test_pixabay_request_error_redacts_api_key(monkeypatch):
    key = "sensitive-api-key"
    def fail_request(*args, **kwargs):
        raise requests.RequestException(f"https://pixabay.com/api/videos/?key={key}")
    monkeypatch.setattr("shortsfactory.providers.pixabay.requests.get", fail_request)

    with pytest.raises(PixabayError) as error:
        PixabayClient(key).search_videos("dark forest")

    assert key not in str(error.value)
    assert "[REDACTED]" in str(error.value)
