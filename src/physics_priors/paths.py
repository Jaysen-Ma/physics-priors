"""Locate the checkout used by the data-driven commands."""

import hashlib
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent


def _find_checkout() -> Path | None:
    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents, *PACKAGE_DIR.parents):
        if (candidate / "src" / "physics_priors" / "__init__.py").is_file() and (
            candidate / "data" / "catalog" / "index.html").is_file():
            return candidate
    return None


_checkout = _find_checkout()
ROOT = _checkout if _checkout is not None else Path.cwd()


def require_checkout() -> None:
    if _checkout is None:
        raise SystemExit("This command needs a physics-priors repository checkout. Run it from the checkout that contains data/catalog/.")


def code_hashes(package_paths: list[str]) -> dict[str, str]:
    """Hash the installed code and label it with its path in the source tree."""
    return {f"src/physics_priors/{name}": hashlib.sha256((PACKAGE_DIR / name).read_bytes()).hexdigest()
            for name in package_paths}
