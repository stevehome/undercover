from agent import __main__ as cli


def test_main_works_the_named_claim(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "decide_claim", calls.append)
    monkeypatch.setattr("sys.argv", ["cli.py", "CLM-1001"])

    cli.main()

    assert calls == ["CLM-1001"]
