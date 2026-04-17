from app.state import AppState


def test_demo_checkout_fails_when_dependency_is_down() -> None:
    app_state = AppState()
    app_state.set_demo_dependency(True, "test")

    result = app_state.process_demo_checkout()

    assert result.success is False
    assert result.status_code == 503
    assert result.status.dependency_down is True


def test_demo_checkout_succeeds_when_healthy() -> None:
    app_state = AppState()
    app_state.set_demo_dependency(False, "test")

    result = app_state.process_demo_checkout()

    assert result.success is True
    assert result.status_code == 200
    assert result.order_id is not None
