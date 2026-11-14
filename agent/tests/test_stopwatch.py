import logging

from agent import stopwatch


def test_a_slow_decision_is_logged_as_a_warning_with_its_steps(monkeypatch, caplog):
    monkeypatch.setattr(stopwatch, "SLOW_MS", 0)
    watch = stopwatch.Stopwatch("a decision")
    watch.lap("the backend's answer")

    with caplog.at_level(logging.INFO, logger="undercover.timing"):
        watch.log()

    [record] = caplog.records
    assert record.levelno == logging.WARNING
    assert "the backend's answer" in record.getMessage()
