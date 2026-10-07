import pytest
from src.jev_server.app import evaluate_systemone


def test_systemone_noul_decision():
    req = {
        "state": "The user wants to find where catalog deciders live.",
        "model": "jev-latest",
        "questions": {
            "relevance": {
                "type": "noul",
                "instructions": "Is this relevant to catalog items?",
            }
        },
    }
    res = evaluate_systemone(req)
    assert "answers" in res
    assert "relevance" in res["answers"]
    ans = res["answers"]["relevance"]
    assert "probability" in ans or "confidence" in ans
