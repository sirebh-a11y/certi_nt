import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import settings
from app.core.pdf.converter import PDFConversionError, convert_docx_to_pdf


class PDFConverterTest(unittest.TestCase):
    def _fake_soffice(self, root: Path, *, create_pdf: bool = True) -> Path:
        script = root / "fake_soffice.py"
        script.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import sys",
                    "from pathlib import Path",
                    "outdir = Path(sys.argv[sys.argv.index('--outdir') + 1])",
                    "source = Path(sys.argv[-1])",
                    "outdir.mkdir(parents=True, exist_ok=True)",
                    f"create_pdf = {str(create_pdf)}",
                    "if create_pdf:",
                    "    (outdir / (source.stem + '.pdf')).write_bytes(b'%PDF-1.4\\n% certi test\\n')",
                    "sys.exit(0)",
                ]
            ),
            encoding="utf-8",
        )
        os.chmod(script, 0o755)
        return script

    def test_convert_docx_to_pdf_moves_generated_pdf_to_requested_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "certificato.docx"
            target = root / "finale" / "certificato_finale.pdf"
            source.write_bytes(b"docx")
            fake_soffice = self._fake_soffice(root)

            with (
                patch.object(settings, "pdf_conversion_enabled", True),
                patch.object(settings, "pdf_converter", "libreoffice"),
                patch.object(settings, "libreoffice_bin", str(fake_soffice)),
                patch.object(settings, "pdf_conversion_timeout_seconds", 5),
            ):
                result = convert_docx_to_pdf(source, target)

            self.assertEqual(result, target.resolve())
            self.assertTrue(target.exists())
            self.assertTrue(target.read_bytes().startswith(b"%PDF"))

    def test_convert_docx_to_pdf_reports_missing_generated_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "certificato.docx"
            target = root / "certificato.pdf"
            source.write_bytes(b"docx")
            fake_soffice = self._fake_soffice(root, create_pdf=False)

            with (
                patch.object(settings, "pdf_conversion_enabled", True),
                patch.object(settings, "pdf_converter", "libreoffice"),
                patch.object(settings, "libreoffice_bin", str(fake_soffice)),
                patch.object(settings, "pdf_conversion_timeout_seconds", 5),
            ):
                with self.assertRaises(PDFConversionError):
                    convert_docx_to_pdf(source, target)


if __name__ == "__main__":
    unittest.main()
