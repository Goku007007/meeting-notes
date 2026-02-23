import tempfile
import unittest
from pathlib import Path

from app.processing import (
    NoExtractableTextError,
    UnsupportedFormatError,
    extract_text_from_file,
    validate_supported_upload,
)


class FileProcessingTests(unittest.TestCase):
    def test_validate_supported_upload_accepts_valid_pdf(self) -> None:
        ext, mime = validate_supported_upload("notes.pdf", "application/pdf")
        self.assertEqual(ext, ".pdf")
        self.assertEqual(mime, "application/pdf")

    def test_validate_supported_upload_rejects_unsupported_extension(self) -> None:
        with self.assertRaises(UnsupportedFormatError):
            validate_supported_upload("payload.exe", "application/octet-stream")

    def test_validate_supported_upload_rejects_mime_extension_mismatch(self) -> None:
        with self.assertRaises(UnsupportedFormatError):
            validate_supported_upload("notes.pdf", "text/plain")

    def test_extract_text_from_txt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notes.txt"
            path.write_text("hello world\nfrom tests", encoding="utf-8")
            extracted = extract_text_from_file(str(path), "text/plain")
            self.assertIn("hello world", extracted)

    def test_extract_text_from_image_without_ocr_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "image.png"
            path.write_bytes(b"not-a-real-image")
            with self.assertRaises(NoExtractableTextError):
                extract_text_from_file(str(path), "image/png")


if __name__ == "__main__":
    unittest.main()
