from pathlib import Path

from src.ast_engine.capsule import build_capsule

SAMPLE = Path(__file__).parent / "fixtures" / "sample.ts"


def test_build_capsule_extracts_symbols():
    capsule = build_capsule(target_path=str(SAMPLE), query="CatalogSearcher")
    assert "@ref" in capsule
    assert "CatalogSearcher" in capsule
    # Capsule must remain compact (< 1500 tokens / roughly 6000 chars)
    assert len(capsule) < 6000


def test_build_capsule_lists_all_symbol_kinds():
    capsule = build_capsule(target_path=str(SAMPLE), query="SearchTarget")
    for kind in ("class", "interface", "type", "function", "const", "enum"):
        assert kind in capsule
