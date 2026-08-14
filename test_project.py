import ftplib
import gzip
import io
import os
import tarfile
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from core.ftp_client import FTPClient
from core.scheduler import TaskScheduler
from ftp_automation import _safe_download_path, load_config
from handlers.json_handler import JSONHandler
from test_ftp_server import FTPHandler
from utils.compress import decompress_file


class FTPClientTests(unittest.TestCase):
    def test_upload_callback_uses_received_and_total_counts(self):
        class Connection:
            def storbinary(self, command, stream, blocksize, callback):
                while True:
                    chunk = stream.read(3)
                    if not chunk:
                        break
                    callback(chunk)

        client = FTPClient("example")
        client._conn = Connection()
        progress = []
        transferred = client.upload("README.md", "README.md",
                                    lambda done, total: progress.append((done, total)))

        self.assertEqual(transferred, Path("README.md").stat().st_size)
        self.assertEqual(progress[-1], (transferred, transferred))
        self.assertTrue(all(done <= total for done, total in progress))

    def test_list_fallback_preserves_filename_spaces(self):
        class Connection:
            def mlsd(self, remote_dir):
                raise ftplib.error_perm("500 MLSD unsupported")

            def dir(self, remote_dir, callback):
                callback("-rw-r--r-- 1 owner group 12 Jan 1 00:00 report final.csv")

        client = FTPClient("example")
        client._conn = Connection()
        self.assertEqual(client.list_files()[0]["name"], "report final.csv")

    def test_nested_directory_creation_walks_one_segment_at_a_time(self):
        class Connection:
            def __init__(self):
                self.current = "/"
                self.directories = {"/"}

            def cwd(self, path):
                if path == "/":
                    self.current = "/"
                    return
                candidate = f"{self.current.rstrip('/')}/{path}"
                if candidate not in self.directories:
                    raise ftplib.error_perm("550 missing")
                self.current = candidate

            def mkd(self, path):
                self.directories.add(f"{self.current.rstrip('/')}/{path}")

        connection = Connection()
        client = FTPClient("example")
        client._conn = connection
        client.cwd("/created/nested")
        self.assertEqual(connection.current, "/created/nested")

    def test_failed_download_preserves_existing_destination(self):
        class Connection:
            def size(self, remote_path):
                return 8

            def retrbinary(self, command, callback, blocksize):
                callback(b"partial")
                raise ftplib.error_temp("450 interrupted")

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "result.txt"
            destination.write_text("original", encoding="utf-8")
            client = FTPClient("example")
            client._conn = Connection()

            with self.assertRaises(ftplib.error_temp):
                client.download("result.txt", str(destination))

            self.assertEqual(destination.read_text(encoding="utf-8"), "original")
            self.assertEqual(list(Path(directory).glob("*.part")), [])


class ConfigurationAndPathTests(unittest.TestCase):
    def test_missing_explicit_config_fails(self):
        with self.assertRaises(FileNotFoundError):
            load_config("/definitely/missing/custom.yaml")

    def test_password_environment_and_relative_path_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.yaml"
            config_path.write_text(
                "ftp:\n"
                "  host: localhost\n"
                "  password_env: FTP_TEST_PASSWORD\n"
                "tasks:\n"
                "  - action: upload\n"
                "    local_dir: data\n"
                "    remote_dir: /incoming\n",
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"FTP_TEST_PASSWORD": "secret"}):
                config = load_config(str(config_path))

            self.assertEqual(config["ftp"]["password"], "secret")
            self.assertEqual(config["tasks"][0]["local_dir"],
                             str((Path(directory) / "data").resolve()))

    def test_download_path_rejects_remote_traversal(self):
        with self.assertRaises(ValueError):
            _safe_download_path("downloads", "../escaped.txt")
        with self.assertRaises(ValueError):
            _safe_download_path("downloads", "folder/file.txt")

    def test_test_server_confines_paths_to_root(self):
        handler = FTPHandler(None, None, "/private/tmp/ftp-root")
        with self.assertRaises(PermissionError):
            handler._abs("../../escaped.txt")


class SchedulerTests(unittest.TestCase):
    def test_standard_sunday_values_match(self):
        sunday = datetime(2026, 8, 16, 0, 0)
        self.assertTrue(TaskScheduler._match_cron("0 0 * * 0", sunday))
        self.assertTrue(TaskScheduler._match_cron("0 0 * * 7", sunday))

    def test_invalid_schedules_are_rejected(self):
        scheduler = TaskScheduler()
        with self.assertRaises(ValueError):
            scheduler.every(0, lambda: None)
        with self.assertRaises(ValueError):
            scheduler.cron("60 * * * *", lambda: None)


class HandlerAndArchiveTests(unittest.TestCase):
    def test_uppercase_jsonl_with_blank_lines_is_consistent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.JSONL"
            path.write_text('{"id": 1}\n\n{"id": 2}\n', encoding="utf-8")
            handler = JSONHandler()
            self.assertTrue(handler.validate(path))
            self.assertEqual(handler.read(path), [{"id": 1}, {"id": 2}])

    def test_tar_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "unsafe.tar"
            with tarfile.open(archive, "w") as tf:
                payload = b"escaped"
                member = tarfile.TarInfo("../escaped.txt")
                member.size = len(payload)
                tf.addfile(member, io.BytesIO(payload))

            with self.assertRaises(ValueError):
                decompress_file(str(archive), str(Path(directory) / "output"))
            self.assertFalse((Path(directory) / "escaped.txt").exists())

    def test_gzip_expansion_limit_removes_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "large.txt.gz"
            with gzip.open(archive, "wb") as stream:
                stream.write(b"x" * 64)

            with self.assertRaises(ValueError):
                decompress_file(str(archive), directory, max_bytes=32)
            self.assertFalse((Path(directory) / "large.txt").exists())


if __name__ == "__main__":
    unittest.main()
