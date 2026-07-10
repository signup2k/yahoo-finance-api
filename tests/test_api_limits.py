from unittest.mock import patch

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.index import _enforce_symbol_limit, app, history


def _symbols(count: int) -> str:
    return ",".join(f"SYM{index}" for index in range(count))


def test_symbol_limit_accepts_200_symbols() -> None:
    _enforce_symbol_limit(_symbols(200).split(","))


def test_symbol_limit_rejects_201_symbols() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _enforce_symbol_limit(_symbols(201).split(","))

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == "Request contains 201 symbols; maximum is 200"


def test_history_accepts_more_than_20_symbols_for_short_window() -> None:
    with patch("api.index.yf.download", return_value=pd.DataFrame()):
        result = history(
            symbols=_symbols(21),
            start="2026-07-08",
            end="2026-07-09",
            interval="1d",
            max_points=None,
        )

    assert result["count"] == 21


def test_history_rejects_201_symbols_before_download() -> None:
    with (
        patch("api.index.yf.download") as download,
        pytest.raises(HTTPException) as exc_info,
    ):
        history(
            symbols=_symbols(201),
            start="2026-07-08",
            end="2026-07-09",
            interval="1d",
            max_points=None,
        )

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == "Request contains 201 symbols; maximum is 200"
    download.assert_not_called()


def test_max_points_must_be_positive() -> None:
    client = TestClient(app)

    response = client.get("/api/history", params={"symbols": "AAPL", "max_points": 0})

    assert response.status_code == 422


def test_history_enforces_default_data_point_budget() -> None:
    with pytest.raises(HTTPException) as exc_info:
        history(
            symbols=_symbols(55),
            start="2025-07-10",
            end="2026-07-10",
            interval="1d",
            max_points=None,
        )

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == (
        "History request would require 20075 rows; maximum is 20000"
    )
