from typing import List, Dict, Optional
import datetime as dt
from collections import OrderedDict
import pathlib as pl
import os
import json
import io
import re

import yaml
import requests
from bs4 import BeautifulSoup
import pandas as pd
import yagmail


ROOT = pl.Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WATCHLIST_FIELDS = [
    "name",
    "email_addresses",
    "products",
]
EMAIL_PATTERN = re.compile(r"[^@]+@[^@]+\.[^@]+")
PRICE_PATTERN = re.compile(r"\d+\.\d\d")


# ---------------------
# Watchlist functions
# ---------------------
def parse_df(csv_text: str, **kwargs) -> pd.DataFrame:
    """
    Given a CSV text with a header, convert it to a DataFrame and
    return the result.
    """
    csv = io.StringIO(csv_text)
    return pd.read_table(csv, sep=",", **kwargs)


def parse_watchlist(watchlist_yaml: pl.PosixPath) -> Dict:
    """
    Given a (decoded) YAML dictionary representing a product watchlist
    convert the CSV text fields to DataFrame and return the resulting
    dictionary.
    If keys are missing from the dictionary, add them and set their values
    to ``None`` to aid format checking in :func:`check_watchlist`.
    """
    w = {}

    # Set all missing keys to None
    for key in WATCHLIST_FIELDS:
        if key in watchlist_yaml:
            w[key] = watchlist_yaml[key]
        else:
            w[key] = None

    if w["products"] is not None:
        w["products"] = parse_df(w["products"], dtype={"stock_code": str})

    return w


def valid_email(x: str):
    """
    Return ``True`` if ``x`` is a valid email address;
    otherwise return ``False``.
    """
    if isinstance(x, str) and re.match(EMAIL_PATTERN, x):
        return True
    else:
        return False


def check_watchlist(watchlist: Dict):
    """
    Raise an error if the given watchlist (dictionary) is invalid.
    """
    w = watchlist
    if not isinstance(w["name"], str) or not len(w["name"]):
        raise ValueError("Name must be a nonempty string")

    for e in w["email_addresses"]:
        if not valid_email(e):
            raise ValueError("Invalid email address", e)

    p = w["products"]
    if p is None:
        raise ValueError("Products must be given")
    if not set(["description", "stock_code"]) <= set(p.columns):
        raise ValueError('Products must have "description" and "stock_code" fields')


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
    # Read
    path = pl.Path(path)
    with path.open("r") as src:
        watchlist_yaml = yaml.safe_load(src)

    # Parse
    watchlist = parse_watchlist(watchlist_yaml)

    # Check
    check_watchlist(watchlist)

    # Create
    return watchlist


# -------------------------
# Countdown API functions
# -------------------------
def get_product(stock_code: str):
    """
    Issue a GET request to Countdown at
    https://shop.countdown.co.nz/Shop/ProductDetails
    with the given stock code (string), and return the response.
    """
    url = "https://shop.countdown.co.nz/Shop/ProductDetails"
    return requests.get(url, params={"stockcode": stock_code})


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
    - ``'sale_price'``
    - ``'price'``
    - ``'discount_percentage'``
    - ``'unit_price'``
    - ``'datetime'``: current datetime as a ``'%Y-%m-%dT%H:%M:%S'``
      string

    Use ``None`` values when the information is not found in the response.
    """
    keys = [
        "stock_code",
        "name",
        "description",
        "size",
        "sale_price",
        "price",
        "discount_percentage",
        "unit_price",
        "datetime",
    ]
    d = OrderedDict([(key, None) for key in keys])

    # Get stock code from URL and set datetime
    d["stock_code"] = re.search(r"stockcode=(\w+)", response.url).group(1)
    d["datetime"] = dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Handle bad product data
    if response.status_code != 200:
        return d

    soup = BeautifulSoup(response.text, "lxml")

    if not soup.find("input", attrs={"name": "stockcode"}):
        return d

    # Handle good product data
    d["name"] = soup.find("div", class_="product-title").h1.text.strip()
    d["description"] = (
        soup.find("p", class_="product-description-text").text.strip() or None
    )
    d["size"] = soup.find("span", class_="volume-size").text.strip() or None

    s1 = soup.find("span", class_="special-price")
    s2 = soup.find("span", class_="club-price-wrapper")
    s3 = soup.find("span", class_="price")
    if s1:
        d["sale_price"] = price_to_float(list(s1.stripped_strings)[0])
        t = soup.find("span", class_="was-price")
        d["price"] = price_to_float(list(t.stripped_strings)[0].replace("was", ""))
    elif s2:
        d["sale_price"] = price_to_float(list(s2.stripped_strings)[0])
        t = soup.find("span", class_="non-club-price")
        d["price"] = price_to_float(
            list(t.stripped_strings)[0].replace("non club price", "")
        )
    elif s3:
        d["price"] = price_to_float(list(s3.stripped_strings)[0])

    if d["sale_price"] is not None:
        d["discount_percentage"] = round(100 * (1 - d["sale_price"] / d["price"]), 1)
    else:
        d["discount_percentage"] = None

    d["unit_price"] = soup.find("div", class_="cup-price").string.strip() or None

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
            results = pd.DataFrame(results).sort_values(
                "discount_percentage", ascending=False
            )
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
        result = products
    else:
        cols = ["name", "sale_price", "price", "discount_percentage"]
        result = products.loc[products["sale_price"].notna(), cols]

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
