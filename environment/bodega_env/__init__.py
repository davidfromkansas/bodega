# load_environment is the verifiers Hub entry point. Guarded so that
# parser.py / rubric.py stay importable for unit tests without verifiers/browserbase.
try:  # pragma: no cover
    from .bodega_env import ShopBrowserEnv, load_environment  # noqa: F401
except Exception:  # verifiers/datasets not installed (local pure-logic tests)
    pass
