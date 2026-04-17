from integrations.llm.gemini_client import GeminiAutomationClient


def test_parse_json_accepts_code_fence_wrapped_payload() -> None:
    client = GeminiAutomationClient(
        api_key="test",
        model="gemini-2.5-flash",
        base_url="https://example.com",
    )

    parsed = client._parse_json("```json\n{\"root_cause\":\"dependency unavailable\",\"confidence\":0.82}\n```")

    assert parsed == {"root_cause": "dependency unavailable", "confidence": 0.82}


def test_parse_json_extracts_embedded_json_object() -> None:
    client = GeminiAutomationClient(
        api_key="test",
        model="gemini-2.5-flash",
        base_url="https://example.com",
    )

    parsed = client._parse_json(
        "Here is the diagnosis:\n{\"action\":\"restart_deployment\",\"target_kind\":\"Deployment\"}"
    )

    assert parsed == {"action": "restart_deployment", "target_kind": "Deployment"}


def test_parse_json_accepts_explanation_payload() -> None:
    client = GeminiAutomationClient(
        api_key="test",
        model="gemini-2.5-flash",
        base_url="https://example.com",
    )

    parsed = client._parse_json(
        '{"explanation":"Gemini used metrics and logs","evidence":["restarts=4","connection refused"],"leader_summary":"The system correlated telemetry and chose a safe fix."}'
    )

    assert parsed == {
        "explanation": "Gemini used metrics and logs",
        "evidence": ["restarts=4", "connection refused"],
        "leader_summary": "The system correlated telemetry and chose a safe fix.",
    }
