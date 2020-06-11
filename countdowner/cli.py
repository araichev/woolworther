import click

import countdowner.main as m


@click.command(short_help='Get the current prices of your watchlist products')
@click.option('-o', '--out_path', default=None,
  help='Path to write CSV output')
@click.option('-d', '--mailgun_domain', default=None,
  help='Mailgun domain key')
@click.option('-k', '--mailgun_key', default=None,
  help='Mailgun API key')
@click.option('-h', '--as_html', is_flag=True, default=True,
  help='Send the optional email as HTML if true;'
  'otherwise send it as text; defaults to True')
@click.option('-a', '--use_async', is_flag=True, default=True,
  help='Collect the product prices asynchronously; defaults to True')
@click.option('-s', '--do_filter_sales', is_flag=True, default=False,
  help='Keep only the products on sale; defaults to False')
@click.argument('watchlist_path')
def countdownit(watchlist_path, out_path, mailgun_domain,
  mailgun_key, as_html, use_async, do_filter_sales):
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
    f = m.run_pipeline(watchlist_path, out_path=out_path,
      mailgun_domain=mailgun_domain, mailgun_key=mailgun_key,
      as_html=as_html, use_async=use_async, do_filter_sales=do_filter_sales)

    if out_path is None:
        print(f.to_csv(index=False))
