import numpy as np
import pytest

from backend.validation import (
    ValidationError,
    parse_ops,
    parse_params,
    parse_worker_image,
    validate_files,
)
from tp3common import imaging

PNG = imaging.encode_png(np.zeros((8, 8), dtype=np.uint8))


def test_valid_chain():
    assert parse_ops("blur, Sobel") == ["blur", "sobel"]


@pytest.mark.parametrize("raw,code", [("", "missing_ops"), ("sobel,rotate", "unsupported_op")])
def test_invalid_ops(raw, code):
    with pytest.raises(ValidationError) as e:
        parse_ops(raw)
    assert e.value.status == 400 and e.value.code == code


def test_worker_image_whitelist():
    assert parse_worker_image(None) == "tp3-worker"
    with pytest.raises(ValidationError) as e:
        parse_worker_image("evil/miner:latest")
    assert e.value.code == "worker_image_not_allowed"


def test_params_must_be_dict_of_dicts():
    assert parse_params('{"threshold": {"threshold": 90}}') == {"threshold": {"threshold": 90}}
    with pytest.raises(ValidationError):
        parse_params('{"threshold": 90}')
    with pytest.raises(ValidationError):
        parse_params("{no json")


def test_corrupt_file_rejected():
    with pytest.raises(ValidationError) as e:
        validate_files([("a.png", b"\x89PNG basura")])
    assert e.value.code == "invalid_image"


def test_file_too_large(monkeypatch):
    monkeypatch.setattr("tp3common.config.MAX_FILE_MB", 0.00001)
    with pytest.raises(ValidationError) as e:
        validate_files([("a.png", PNG)])
    assert e.value.status == 413


def test_valid_file_ok():
    validate_files([("a.png", PNG)])
