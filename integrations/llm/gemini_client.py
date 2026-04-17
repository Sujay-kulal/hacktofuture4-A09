from __future__ import annotations

import json
import logging
import re
import time
from hashlib import sha256
from typing import Any

import httpx

from app.models import TelemetryEvent

logger = logging.getLogger("selfheal.gemini")


class GeminiAutomationClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        fallback_models: list[str] | None = None,
        max_retries: int = 3,
        cache_seconds: int = 600,
        rate_limit_cooldown_seconds: int = 60,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.fallback_models = fallback_models or []
        self.max_retries = max_retries
        self.cache_seconds = cache_seconds
        self.rate_limit_cooldown_seconds = rate_limit_cooldown_seconds
        self.last_error: str | None = None
        self.cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self.rate_limited_until = 0.0

    def analyze_event(self, event: TelemetryEvent) -> dict[str, Any] | None:
        prompt = (
            "You are an SRE assistant for Kubernetes incident response. "
            "Analyze this telemetry event and return strict JSON with keys "
            "'root_cause' and 'confidence'. Keep root_cause short.\n\n"
            f"{self._event_payload(event)}"
        )
        result = self._generate_json(prompt)
        if result is None:
            logger.warning("Gemini RCA returned no usable result for service=%s scenario=%s", event.service, event.scenario)
        else:
            logger.info("Gemini RCA returned a usable result for service=%s scenario=%s", event.service, event.scenario)
        return result

    def recommend_action(
        self,
        event: TelemetryEvent,
        root_cause: str,
        playbook_action: str,
    ) -> dict[str, Any] | None:
        prompt = (
            "You are an SRE remediation planner for Kubernetes. "
            "Choose the safest action for this incident. "
            "Return strict JSON with keys 'action', 'target_kind', 'parameters', and 'reason'. "
            "Only choose one of these actions: restart_deployment, scale_deployment, rollback_deployment. "
            "Prefer safe low-blast-radius actions. "
            f"If unsure, use '{playbook_action}'.\n\n"
            f"Estimated root cause: {root_cause}\n"
            f"{self._event_payload(event)}"
        )
        result = self._generate_json(prompt)
        if result is None:
            logger.warning(
                "Gemini remediation returned no usable result for service=%s scenario=%s",
                event.service,
                event.scenario,
            )
        else:
            logger.info(
                "Gemini remediation returned a usable result for service=%s scenario=%s",
                event.service,
                event.scenario,
            )
        return result

    def explain_decision(
        self,
        event: TelemetryEvent,
        *,
        incident_id: str | None,
        root_cause: str | None,
        action: str | None,
    ) -> dict[str, Any] | None:
        prompt = (
            "You are explaining an autonomous Kubernetes incident response decision to hackathon judges. "
            "Use only the evidence provided. Return strict JSON with keys "
            "'explanation', 'evidence', and 'leader_summary'. "
            "'explanation' should clearly say how the model used symptoms, metrics, logs, and traces if present. "
            "'evidence' must be a short list of concrete signal strings. "
            "'leader_summary' must be a 1-2 sentence high-level pitch.\n\n"
            f"incident_id={incident_id}\n"
            f"root_cause={root_cause}\n"
            f"action={action}\n"
            f"{self._event_payload(event)}"
        )
        result = self._generate_json(prompt)
        if result is None:
            logger.warning(
                "Gemini explanation returned no usable result for service=%s scenario=%s",
                event.service,
                event.scenario,
            )
        else:
            logger.info(
                "Gemini explanation returned a usable result for service=%s scenario=%s",
                event.service,
                event.scenario,
            )
        return result

    def _event_payload(self, event: TelemetryEvent) -> str:
        return json.dumps(
            {
                "scenario": event.scenario,
                "service": event.service,
                "namespace": event.namespace,
                "symptoms": event.symptoms,
                "metrics": event.metrics,
                "logs": event.logs[:5],
                "traces": event.traces[:5],
                "metadata": event.metadata,
            }
        )

    def _generate_json(self, prompt: str) -> dict[str, Any] | None:
        self.last_error = None
        cache_key = sha256(prompt.encode("utf-8")).hexdigest()
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.info("Gemini cache hit")
            return cached

        if time.time() < self.rate_limited_until:
            self.last_error = (
                f"Gemini HTTP 429 cooldown active for {int(self.rate_limited_until - time.time())}s"
            )
            logger.warning("Gemini request skipped because rate-limit cooldown is active")
            return None

        models_to_try = [self.model, *self.fallback_models]
        hit_rate_limit = False

        for model_name in models_to_try:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = httpx.post(
                        f"{self.base_url}/models/{model_name}:generateContent",
                        headers={
                            "x-goog-api-key": self.api_key,
                            "Content-Type": "application/json",
                        },
                        json={
                            "contents": [
                                {
                                    "parts": [
                                        {
                                            "text": prompt,
                                        }
                                    ]
                                }
                            ],
                            "generationConfig": {
                                "temperature": 0.1,
                                "responseMimeType": "application/json",
                            },
                        },
                        timeout=20,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    
                    usage = payload.get("usageMetadata", {})
                    token_count = usage.get("totalTokenCount", 0)
                    if token_count > 0:
                        try:
                            from app.state import state
                            state.add_gemini_tokens(token_count)
                        except ImportError:
                            pass # For tests or isolated scripts

                    text = self._extract_text(payload)
                    if not text:
                        finish_reason = payload.get("candidates", [{}])[0].get("finishReason", "unknown")
                        self.last_error = f"Gemini returned no text (finishReason={finish_reason})"
                        logger.warning("Gemini response did not contain any text parts for model=%s", model_name)
                        break
                    logger.info("Gemini request succeeded with model=%s attempt=%s", model_name, attempt)
                    parsed = self._parse_json(text)
                    if parsed is not None:
                        self.cache[cache_key] = (time.time() + self.cache_seconds, parsed)
                        return parsed
                    self.last_error = "Gemini returned text that could not be parsed as JSON"
                    logger.warning(
                        "Gemini returned non-JSON content for model=%s attempt=%s text=%s",
                        model_name,
                        attempt,
                        text[:300],
                    )
                    break
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    self.last_error = f"Gemini HTTP {status_code}"
                    logger.error(
                        "Gemini request failed: model=%s attempt=%s status=%s error=%s",
                        model_name,
                        attempt,
                        status_code,
                        exc,
                    )
                    if status_code == 429:
                        hit_rate_limit = True
                        break
                    if status_code in {500, 503, 504} and attempt < self.max_retries:
                        time.sleep(min(2 ** (attempt - 1), 5))
                        continue
                    if status_code in {500, 503, 504}:
                        break
                    return None
                except Exception as exc:
                    self.last_error = str(exc)
                    logger.error("Gemini request failed: model=%s attempt=%s error=%s", model_name, attempt, exc)
                    return None
            if hit_rate_limit:
                continue

        if hit_rate_limit:
            self.rate_limited_until = time.time() + self.rate_limit_cooldown_seconds
            self.last_error = f"Gemini HTTP 429"

        return None

    def _extract_text(self, payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates", [])
        if not candidates:
            return ""

        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(str(part.get("text", "")) for part in parts)

    def _parse_json(self, text: str) -> dict[str, Any] | None:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        candidates = [cleaned]
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidates.append(cleaned[start : end + 1])

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    def _get_cached(self, cache_key: str) -> dict[str, Any] | None:
        cached = self.cache.get(cache_key)
        if not cached:
            return None
        expires_at, payload = cached
        if expires_at < time.time():
            self.cache.pop(cache_key, None)
            return None
        return payload
