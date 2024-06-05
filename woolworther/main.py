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
API_URL = "https://www.woolworths.co.nz/api/v1/products/"


def convert_google_sheet_url(url: str) -> str:
    """
    Given a Google Sheets URL, convert it to a CSV download URL.
    """
    return "/".join(url.split("/")[:-1]) + "/export?format=csv"


def check_watchlist(watchlist: pd.DataFrame) -> pd.DataFrame:
    """
    Raise an error if the given watchlist (dictionary) is invalid.
    """
    if "stock_code" not in watchlist.columns:
        raise ValueError("Watchlist must contain the column stock_code")

    if not watchlist.stock_code.dropna().nunique():
        raise ValueError("Column stock_code must contain at least one value")

    return watchlist


def read_watchlist(path_or_url: str) -> list[str]:
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
    Issue a GET request to Woolworths at ``API_URL``
    with the given stock code (string), and return the response.
    """
    url = API_URL + f"{stock_code}"
    headers = {
        "x-requested-with": "OnlineShopping.WebApp",
        "cookie": "ARRAffinity=c2dba6f1a343c8b908c4c09af49d7b98f09d8a609f95e791c930db34ec6d2ef1; ARRAffinitySameSite=c2dba6f1a343c8b908c4c09af49d7b98f09d8a609f95e791c930db34ec6d2ef1; AKA_A2=A; ak_bmsc=6249687A1A0D88DC39E27A1FCF09F6CD~000000000000000000000000000000~YAAQZqQFF+gs8FV8AQAAciUGkQ0XwzGMcjBgBM7TaKy0ECjCIMqyqRk+0MgEIt+sud6ZdiqF4rRUuuDtkKCbAgFrG/+i/8AuvurzvDnVyqMkbVyVZVj45yZUqMR1ek+3IahnLdalwmEBgZaI/i3Uc7DzxmI3Cyv2yVhkgakkTPQXWO2Q1YirT1cKaO8ERFEK5kUqTHmmSzVLK3GNKTcHFBK5WTuE6r0xVKi+Kc3eayFTtb+raBIuFHUZmCtwWnMII9x4dTOE2TaYl59JQ9D/2EytXM4D6hVcdIt9jWU7A/R/VF7hEO736UQ+mQJ9LmSl2EzQcxXOV+2Y0RTlzUjb/ds/Vq9qcLxxuNGnNjb92Ih2TnTS3LhTyHj+iq1M6Jozv8Ee+PFI6cGoFB70znEUOQ==; _gcl_au=1.1.112134549.1634520676; _ga=GA1.3.1902341848.1634520678; _gid=GA1.3.1907316599.1634520678; _fbp=fb.2.1634520679019.1202416094; gig_canary=false; gig_canary_ver=12471-3-27242010; _hjid=849c2aba-7c8b-44f5-88e7-81f4f63a557a; _hjFirstSeen=1; outbrain_cid_fetch=true; _hjIncludedInSessionSample=0; _hjAbsoluteSessionInProgress=0; agaCORS=766707b394872b181f1414b0000342ea; aga=766707b394872b181f1414b0000342ea; dtid=2:8PQgEn7rwBP9KBt6jqV3RqgMO5nR5MA15ih3MW8L7BJ6iBe73d6WFE5Q5tCDQ6SN77qc0cO1QXqawGcl9fwIf8+wnG+qEplLBowccBz1O+3p3F4nXXPiVS7zVBwD1GbuK9c=; ASP.NET_SessionId=t0cnvomcyljorg0xur11tuoz; cw-laie=baf3132a459143b0b09a84a3b88e5859; XSRF-TOKEN=PiSuM33VjBmPNGj3TtpbSWa9IRFOVWy0LfSQe4atJKaEzenrRHo8k9EnClmtBlAnpJpztgxFaiWl0S8buHIMTL88uzu7pcZXjo5iF3ibc5s1:kEIOuz0q9VRMllaciZtE4_2Py-67q_WOV9P_qNuC5dLR72bOrvUEXg-pkZbEPf-sicW1nUf5b1FC18glevupCdKOlF2mkt4dBWKnA6EHQco1; ai_user=/goLDT9kthzL/oVgfQa1ya|2021-10-18T01:31:22.610Z; cw-arjshtsw=i22a38c0036d94ef097af372570c18695iqlhdvozg; gig_bootstrap_3_PWTq_MK-V930M4hDLpcL_qqUx224X_zPBEZ8yJeX45RHI-uKWYQC5QadqeRIfQKB=login_ver4; mdLogger=false; kampyle_userid=d0f3-1e04-63a4-8e62-3665-80d7-6fa3-bc20; kampyleUserSession=1634520693032; kampyleUserSessionsCount=1; kampyleSessionPageCounter=1; bm_mi=B59FEB20F705FC84AFCA08AB5CB915EB~lQoAYQbp4aPCsNFC7R9wjtRaa4U2Iyit6GlMkelZ6jIRWzCpVYleiRSSMnUKjphxOKFK5EwfhvTkqDeoNE9/ghGUX9zTiB7BuXaHJYJx1BgbOOgIw3x7T6FJOm96MjuoF5wn0EUKNl+SttGeYFcfhZUR3rlUZVUU8lCB/slrwfN/xIfQc6+ZkUYTZMWVIy28Y8h24dzclRgWrkQ4r7XkmwEHcPlVgtvM9vLguqb6vkjGrdUI9B7Fb6hdFVYmO1fb; akavpau_vpshop=1634521115~id=4669dc13e8a206c282a1d5c181ba10f1; bm_sv=0AAF0A61285DF089DF7A0FB7943D147C~LCcXFtEspgPOBwZfGH4grrwekajjeqH3OCvW6FQMeDi04BLm5B4NJ+r3B8+GaonNpE2HPCuokEe/2XloccFg+yrZhJ33vYmRnUTNKI4iI+Kjm95q2yfW14kSgzjj/ic3ZJOwn4Bx3DJjQmWAmLoBT+OeQtDdkzpEzBiUuMT8Ykc=; ai_sessioncw-=xAuBqb2T634RKsNxUQJLmh|1634520683304|1634520815688; _dc_gtm_UA-10765339-1=1",
        "expires": "-1",
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 12_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Mobile/15E148 Safari/604.1",
    }
    return requests.get(url, headers=headers)


def price_to_float(price_string: str) -> float:
    """
    Convert a price string to a float.
    """
    return float(re.search(PRICE_PATTERN, price_string).group(0))


def parse_product(response) -> dict:
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
    d["description"] = (
        r["description"].replace("<p>", "").replace("</p>", "")
        if r["description"] is not None
        else None
    )
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


def collect_products(stock_codes: list[str], *, as_df: bool = True):
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
        cols = [
            "name",
            "stock_code",
            "size",
            "sale_price_($)",
            "normal_price_($)",
            "discount_(%)",
        ]
        result = (
            products.loc[lambda x: x["discount_(%)"] > 0]
            .filter(cols)
            .reset_index(drop=True)
        )

    return result


def email(
    products: pd.DataFrame,
    recipients: list[str],
    subject: str,
    gmail_username: str,
    gmail_password: str,
    headers: dict | None = None,
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
    subject = subject
    if as_plaintext:
        contents = products.to_string(index=False, float_format="%.2f")
    else:
        contents = products.to_html(index=False, float_format="%.2f")

    with yagmail.SMTP(gmail_username, gmail_password) as yag:
        yag.send(
            to=recipients,
            subject=subject,
            contents=contents,
            headers=headers,
        )


def run_pipeline(
    watchlist_path: pl.PosixPath,
    recipients: list[str] = None,
    out_path: pl.PosixPath | None = None,
    gmail_username: str | None = None,
    gmail_password: str | None = None,
    headers: dict | None = None,
    *,
    as_plaintext: bool = False,
    sales_only: bool = False,
):
    """
    Read a CSV watchlist located at ``watchlist_path``, one that :func:`read_watchlist` can read,
    collect all the product information from Woolworths, and keep only the items on sale
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
        subject = f"{f.shape[0]} sales on your Woolworths watchlist"
    else:
        subject = f"{f.shape[0]} items on your Woolworths watchlist"

    # Filter sale items and email
    if recipients and gmail_username is not None and gmail_password is not None:
        email(
            f,
            recipients=recipients,
            subject=subject,
            gmail_username=gmail_username,
            gmail_password=gmail_password,
            as_plaintext=as_plaintext,
            headers=headers,
        )

    # Output product updates
    if out_path is None:
        return f
    else:
        out_path = pl.Path(out_path)
        if not out_path.parent.exists():
            out_path.parent.mkdir(parents=True)

        f.to_csv(str(out_path), index=False)
