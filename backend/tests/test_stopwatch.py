import logging

from backend import stopwatch


def test_a_slow_piece_of_work_is_logged_as_a_warning_with_its_steps(
    monkeypatch, caplog
):
    monkeypatch.setattr(stopwatch, "SLOW_MS", 0)
    watch = stopwatch.Stopwatch("a decision")
    watch.lap("first step")
    watch.lap("second step")

    with caplog.at_level(logging.INFO, logger="undercover.timing"):
        watch.log()

    [record] = caplog.records
    assert record.levelno == logging.WARNING
    assert "a decision took" in record.getMessage()
    assert "first step" in record.getMessage()
    assert "second step" in record.getMessage()


def test_a_quick_piece_of_work_is_logged_at_info_only(caplog):
    watch = stopwatch.Stopwatch("a decision")
    watch.lap("only step")

    with caplog.at_level(logging.INFO, logger="undercover.timing"):
        watch.log()

    [record] = caplog.records
    assert record.levelno == logging.INFO
