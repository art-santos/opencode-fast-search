from src.ast_engine.capsule import build_capsule


def test_build_capsule_extracts_symbols():
    sample_file = "/home/dev-env/zipfy-monorepo-transposed/packages/primitives-v2/primitive-catalog/src/domain/deciders/DefineItemDecider.ts"
    capsule = build_capsule(target_path=sample_file, query="DefineItemDecider")
    assert "@ref" in capsule
    assert "DefineItemDecider" in capsule
    # Capsule must remain compact (< 1500 tokens / roughly 6000 chars)
    assert len(capsule) < 6000
