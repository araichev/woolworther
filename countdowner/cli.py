import click

import countdowner.main as m


@click.command(short_help="Get the current prices of your watchlist products")
@click.option("-o", "--out_path", default=None, help="Path to write CSV output")
@click.option("-gu", "--gmail_username", default=None, help="GMail username")
@click.option("-gp", "--gmail_password", default=None, help="GMail password")
@click.option(
    "-t",
    "--as_plaintext",
    is_flag=False,
    default=False,
    help="Send the optional email in plaintext if true;"
    "otherwise send it as HTML; defaults to False",
)
@click.option(
    "-s",
    "--filter_sales",
    is_flag=True,
    default=False,
    help="Keep only the products on sale; defaults to False",
)
@click.argument("watchlist_path")
def countdownit(
    watchlist_path,
    out_path,
    gmail_username,
    gmail_password,
    *,
    as_plaintext,
    filter_sales,
):
    """
    Read a YAML watchlist located at WATCHLIST_PATH,
    collect all the product information from Countdown,
    keep only the sales data if DO_FILTER_SALES.
    Print the resulting product information to stdout as a CSV string.
    If OUT_PATH is given, then instead write the CSV to a file
    located at OUT_PATH.

    If MAILGUN_DOMAIN (Mailgun domain) and MAILGUN_KEY (Mailgun API key)
    are given, then additionally email the product table
    to the email address listed in the watchlist.
    """
    f = m.run_pipeline(
        watchlist_path,
        out_path=out_path,
        gmail_username=gmail_username,
        gmail_password=gmail_password,
        as_plaintext=as_plaintext,
        filter_sales=filter_sales,
    )

    if out_path is None:
        print(f.to_csv(index=False))
