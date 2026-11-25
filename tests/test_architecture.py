"""Architecture rules from the design doc, enforced by reading the source (no imports executed).

- Dependencies point inward: engine imports only schemas, eval7 and PokerKit; only engine.rules
  imports PokerKit; storage imports schemas only.
- The engine never calls a global random function, so seeded replay stays exact.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "pokersim"


def _modules(package: str) -> list[Path]:
    return sorted((SRC / package).rglob("*.py"))


def _imports(path: Path) -> set[str]:
    """Top-level names imported by a file, as dotted module paths."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def _pokersim_targets(path: Path) -> set[str]:
    return {m.split(".")[1] for m in _imports(path) if m.startswith("pokersim.") and "." in m}


def test_engine_imports_only_schemas_from_pokersim() -> None:
    for path in _modules("engine"):
        bad = _pokersim_targets(path) - {"schemas", "engine"}
        assert not bad, f"{path.name} imports {bad}"


def test_only_rules_imports_pokerkit() -> None:
    for path in sorted(SRC.rglob("*.py")):
        uses = any(m == "pokerkit" or m.startswith("pokerkit.") for m in _imports(path))
        assert not uses or path.relative_to(SRC) == Path("engine/rules.py"), path.name


def test_engine_has_no_io_or_web_imports() -> None:
    forbidden = {"fastapi", "sqlalchemy", "sqlite3", "requests", "httpx", "uvicorn", "socket"}
    for path in _modules("engine"):
        bad = {m.split(".")[0] for m in _imports(path)} & forbidden
        assert not bad, f"{path.name} imports {bad}"


def test_schemas_and_storage_do_not_import_the_engine_or_api() -> None:
    for path in _modules("schemas"):
        assert not (_pokersim_targets(path) - {"schemas"}), path.name
    for path in _modules("storage"):
        assert not (_pokersim_targets(path) - {"schemas", "storage"}), path.name


def test_engine_uses_no_global_random_calls() -> None:
    """random.Random(seed) is fine. random.random(), random.choice() and friends are not."""
    for path in _modules("engine"):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "random"
                and node.attr not in {"Random"}
            ):
                raise AssertionError(f"{path.name}:{node.lineno} calls random.{node.attr}")
