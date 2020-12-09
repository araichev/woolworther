import tempfile


import pytest
import requests
import responses
import pandas as pd

from .context import countdowner, DATA_DIR, BODY
from countdowner import *

def test_convert_google_sheet_url():
    url = "https://docs.google.com/spreadsheets/d/DOCID/edit?usp=sharing"
    expect = "https://docs.google.com/spreadsheets/d/DOCID/export?format=csv"
    assert convert_google_sheet_url(url) == expect

def test_read_watchlist():
    w = read_watchlist(DATA_DIR / "watchlist.csv")
    assert isinstance(w, dict)
    expect_keys = {"email_addresses", "products"}
    assert set(w.keys()) == expect_keys
    assert isinstance(w["products"], pd.DataFrame)

    with pytest.raises(ValueError):
        read_watchlist(DATA_DIR / "bad_watchlist.csv")

@responses.activate
def test_get_product():
    # Create mock GET response
    responses.add(
        responses.GET,
        "https://shop.countdown.co.nz/api/v1/products/hello",
        status=200,
        body=BODY,
        content_type="application/json",
    )

    r = get_product("hello")
    assert isinstance(r, requests.models.Response)


def test_parse_product():
    r = requests.models.Response()
    setattr(r, "url", "https://shop.countdown.co.nz/api/v1/products/1")
    p = parse_product(r)
    assert isinstance(p, dict)
    keys = [
        "stock_code",
        "name",
        "description",
        "size",
        "unit_price_($)",
        "unit_size",
        "sale_price_($)",
        "normal_price_($)",
        "discount_(%)",
        "datetime",
    ]
    assert set(p.keys()) == set(keys)
    assert p["stock_code"] == "1"


@responses.activate
def test_collect_products():
    # Create mock GET response
    responses.add(
        responses.GET,
        re.compile("https://shop.countdown.co.nz/api/v1/products/(\\w)+"),
        match_querystring=False,
        status=200,
        body=BODY,
        content_type="application/json",
    )

    f = collect_products(["1", "260803"])
    assert isinstance(f, pd.DataFrame)
    assert f.shape == (2, 10)

    f = collect_products([])
    assert isinstance(f, pd.DataFrame)
    assert f.empty


def test_filter_sales():
    f = pd.DataFrame(
        [["a", 2, 3, 20.1]],
        columns=["name", "sale_price_($)", "normal_price_($)", "discount_(%)"],
    )
    g = filter_sales(f)
    assert isinstance(g, pd.DataFrame)
    assert g.to_dict() == f.to_dict()

    f = pd.DataFrame(
        [["a", 2, 3, 0]],
        columns=["name", "sale_price_($)", "normal_price_($)", "discount_(%)"],
    )
    g = filter_sales(f)
    assert isinstance(g, pd.DataFrame)
    assert g.empty

    f = pd.DataFrame()
    g = filter_sales(f)
    assert isinstance(g, pd.DataFrame)
    assert g.empty


@responses.activate
def test_run_pipeline():
    # Create mock GET response
    responses.add(
        responses.GET,
        re.compile("https://shop.countdown.co.nz/api/v1/products/(\\w)+"),
        match_querystring=False,
        status=200,
        body=BODY,
        content_type="application/json",
    )

    w_path = DATA_DIR / "watchlist.csv"
    # Test without writing to file
    f = run_pipeline(w_path, sales_only=False)
    # Should be a DataFrame
    assert isinstance(f, pd.DataFrame)
    # File should contain all the products in the watchlist
    w = read_watchlist(w_path)
    assert set(w["products"].stock_code) == set(f.stock_code)

    # Test with writing to file
    with tempfile.NamedTemporaryFile() as tmp:
        run_pipeline(w_path, out_path=tmp.name, sales_only=False)
        # File should be a CSV
        f = pd.read_csv(tmp, dtype={"stock_code": str})
        assert isinstance(f, pd.DataFrame)
        # File should contain all the products in the watchlist
        w = read_watchlist(w_path)
        print(f)
        assert set(w["products"].stock_code) == set(f.stock_code)
