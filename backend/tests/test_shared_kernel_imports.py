from __future__ import annotations


def test_kernel_imports():
    from detect_ai.shared.kernel import config, database, security, timeutil, pagination, deps  # noqa
    assert config is not None


def test_kernel_supabase_and_errors_imports():
    from detect_ai.shared.kernel import supabase, errors  # noqa
    assert supabase is not None
    assert errors is not None
    assert hasattr(errors, "integrity_error_handler")
