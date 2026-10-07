from src.mcp_server import handle_request


def test_tools_list():
    res = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    assert res["id"] == 1
    names = [t["name"] for t in res["result"]["tools"]]
    assert "jit_capsule" in names
    assert "jev_decide" in names


def test_call_jit_capsule():
    res = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "jit_capsule",
                "arguments": {
                    "query": "DefineItem",
                    "target_path": "/home/dev-env/zipfy-monorepo-transposed/packages/primitives-v2/primitive-catalog/src/domain/deciders/DefineItemDecider.ts",
                },
            },
        }
    )
    text = res["result"]["content"][0]["text"]
    assert "@ref" in text


def test_call_jev_decide_fail_open():
    # No network needed: must fall back to local scorer when server is down
    import os

    os.environ["JEV_BASE_URL"] = "http://127.0.0.1:9"
    res = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "jev_decide",
                "arguments": {"prompt": "catalog items", "choices": ["catalog", "billing"]},
            },
        }
    )
    text = res["result"]["content"][0]["text"]
    assert "catalog" in text.lower() or "billing" in text.lower()
