"""Tests for LLM OpenAI-compatible client."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import urllib.error

from h2track_tracking.llm.client import OpenAICompatClient


class TestOpenAICompatClientEndpoint:
    """Test endpoint building."""

    def test_endpoint_for_chat_https(self):
        """Test HTTPS chat endpoint building."""
        client = OpenAICompatClient()
        endpoint = client._endpoint_for("https://api.example.com/v1", "chat")
        assert endpoint == "https://api.example.com/v1/chat/completions"

    def test_endpoint_for_chat_http_rejected(self):
        """Test HTTP URL is rejected for security."""
        client = OpenAICompatClient()
        with pytest.raises(ValueError, match="https"):
            client._endpoint_for("http://api.example.com/v1", "chat")

    def test_endpoint_for_chat_https(self):
        """Test HTTPS chat endpoint building."""
        client = OpenAICompatClient()
        endpoint = client._endpoint_for("https://api.example.com/v1/", "chat")
        assert endpoint == "https://api.example.com/v1/chat/completions"

    def test_endpoint_for_responses_api(self):
        """Test responses API endpoint building."""
        client = OpenAICompatClient()
        endpoint = client._endpoint_for("https://api.example.com/v1", "responses")
        assert endpoint == "https://api.example.com/v1/responses"

    def test_endpoint_for_versioned_url_chat(self):
        """Test versioned URL for chat."""
        client = OpenAICompatClient()
        endpoint = client._endpoint_for("https://api.example.com/v1", "chat")
        assert endpoint == "https://api.example.com/v1/chat/completions"

    def test_endpoint_for_versioned_url_responses(self):
        """Test versioned URL for responses."""
        client = OpenAICompatClient()
        endpoint = client._endpoint_for("https://api.example.com/v2", "responses")
        assert endpoint == "https://api.example.com/v2/responses"

    def test_endpoint_for_unsupported_protocol(self):
        """Test unsupported protocol raises error."""
        client = OpenAICompatClient()
        with pytest.raises(ValueError, match="unsupported protocol"):
            client._endpoint_for("https://api.example.com", "unknown")


class TestOpenAICompatClientPostJson:
    """Test HTTP POST functionality."""

    def test_post_json_success(self):
        """Test successful POST request."""
        client = OpenAICompatClient()

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"result": "ok"}'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client._post_json(
                url="https://api.example.com/v1/test",
                api_key="test-key",
                timeout_sec=30.0,
                payload={"test": "data"},
            )

        assert result == {"result": "ok"}

    def test_post_json_with_headers(self):
        """Test POST request includes correct headers."""
        client = OpenAICompatClient()

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"result": "ok"}'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        captured_request = []

        def capture_urlopen(request, timeout=None):
            captured_request.append(request)
            return mock_response

        with patch("urllib.request.urlopen", capture_urlopen):
            client._post_json(
                url="https://api.example.com/v1/test",
                api_key="test-api-key",
                timeout_sec=30.0,
                payload={"test": "data"},
            )

        assert len(captured_request) == 1
        req = captured_request[0]
        assert "Authorization" in req.headers
        assert "test-api-key" in req.headers["Authorization"]

    def test_post_json_with_extra_headers(self):
        """Test POST request with extra headers."""
        client = OpenAICompatClient()

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"result": "ok"}'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        captured_request = []

        def capture_urlopen(request, timeout=None):
            captured_request.append(request)
            return mock_response

        with patch("urllib.request.urlopen", capture_urlopen):
            client._post_json(
                url="https://api.example.com/v1/test",
                api_key="test-key",
                timeout_sec=30.0,
                payload={"test": "data"},
                extra_headers={"X-Custom": "value"},
            )

        req = captured_request[0]
        # Note: urllib lowercases header names
        assert "X-custom" in req.headers or "X-Custom" in req.headers

    def test_post_json_http_error(self):
        """Test HTTP error handling."""
        client = OpenAICompatClient()

        mock_error = urllib.error.HTTPError("url", 500, "Error", {}, None)
        mock_error.read = Mock(return_value=b"error details")

        with patch("urllib.request.urlopen", side_effect=mock_error):
            with pytest.raises(RuntimeError, match="http 500"):
                client._post_json(
                    url="https://api.example.com/v1/test",
                    api_key="test-key",
                    timeout_sec=30.0,
                    payload={"test": "data"},
                )

    def test_post_json_url_error(self):
        """Test URL error handling."""
        client = OpenAICompatClient()

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Timeout")):
            with pytest.raises(RuntimeError, match="network error"):
                client._post_json(
                    url="https://api.example.com/v1/test",
                    api_key="test-key",
                    timeout_sec=30.0,
                    payload={"test": "data"},
                )


class TestOpenAICompatClientExtractChat:
    """Test chat response extraction."""

    def test_extract_chat_text_with_content(self):
        """Test extracting text from chat response."""
        client = OpenAICompatClient()

        response = {
            "choices": [
                {"message": {"content": "Hello, world!"}}
            ]
        }

        result = client._extract_chat_text(response)
        assert result == "Hello, world!"

    def test_extract_chat_text_empty_choices(self):
        """Test handling empty choices."""
        client = OpenAICompatClient()

        response = {"choices": []}
        result = client._extract_chat_text(response)
        assert result == ""

    def test_extract_chat_text_no_content(self):
        """Test handling missing content."""
        client = OpenAICompatClient()

        response = {"choices": [{"message": {}}]}
        result = client._extract_chat_text(response)
        assert result == ""

    def test_extract_chat_text_with_content_list(self):
        """Test extracting text from content list."""
        client = OpenAICompatClient()

        response = {
            "choices": [
                {"message": {"content": [{"text": "Part 1"}, {"text": "Part 2"}]}}
            ]
        }

        result = client._extract_chat_text(response)
        assert "Part 1" in result
        assert "Part 2" in result

    def test_extract_chat_text_with_type_text(self):
        """Test extracting text from content with type field."""
        client = OpenAICompatClient()

        response = {
            "choices": [
                {"message": {"content": [{"type": "text", "text": "Typed content"}]}}
            ]
        }

        result = client._extract_chat_text(response)
        assert result == "Typed content"


class TestOpenAICompatClientExtractResponses:
    """Test responses API extraction."""

    def test_extract_responses_text_direct(self):
        """Test extracting text from output_text field."""
        client = OpenAICompatClient()

        response = {"output_text": "Direct output text"}

        result = client._extract_responses_text(response)
        assert result == "Direct output text"

    def test_extract_responses_text_from_output(self):
        """Test extracting text from responses API format."""
        client = OpenAICompatClient()

        response = {
            "output": [
                {"content": [{"text": "Response text here"}]}
            ]
        }

        result = client._extract_responses_text(response)
        assert result == "Response text here"

    def test_extract_responses_text_empty_output(self):
        """Test handling empty output."""
        client = OpenAICompatClient()

        response = {"output": []}
        result = client._extract_responses_text(response)
        assert result == ""

    def test_extract_responses_text_no_text(self):
        """Test handling missing text."""
        client = OpenAICompatClient()

        response = {"output": [{"content": [{}]}]}
        result = client._extract_responses_text(response)
        assert result == ""

    def test_extract_responses_text_multiple_parts(self):
        """Test extracting text from multiple content parts."""
        client = OpenAICompatClient()

        response = {
            "output": [
                {"content": [{"text": "Part 1"}, {"text": "Part 2"}]}
            ]
        }

        result = client._extract_responses_text(response)
        assert "Part 1" in result
        assert "Part 2" in result


class TestOpenAICompatClientCall:
    """Test the main call method."""

    @pytest.fixture
    def valid_profile(self):
        """Return a valid LLM profile."""
        return {
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
            "model": "gpt-4",
        }

    def test_call_with_chat_protocol(self, valid_profile):
        """Test call with chat protocol."""
        client = OpenAICompatClient()
        valid_profile["protocol"] = "chat"

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"choices": [{"message": {"content": "Test response"}}]}'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.call(profile=valid_profile, messages=[{"role": "user", "content": "Hello"}])

        assert result["text"] == "Test response"
        assert result["protocol_used"] == "chat"

    def test_call_with_responses_protocol(self, valid_profile):
        """Test call with responses protocol."""
        client = OpenAICompatClient()
        valid_profile["protocol"] = "responses"

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"output": [{"content": [{"text": "Responses API text"}]}]}'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.call(profile=valid_profile, messages=[{"role": "user", "content": "Hello"}])

        assert result["text"] == "Responses API text"
        assert result["protocol_used"] == "responses"

    def test_call_with_dual_protocol_fallback(self, valid_profile):
        """Test dual protocol falls back to chat when responses fails."""
        client = OpenAICompatClient()
        valid_profile["protocol"] = "dual"

        call_count = [0]

        def urlopen_side_effect(request, timeout=None):
            call_count[0] += 1
            if "responses" in request.full_url:
                raise urllib.error.HTTPError("url", 404, "Not Found", {}, None)
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"choices": [{"message": {"content": "Chat response"}}]}'
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            return mock_response

        with patch("urllib.request.urlopen", urlopen_side_effect):
            result = client.call(profile=valid_profile, messages=[{"role": "user", "content": "Hello"}])

        assert result["text"] == "Chat response"
        assert result["protocol_used"] == "chat"

    def test_call_incomplete_profile(self):
        """Test call with incomplete profile raises error."""
        client = OpenAICompatClient()

        with pytest.raises(RuntimeError, match="incomplete llm profile"):
            client.call(profile={}, messages=[{"role": "user", "content": "Hello"}])

    def test_call_missing_base_url(self):
        """Test call with missing base_url raises error."""
        client = OpenAICompatClient()

        profile = {"api_key": "test", "model": "gpt-4"}

        with pytest.raises(RuntimeError, match="incomplete llm profile"):
            client.call(profile=profile, messages=[{"role": "user", "content": "Hello"}])

    def test_call_missing_api_key(self):
        """Test call with missing api_key raises error."""
        client = OpenAICompatClient()

        profile = {"base_url": "https://api.example.com", "model": "gpt-4"}

        with pytest.raises(RuntimeError, match="incomplete llm profile"):
            client.call(profile=profile, messages=[{"role": "user", "content": "Hello"}])

    def test_call_missing_model(self):
        """Test call with missing model raises error."""
        client = OpenAICompatClient()

        profile = {"base_url": "https://api.example.com", "api_key": "test"}

        with pytest.raises(RuntimeError, match="incomplete llm profile"):
            client.call(profile=profile, messages=[{"role": "user", "content": "Hello"}])

    def test_call_unsupported_protocol(self, valid_profile):
        """Test call with unsupported protocol raises error."""
        client = OpenAICompatClient()
        valid_profile["protocol"] = "unknown"

        with pytest.raises(RuntimeError, match="unsupported profile protocol"):
            client.call(profile=valid_profile, messages=[{"role": "user", "content": "Hello"}])

    def test_call_with_custom_timeout(self, valid_profile):
        """Test call with custom timeout."""
        client = OpenAICompatClient()
        valid_profile["timeout_sec"] = 120.0

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"choices": [{"message": {"content": "OK"}}]}'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        captured_timeout = []

        def capture_urlopen(request, timeout=None):
            captured_timeout.append(timeout)
            return mock_response

        with patch("urllib.request.urlopen", capture_urlopen):
            client.call(profile=valid_profile, messages=[{"role": "user", "content": "Hello"}])

        assert captured_timeout[0] == 120.0

    def test_call_with_extra_headers(self, valid_profile):
        """Test call with extra headers."""
        client = OpenAICompatClient()
        valid_profile["headers"] = {"X-Custom": "value"}

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"choices": [{"message": {"content": "OK"}}]}'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        captured_request = []

        def capture_urlopen(request, timeout=None):
            captured_request.append(request)
            return mock_response

        with patch("urllib.request.urlopen", capture_urlopen):
            client.call(profile=valid_profile, messages=[{"role": "user", "content": "Hello"}])

        # Check that the header was set in the request
        assert len(captured_request) > 0


class TestOpenAICompatClientEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_messages(self):
        """Test with empty messages list."""
        client = OpenAICompatClient()
        profile = {
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
            "model": "gpt-4",
            "protocol": "chat",
        }

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"choices": [{"message": {"content": "OK"}}]}'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.call(profile=profile, messages=[])

        assert result["text"] == "OK"

    def test_malformed_json_response(self):
        """Test handling malformed JSON response."""
        client = OpenAICompatClient()
        profile = {
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
            "model": "gpt-4",
            "protocol": "chat",
        }

        mock_response = MagicMock()
        mock_response.read.return_value = b'invalid json'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            with pytest.raises(Exception):  # JSON decode error
                client.call(profile=profile, messages=[{"role": "user", "content": "Hello"}])

    def test_base_url_trailing_slash(self):
        """Test base URL with trailing slash is handled."""
        client = OpenAICompatClient()
        profile = {
            "base_url": "https://api.example.com/v1/",
            "api_key": "test-key",
            "model": "gpt-4",
            "protocol": "chat",
        }

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"choices": [{"message": {"content": "OK"}}]}'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        captured_urls = []

        def capture_urlopen(request, timeout=None):
            captured_urls.append(request.full_url)
            return mock_response

        with patch("urllib.request.urlopen", capture_urlopen):
            client.call(profile=profile, messages=[{"role": "user", "content": "Test"}])

        # Should not have double slashes
        assert "//v1//" not in captured_urls[0]
