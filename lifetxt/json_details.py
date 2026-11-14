"""JSON detail value codec shared by the parser and interchange formats."""

import json
import math


def _finite_float(raw):
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("JSON numbers must be finite.")
    return value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON object keys must be unique.")
        result[key] = value
    return result


DECODER = json.JSONDecoder(
    parse_float=_finite_float,
    parse_constant=_finite_float,
    object_pairs_hook=_unique_object,
)


def encode_json_value(value):
    # ASCII escaping also keeps all Unicode line separators within one line.
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
