from typing import List, Dict, Optional
import datetime as dt
import pathlib as pl
import os
import re

import requests
import titlecase as tc
import pandas as pd
import yagmail


BASE_DIR = pl.Path(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = BASE_DIR / "data"
PRICE_PATTERN = re.compile(r"\d+\.\d\d")


def convert_google_sheet_url(url: str) -> str:
    """
    Given a Google Sheets URL, convert it to a CSV download URL.
    """
    return "/".join(url.split("/")[:-1]) + "/export?format=csv"


def check_watchlist(watchlist: pd.DataFrame) -> pd.DataFrame:
    """
    Raise an error if the given watchlist (dictionary) is invalid.
    """
    if not "stock_code" in watchlist.columns:
        raise ValueError(f"Watchlist must contain the column stock_code")

    if not watchlist.stock_code.dropna().nunique():
        raise ValueError(f"Column stock_code must contain at least one value")

    return watchlist


def read_watchlist(path_or_url: str) -> List[str]:
    """
    Read the watchlist CSV at the given path, check it, and
    return its list of stock codes.
    The CSV file should have at least the column

    - ``'stock_code'``: the stock code of a product

    More columns are OK and will be ignored.
    """
    # If given a Google Sheet path, convert it to a CSV download path
    if (p := str(path_or_url)).startswith("https://docs.google.com/spreadsheets/d/"):
        path_or_url = convert_google_sheet_url(p)

    # Read and check watchlist
    w = pd.read_csv(path_or_url, dtype={"stock_code": str}).pipe(check_watchlist)

    return w.stock_code.to_list()


def get_product(stock_code: str):
    """
    Issue a GET request to Countdown at
    https://shop.countdown.co.nz/Shop/ProductDetails
    with the given stock code (string), and return the response.
    """
    url = f"https://shop.countdown.co.nz/api/v1/products/{stock_code}"
    headers = {
        "x-requested-with": "OnlineShopping.WebApp",
    }
    return requests.get(url, headers=headers)


def price_to_float(price_string: str) -> float:
    """
    Convert a price string to a float.
    """
    return float(re.search(PRICE_PATTERN, price_string).group(0))


def parse_product(response) -> Dict:
    """
    Given a response of the form output by :func:`get_product` or
    :func:`get_product_a`, parse it, and return the a dictionary
    with the following keys and their corresponding values.

    - ``'stock_code'``
    - ``'name'``
    - ``'description'``
    - ``'size'``
    - ``'unit_price_($)'``
    - ``'unit_size_($)'``
    - ``'sale_price_($)'``
    - ``'normal_price_($)'``
    - ``'discount_(%)'``
    - ``'datetime'``: current datetime as a ``'%Y-%m-%dT%H:%M:%S'`` string

    Use ``None`` values when the information is not found in the response.
    """
    # Initialize result
    d = {
        "stock_code": re.search(r"products/(\w+)", response.url).group(1),
        "name": None,
        "description": None,
        "size": None,
        "unit_price_($)": None,
        "unit_size": None,
        "sale_price_($)": None,
        "normal_price_($)": None,
        "discount_(%)": None,
        "datetime": dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }

    # Handle bad product data
    if response.status_code != 200:
        return d

    r = response.json()
    d["name"] = tc.titlecase(r["name"])
    d["description"] = r["description"]
    d["size"] = r["size"]["volumeSize"]
    d["unit_price_($)"] = r["size"]["cupPrice"]
    d["unit_size"] = r["size"]["cupMeasure"]
    d["sale_price_($)"] = r["price"]["salePrice"]
    d["normal_price_($)"] = r["price"]["originalPrice"]
    if d["normal_price_($)"] != 0:
        d["discount_(%)"] = round(
            100 * (1 - d["sale_price_($)"] / d["normal_price_($)"]), 1
        )
    else:
        d["discount_(%)"] = 0

    return d


def collect_products(stock_codes: List[str], *, as_df: bool = True):
    """
    For each item in the given list of stock codes,
    call :func:`get_product`, parse the responses,
    and return the results as a list of dictionaries.
    If ``as_df``, then return the result as a DataFrame
    with columns equal to the keys listed in :func:`parse_product`.
    """
    results = []
    responses = (get_product(code) for code in stock_codes)
    for response in responses:
        info = parse_product(response)
        results.append(info)

    if as_df:
        if results:
            results = pd.DataFrame(results).sort_values("discount_(%)", ascending=False)
            results["datetime"] = pd.to_datetime(results["datetime"])
        else:
            results = pd.DataFrame()

    return results


def filter_sales(products: pd.DataFrame) -> pd.DataFrame:
    """
    Given a DataFrame of products of the form returned by
    :func:`collect_products`, keep only the items on sale and the
    columns ``['name', 'sale_price', 'price', 'discount']``.
    """
    if products.empty:
        result = products.copy()
    else:
        cols = ["name", "size", "sale_price_($)", "normal_price_($)", "discount_(%)"]
        result = (
            products.loc[lambda x: x["discount_(%)"] > 0]
            .filter(cols)
            .reset_index(drop=True)
        )

    return result


def email(
    products: pd.DataFrame,
    recipients: List[str],
    subject: str,
    gmail_username: str,
    gmail_password: str,
    *,
    as_plaintext: bool = False,
) -> None:
    """
    Email the given product DataFrame to the given recipient email addresses
    using GMail with the given username and password.
    Use the given subject in the email.
    If ``as_plaintext``, then write the email body as plaintext;
    otherwise, write it as HTML.
    """
    to = recipients
    subject = subject
    if as_plaintext:
        contents = products.to_string(index=False, float_format="%.2f")
    else:
        contents = products.to_html(index=False, float_format="%.2f")

    with yagmail.SMTP(gmail_username, gmail_password) as yag:
        yag.send(
            to=to, subject=subject, contents=contents,
        )


def run_pipeline(
    watchlist_path: pl.PosixPath,
    recipients: List[str] = None,
    out_path: Optional[pl.PosixPath] = None,
    gmail_username: Optional[str] = None,
    gmail_password: Optional[str] = None,
    *,
    as_plaintext: bool = False,
    sales_only: bool = False,
):
    """
    Read a CSV watchlist located at ``watchlist_path``, one that :func:`read_watchlist` can read,
    collect all the product information from Countdown, and keep only the items on sale
    if ``sales_only``.
    Return the resulting DataFrame.

    If an output path is given, then instead write the result to a CSV at that path.

    If a list of recipient email addresses is given, along with a
    GMail username and password, then additionally email the product information
    from that GMail email address to the recipients.
    Use the function :func:`email` for this.
    """
    stock_codes = read_watchlist(watchlist_path)
    f = collect_products(stock_codes)

    if sales_only:
        f = filter_sales(f)
        subject = f"{f.shape[0]} sales on your Countdown watchlist"
    else:
        subject = f"{f.shape[0]} items on your Countdown watchlist"

    # Filter sale items and email
    if recipients and gmail_username is not None and gmail_password is not None:
        email(
            f,
            recipients=recipients,
            subject=subject,
            gmail_username=gmail_username,
            gmail_password=gmail_password,
            as_plaintext=as_plaintext,
        )

    # Output product updates
    if out_path is None:
        return f
    else:
        out_path = pl.Path(out_path)
        if not out_path.parent.exists():
            out_path.parent.mkdir(parents=True)

        f.to_csv(str(out_path), index=False)
