"""Regression tests for SSRF guards on web_fetch and api_call.

These ensure the workspace cannot be coerced into hitting localhost,
internal RFC1918 / link-local addresses, or non-http(s) schemes via
the LLM-callable tools.
"""
from __future__ import annotations

import pytest

from app.text_editor import TextEditorTool
from app.tools import ToolExecutor, _validate_public_http_url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/foo",
        "gopher://example.com/",
        "javascript:alert(1)",
    ],
)
def test_validate_rejects_non_http_schemes(url):
    with pytest.raises(Exception):
        _validate_public_http_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/admin",
        "http://127.0.0.1:8080",
        "http://0.0.0.0",
        "http://10.0.0.1",
        "http://192.168.1.1",
        "http://172.16.5.5",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://[::1]/",
        "http://[fd00::1]/",
    ],
)
def test_validate_rejects_internal_targets(url):
    with pytest.raises(Exception):
        _validate_public_http_url(url)


def test_validate_accepts_normal_https_url():
    assert _validate_public_http_url("https://example.com/foo").startswith("https://")
    assert _validate_public_http_url("http://example.com").startswith("http://")


def test_web_fetch_blocks_internal_url(workspace):
    t = ToolExecutor(workspace, text_editor=TextEditorTool(workspace))
    res = t.web_fetch("http://127.0.0.1:65000/whatever")
    assert not res.ok
    assert "internal" in res.output.lower() or "private" in res.output.lower()


def test_api_call_blocks_internal_url(workspace):
    t = ToolExecutor(workspace, text_editor=TextEditorTool(workspace))
    res = t.api_call("GET", "http://169.254.169.254/latest/meta-data/")
    assert not res.ok
    assert "internal" in res.output.lower() or "private" in res.output.lower()


def test_api_call_rejects_file_scheme(workspace):
    t = ToolExecutor(workspace, text_editor=TextEditorTool(workspace))
    res = t.api_call("GET", "file:///etc/passwd")
    assert not res.ok
    assert "http" in res.output.lower()
