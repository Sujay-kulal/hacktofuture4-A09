from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent


def _as_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    app_name: str = "agentic-self-healing-cloud"
    kube_mode: str = os.getenv("SELFHEAL_KUBE_MODE", "mock")
    policies_file: Path = BASE_DIR / "policies" / "default.yaml"
    playbooks_file: Path = BASE_DIR / "playbooks" / "default.yaml"
    default_namespace: str = os.getenv("SELFHEAL_NAMESPACE", "demo")
    telemetry_claim_timeout_seconds: int = int(os.getenv("SELFHEAL_CLAIM_TIMEOUT_SECONDS", "300"))
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/selfheal",
    )
    prometheus_url: str | None = os.getenv("PROMETHEUS_URL")
    loki_url: str | None = os.getenv("LOKI_URL")
    trace_url: str | None = os.getenv("TRACE_URL")
    trace_backend: str = os.getenv("TRACE_BACKEND", "tempo")
    tracing_enabled: bool = _as_bool("OTEL_TRACING_ENABLED", "false")
    otel_service_name: str = os.getenv("OTEL_SERVICE_NAME", "selfheal-api")
    otel_exporter_otlp_endpoint: str | None = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    telemetry_mode: str = os.getenv("SELFHEAL_TELEMETRY_MODE", "mock")
    static_dir: Path = BASE_DIR / "frontend"
    dependency_graph_file: Path = BASE_DIR / "dependencies" / "default.yaml"
    background_monitoring_enabled: bool = _as_bool("SELFHEAL_BACKGROUND_MONITORING", "false")
    background_monitoring_interval_seconds: int = int(os.getenv("SELFHEAL_MONITOR_INTERVAL_SECONDS", "30"))
    background_monitoring_max_events_per_scan: int = int(os.getenv("SELFHEAL_MONITOR_MAX_EVENTS_PER_SCAN", "5"))
    background_monitoring_max_queue_depth: int = int(os.getenv("SELFHEAL_MONITOR_MAX_QUEUE_DEPTH", "25"))
    background_monitor_namespaces: list[str] = [
        item.strip() for item in os.getenv("SELFHEAL_MONITOR_NAMESPACES", "").split(",") if item.strip()
    ]
    prometheus_restart_threshold: float = float(os.getenv("PROM_RESTART_THRESHOLD", "3"))
    prometheus_error_rate_threshold: float = float(os.getenv("PROM_ERROR_RATE_THRESHOLD", "0.1"))
    prometheus_latency_threshold_ms: float = float(os.getenv("PROM_LATENCY_THRESHOLD_MS", "1500"))
    loki_error_log_threshold: float = float(os.getenv("LOKI_ERROR_LOG_THRESHOLD", "3"))
    trace_error_threshold: float = float(os.getenv("TRACE_ERROR_THRESHOLD", "1"))
    prometheus_restart_query: str = os.getenv(
        "PROM_RESTART_QUERY",
        'sum(increase(kube_pod_container_status_restarts_total{namespace="{namespace}", pod=~"{service}.*"}[10m]))',
    )
    prometheus_ready_query: str = os.getenv(
        "PROM_READY_QUERY",
        'sum(kube_deployment_status_replicas_available{namespace="{namespace}", deployment="{service}"})',
    )
    prometheus_desired_query: str = os.getenv(
        "PROM_DESIRED_QUERY",
        'sum(kube_deployment_spec_replicas{namespace="{namespace}", deployment="{service}"})',
    )
    prometheus_error_rate_query: str = os.getenv(
        "PROM_ERROR_RATE_QUERY",
        'sum(rate(http_requests_total{namespace="{namespace}", service="{service}", status=~"5.."}[5m])) / clamp_min(sum(rate(http_requests_total{namespace="{namespace}", service="{service}"}[5m])), 0.001)',
    )
    prometheus_latency_query: str = os.getenv(
        "PROM_LATENCY_QUERY",
        'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{namespace="{namespace}", service="{service}"}[5m])) by (le)) * 1000',
    )
    loki_error_query: str = os.getenv(
        "LOKI_ERROR_QUERY",
        'sum(count_over_time({namespace="{namespace}", app="{service}"} |= "error"[5m]))',
    )
    tempo_traceql_query: str = os.getenv(
        "TEMPO_TRACEQL_QUERY",
        '{ resource.service.name = "{service}" && status = error }',
    )
    jaeger_trace_service_tag: str = os.getenv("JAEGER_TRACE_TAGS", '{"error":"true"}')
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_fallback_models: list[str] = [
        item.strip() for item in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.0-flash").split(",") if item.strip()
    ]
    gemini_max_retries: int = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
    gemini_cache_seconds: int = int(os.getenv("GEMINI_CACHE_SECONDS", "600"))
    gemini_rate_limit_cooldown_seconds: int = int(os.getenv("GEMINI_RATE_LIMIT_COOLDOWN_SECONDS", "60"))
    automation_mode: str = os.getenv("SELFHEAL_AUTOMATION_MODE", "hybrid")
    gemini_base_url: str = os.getenv(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta",
    )


settings = Settings()
