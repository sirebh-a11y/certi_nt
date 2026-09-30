"""Download names are independent from certificate identity and storage paths."""
import re

from app.modules.quarta_taglio.models import QuartaTaglioFinalCertificate


def standard_certificate_file_name(certificate: QuartaTaglioFinalCertificate, extension: str) -> str:
    number = certificate.certificate_number or certificate.draft_number
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(number or "").strip()).strip("._") or "certificato"
    return f"{stem}.{extension}"


def certificate_pdf_file_name(certificate: QuartaTaglioFinalCertificate) -> str:
    return getattr(certificate, "pdf_file_name", None) or standard_certificate_file_name(certificate, "pdf")


def normalize_pdf_file_name(value: str) -> str:
    if re.search(r'[\\/:*?"<>|\x00-\x1f\x7f]', value):
        raise ValueError('Il nome PDF non può contenere / \\ : * ? " < > | o caratteri di controllo.')
    name = value.strip()
    stem = name[:-4] if name.lower().endswith(".pdf") else name
    if not stem or stem.startswith(".") or stem.endswith((".", " ")):
        raise ValueError("Inserisci un nome PDF valido, senza punti o spazi finali.")
    if re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", stem.split(".")[0], re.IGNORECASE):
        raise ValueError("Questo nome file è riservato dal sistema. Scegli un altro nome.")
    name = f"{stem}.pdf"
    if len(name) > 255:
        raise ValueError("Il nome PDF può contenere al massimo 255 caratteri, inclusa l'estensione .pdf.")
    return name
