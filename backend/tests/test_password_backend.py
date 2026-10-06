def test_password_roundtrip_pwdlib_only():
    from detect_ai.shared.kernel import security as sec

    assert sec._password_hash is not None
    assert not hasattr(sec, "_legacy_context")
    h = sec.get_password_hash("Mat_khau-123")
    assert sec.verify_password("Mat_khau-123", h) is True
    assert sec.verify_password("sai", h) is False


def test_seed_bcrypt_hash_readable_by_pwdlib():
    from detect_ai.shared.kernel import security as sec

    seed_hash = "$2b$12$j7D8K3jeMgvKWaxk6Uwa6OrY37nj/dAJ2Ouel7iCMrZnT/Y.5ISvC"
    assert sec.verify_password("123456", seed_hash) is True
