Countdowner
************
.. image:: https://travis-ci.org/araichev/countdowner.svg?branch=master
    :target: https://travis-ci.org/araichev/countdowner

A Python 3.7+ library to check for sales at Countdown grocery stores throughout New Zealand.
Also has a command-line interface.


Installation
=============
``poetry add git+https://github.com/araichev/countdowner.git``


Usage
======
Here is a common workflow.

#. Get the stock codes of the products you want to watch by searching `the Countdown site <https://shop.countdown.co.nz/>`_.  The stock code of a product is listed in the URL of its details page. For example, the stock code for the product at ``https://shop.countdown.co.nz/Shop/ProductDetails?stockcode=214684&name=colgate-360-toothbrush-medium-whole-mouth-clean`` is ``214684``.

#. Put your stock codes in a CSV file with at least the column ``stock_code``. Other columns are OK and will be ignored, e.g.::

    product_description,stock_code
    Brazil nuts,291156
    GB chocolate,32467
    cheese,281739

#. Use the ``countdowner`` library functions as in the Jupyter notebook at ``notebooks/examples.ipynb`` to get price information for your products and optionally email the results.  For emailing you will need a GMail account.


Authors
========
- Alex Raichev (2017-05)


Notes
======
- Development status is Alpha
- This project uses semantic versioning


Changes
========

4.0.0, 2020-12-??
-----------------
- Switched from YAML watchlists to CSV watchlists.
- Removed the CLI, because i didn't find it useful.


3.1.0, 2020-06-19
-----------------
- Handled new Countdown API.


3.0.0, 2020-06-18
-----------------
- Breaking change: Switched to using Yagmail instead of Mailgun.


2.0.0, 2020-06-11
-----------------
- Breaking change: Removed async feature for the time being, because the latest ``requests`` and ``grequests`` were conflicting.


1.0.1, 2020-06-11
-----------------
- Bugfixed a null edge cases in ``collect_products()`` and ``filter_sales()``.


1.0.0, 2020-06-11
-----------------
- Switched to Poetry
- Upgraded to Python 3.8
- Breaking change: changed ``async`` keyword to ``use_async``.


0.4.0, 2017-12-06
-------------------
- Updated ``parse_product`` to handle Countdown's new HTML output and rounded discount percentages to one decimal place
- Added ``do_filter_sales`` flag to ``run_pipeline``
- Changed ``countdownit`` to print to screen if no output path given


0.3.1, 2017-11-10
-------------------
- Adapted ``parse_product`` function to Countdown's new HTML output


0.3.0, 2017-10-06
-------------------
- Changed ``run_pipeline`` API


0.2.0, 2017-06-18
-------------------
- Allowed for multiple email addresses in watchlist
- In tests, replaced actual HTTP requests with mock ones


0.1.0, 2017-06-04
-------------------
- Replaced ``curio`` and ``curio-http`` with ``grequests`` for asynchronous requests. The latter is slower but easier to use.
- Handled invalid stock codes
- Added some automated tests


0.0.1, 2017-05-30
------------------
- First draft