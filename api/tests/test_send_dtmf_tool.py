"""Tests for send_dtmf tool schema."""

from api.services.workflow.tools.send_dtmf import get_send_dtmf_tools


def test_get_send_dtmf_tools_schema():
    tools = get_send_dtmf_tools()
    assert len(tools) == 1
    func = tools[0]["function"]
    assert func["name"] == "send_dtmf"
    assert "digits" in func["parameters"]["properties"]
