from typing import List, Dict, Optional
import datetime as dt
import pathlib as pl
import os
import io
import re

import yaml
import requests
import titlecase as tc
import pandas as pd
import yagmail


ROOT = pl.Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WATCHLIST_FIELDS = [
    "email_address",
    "product_description",
    "stock_code",
]
EMAIL_PATTERN = re.compile(r"[^@]+@[^@]+\.[^@]+")
PRICE_PATTERN = re.compile(r"\d+\.\d\d")


# ---------------------
# Watchlist functions
# ---------------------
def valid_email(x: str):
    """
    Return ``True`` if ``x`` is a valid email address;
    otherwise return ``False``.
    """
    if isinstance(x, str) and re.match(EMAIL_PATTERN, x):
        return True
    else:
        return False


def check_watchlist(watchlist: pd.DataFrame) -> pd.DataFrame:
    """
    Raise an error if the given watchlist (dictionary) is invalid.
    """
    w = watchlist
    if not set(WATCHLIST_FIELDS) <= set(w.columns):
        raise ValueError(f"Watchlist must contain the columns {WATCHLIST_FIELDS}")

    for col in WATCHLIST_FIELDS:
        if not w[col].dropna().nunique():
            raise ValueError(f"Must include at least one value for {col}")
    
    f = w.filter(["product_description", "stock_code"]).dropna(how="all")
    for col in f.columns:
        if f[col].isna().sum():
            raise ValueError(f"Column {col} must contain blanks")
    
    return watchlist

def convert_google_sheet_url(url: str) -> str:
    """
    Given a Google Sheets URL, convert it to a CSV download URL.
    """
    return "/".join(url.split("/")[:-1]) + "/export?format=csv"

def read_watchlist(path: pl.PosixPath) -> Dict:
    """
    Read a YAML file of watchlist data at the given path,
    parse the file, check it, and return the resulting watchlist
    dictionary.
    The YAML file should have the following form::

        - name: Hello
        - email_addresses: [a@b.com, c@d.net]
        - products: |
            description,stock_code
            chips sis,267945
            bagels bro,285453

    """
    # If given a Google Sheet path, convert it to a CSV download path
    if str(path).startswith("https://docs.google.com/spreadsheets/d/"):
        path = convert_google_sheet_url(str(path))

    # Read and check watchlist
    w = (
        pd.read_csv(path, dtype={"stock_code": str})
        .pipe(check_watchlist)
    )

    # Dictify
    return {
        "email_addresses": w.email_address.dropna().unique().tolist(),
        "products": w.filter(["product_description", "stock_code"]).dropna(),
    }

# -------------------------
# Countdown API functions
# -------------------------
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


# -------------------------
# Data pipeline functions
# -------------------------
def filter_sales(products: pd.DataFrame) -> pd.DataFrame:
    """
    Given a DataFrame of products of the form returned by
    :func:`collect_products`, keep only the items on sale and the
    columns ``['name', 'sale_price', 'price', 'discount']``.
    """
    if products.empty:
        result = products.copy()
    else:
        cols = ["name", "sale_price_($)", "normal_price_($)", "discount_(%)"]
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
):
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
    out_path: Optional[pl.PosixPath] = None,
    gmail_username: Optional[str] = None,
    gmail_password: Optional[str] = None,
    *,
    as_plaintext: bool = False,
    sales_only: bool = False,
):
    """
    Read a YAML watchlist located at ``watchlist_path``, one that :func:`read_watchlist` can read,
    collect all the product information from Countdown, and keep only the items on sale
    if ``sales_only``.

    Return the resulting DataFrame.
    If an output path is given, then instead write the result to a CSV at that path.

    If a GMail username and password are given, then additionally send an email
    from that email address to the recipients mentioned in the watchlist
    and with the product information.
    Use the function :func:`email` for this.
    """
    # Read products
    watchlist_path = pl.Path(watchlist_path)
    w = read_watchlist(watchlist_path)

    # Collect updates
    codes = w["products"]["stock_code"]
    f = collect_products(codes)

    if sales_only:
        f = filter_sales(f)
        subject = f"{f.shape[0]} sales on your Countdown watchlist"
    else:
        subject = f"{f.shape[0]} items on your Countdown watchlist"

    # Filter sale items and email
    if gmail_username is not None and gmail_password is not None:
        email(
            f,
            recipients=w["email_addresses"],
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
