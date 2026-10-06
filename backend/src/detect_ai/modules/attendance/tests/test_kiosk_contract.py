from __future__ import annotations

from detect_ai.main import app
from detect_ai.modules.attendance.presentation.kiosk_routes import router as kiosk_router
from detect_ai.modules.attendance.presentation.kiosk_ws import router as kiosk_ws_router
from detect_ai.modules.attendance.public import record_checkin


def test_kiosk_openapi_shape():
    """OpenAPI-shape test: paths + methods match HEAD, introspected via app.openapi()."""
    openapi = app.openapi()
    paths = openapi["paths"]

    expected_routes = {
        "/api/v1/kiosk/checkin": {"post"},
        "/api/v1/kiosk/gallery-status": {"get"},
        "/api/v1/kiosk/enroll/{user_id}": {"post"},
        "/api/v1/kiosk/backfill": {"post"},
        "/api/v1/kiosk/reset-session": {"post"},
    }

    for route, methods in expected_routes.items():
        assert route in paths, f"Missing route {route} in openapi"
        registered_methods = set(paths[route].keys())
        assert methods.issubset(registered_methods), (
            f"Route {route} missing methods: {methods - registered_methods}"
        )

    # WebSocket route in app routes
    all_routes = []
    for r in app.routes:
        if hasattr(r, "original_router") and r.original_router:
            all_routes.extend(r.original_router.routes)
        else:
            all_routes.append(r)
    ws_paths = [getattr(r, "path", None) for r in all_routes]
    assert "/api/v1/kiosk/ws" in ws_paths

    # Response schema introspection: status and schedule_id keys
    schemas = openapi.get("components", {}).get("schemas", {})
    assert "CheckinResponse" in schemas
    checkin_props = schemas["CheckinResponse"].get("properties", {})
    assert "schedule_id" in checkin_props

    # Status in paths (e.g. /api/v1/kiosk/gallery-status) and response codes
    kiosk_paths = [p for p in paths if "kiosk" in p]
    assert any("status" in p for p in kiosk_paths)

    checkin_responses = paths["/api/v1/kiosk/checkin"]["post"].get("responses", {})
    assert "200" in checkin_responses


def test_kiosk_shims_and_public():
    from detect_ai.modules.attendance.presentation.kiosk_routes import router as shim_kiosk
    from detect_ai.modules.attendance.presentation.kiosk_ws import router as shim_kiosk_ws

    assert shim_kiosk is kiosk_router
    assert shim_kiosk_ws is kiosk_ws_router
    assert callable(record_checkin)
