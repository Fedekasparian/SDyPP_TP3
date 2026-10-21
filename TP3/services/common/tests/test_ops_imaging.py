import numpy as np
import pytest

from tp3common import imaging, ops


@pytest.fixture
def rgb():
    rng = np.random.default_rng(42)
    return rng.integers(0, 256, size=(97, 64, 3), dtype=np.uint8)


def test_sobel_flat_image_has_no_edges():
    flat = np.full((10, 10), 120, dtype=np.uint8)
    assert ops.sobel(flat).max() == 0


def test_sobel_detects_vertical_edge():
    img = np.zeros((10, 10), dtype=np.uint8)
    img[:, 5:] = 255
    out = ops.sobel(img)
    assert out[:, 4:6].min() == 255
    assert out[:, :3].max() == 0


def test_threshold_is_binary(rgb):
    assert set(np.unique(ops.threshold(rgb, threshold=100))) <= {0, 255}


@pytest.mark.parametrize("chain", [["sobel"], ["blur", "sobel"], ["grayscale", "blur", "threshold"]])
@pytest.mark.parametrize("n", [1, 3, 7])
def test_split_process_join_equals_full_image(rgb, chain, n):
    """Propiedad clave del sistema distribuido: partir + procesar + unir == procesar entero."""
    expected = ops.apply_chain(rgb, chain)
    strips = imaging.split_strips(rgb, n, ops.required_overlap(chain))
    cores = [imaging.crop_core(ops.apply_chain(s.data, chain), s.pad_top, s.core_h) for s in strips]
    np.testing.assert_array_equal(imaging.join_strips(cores), expected)


def test_encode_decode_roundtrip(rgb):
    data = imaging.encode_png(rgb)
    assert imaging.image_format(data) == "PNG"
    np.testing.assert_array_equal(imaging.decode(data), rgb)


def test_invalid_image_format():
    assert imaging.image_format(b"esto no es una imagen") is None
