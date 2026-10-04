"""A rollback must give back the bytes that were there, not a re-encoded copy of the text."""

from cortex.core.transaction import MEMORY_BACKUP_THRESHOLD, TransactionManager


def _manager(tmp_path):
    return TransactionManager(backup_dir=tmp_path / "backups")


def test_crlf_file_comes_back_unchanged(tmp_path):
    target = tmp_path / "f.txt"
    original = b"one\r\ntwo\r\n"
    target.write_bytes(original)
    tm = _manager(tmp_path)
    tm.begin()
    tm.backup_file(target, "edit")
    target.write_bytes(b"changed\n")

    assert tm.rollback() is True

    assert target.read_bytes() == original


def test_file_that_is_not_utf8_is_backed_up_and_restored(tmp_path):
    target = tmp_path / "blob.bin"
    original = bytes(range(256))
    target.write_bytes(original)
    tm = _manager(tmp_path)
    tm.begin()

    backup = tm.backup_file(target, "write")
    target.write_bytes(b"gone")

    assert backup is not None, "an undecodable file must still be backed up"
    assert tm.rollback() is True
    assert target.read_bytes() == original


def test_large_file_comes_back_unchanged(tmp_path):
    target = tmp_path / "big.bin"
    original = b"\r\n".join(b"line %d" % i for i in range(MEMORY_BACKUP_THRESHOLD // 4))
    assert len(original) > MEMORY_BACKUP_THRESHOLD
    target.write_bytes(original)
    tm = _manager(tmp_path)
    tm.begin()
    tm.backup_file(target, "edit")
    target.write_bytes(b"x")

    assert tm.rollback() is True

    assert target.read_bytes() == original
