import os
import sys
from pathlib import Path
import json

sys.path.insert(0, os.path.abspath(".."))

import woolworther

# Body for mock responses
BODY = json.dumps(
    {
        "sku": "32467",
        "name": "Green & Blacks Chocolate Block Dark 85% Cocoa",
        "description": "description",
        "size": {"volumeSize": "90g", "cupMeasure": "100g", "cupPrice": 3.3},
        "price": {"originalPrice": 3.33, "salePrice": 3},
    }
)
