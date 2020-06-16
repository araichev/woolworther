import tempfile

from click.testing import CliRunner
import responses

from .context import countdowner, DATA_DIR
from countdowner import *
from countdowner.cli import *


runner = CliRunner()


@responses.activate
def test_countdownit():
    # Create mock GET response
    responses.add(
        responses.GET,
        "https://shop.countdown.co.nz/Shop/ProductDetails",
        status=200,
        body="junk",
        content_type="text/xml",
    )

    w_path = DATA_DIR / "watchlist.yaml"

    result = runner.invoke(countdownit, [str(w_path)])
    assert result.exit_code == 0

    with tempfile.NamedTemporaryFile() as tmp:
        result = runner.invoke(countdownit, [str(w_path), "-o", tmp.name])
        assert result.exit_code == 0
