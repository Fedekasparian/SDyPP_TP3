import pytest

from tp3common import blobs


def test_local_store_roundtrip_returns_pointer(tmp_path):
    store = blobs.LocalStore(str(tmp_path))
    uri = store.put(blobs.frag_name("j1", 0, 2, "in"), b"\x89PNG data")
    assert uri.startswith("file://") and uri.endswith("jobs/j1/frag/0/2/in")
    assert store.get(uri) == b"\x89PNG data"


def test_local_store_overwrite_is_idempotent(tmp_path):
    store = blobs.LocalStore(str(tmp_path))
    store.put("jobs/j/out/0", b"a")
    uri = store.put("jobs/j/out/0", b"b")
    assert store.get(uri) == b"b"


def test_missing_blob_raises_not_found(tmp_path):
    store = blobs.LocalStore(str(tmp_path))
    with pytest.raises(blobs.BlobNotFound):
        store.get((tmp_path / "nada").as_uri())


def test_gcs_backend_requires_bucket(monkeypatch):
    monkeypatch.setattr(blobs.config, "BLOB_BACKEND", "gcs")
    monkeypatch.setattr(blobs.config, "BLOB_BUCKET", "")
    blobs.reset_store()
    try:
        with pytest.raises(RuntimeError, match="BLOB_BUCKET"):
            blobs.get_store()
    finally:
        blobs.reset_store()
