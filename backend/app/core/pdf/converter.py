from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.config import settings


class PDFConversionError(RuntimeError):
    """Raised when the server cannot convert a DOCX into a PDF."""


def convert_docx_to_pdf(
    source_path: Path,
    output_path: Path,
    *,
    timeout_seconds: int | None = None,
) -> Path:
    """Convert one DOCX file to PDF with the configured backend converter.

    LibreOffice writes the PDF using the input stem inside the requested output
    directory. We convert in a temporary folder first, then move the result to
    the exact storage path requested by the application.
    """
    if not settings.pdf_conversion_enabled:
        raise PDFConversionError("Conversione PDF disabilitata")
    if settings.pdf_converter.lower() != "libreoffice":
        raise PDFConversionError(f"Convertitore PDF non supportato: {settings.pdf_converter}")

    source = Path(source_path).resolve()
    target = Path(output_path).resolve()
    if not source.exists():
        raise PDFConversionError(f"File Word non trovato: {source}")
    if source.suffix.lower() != ".docx":
        raise PDFConversionError("La conversione PDF accetta solo file .docx")

    soffice = settings.libreoffice_bin
    if not soffice or shutil.which(soffice) is None:
        raise PDFConversionError(f"LibreOffice non trovato: {soffice}")

    timeout = timeout_seconds if timeout_seconds is not None else settings.pdf_conversion_timeout_seconds
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="certi_pdf_") as tmp_root:
        tmp_dir = Path(tmp_root)
        out_dir = tmp_dir / "out"
        profile_dir = tmp_dir / "lo_profile"
        out_dir.mkdir()
        profile_dir.mkdir()

        command = [
            soffice,
            f"-env:UserInstallation={profile_dir.as_uri()}",
            "--headless",
            "--nologo",
            "--nofirststartwizard",
            "--nodefault",
            "--nolockcheck",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(source),
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout or "").strip()
            raise PDFConversionError(f"LibreOffice non ha convertito il Word: {message or 'errore sconosciuto'}")

        generated = out_dir / f"{source.stem}.pdf"
        if not generated.exists():
            message = (completed.stdout or completed.stderr or "").strip()
            raise PDFConversionError(f"PDF non generato da LibreOffice: {message or generated.name}")
        shutil.move(str(generated), str(target))

    return target
