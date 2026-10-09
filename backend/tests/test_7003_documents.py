"""Real application Word builder, no production records or document writes."""
from pathlib import Path
import pytest
from docx import Document
from app.core.users.models import User
from app.modules.quarta_taglio.certificate_docx import build_forgialluminio_draft_docx, update_docx_content_controls
from app.modules.quarta_taglio.schemas import QuartaTaglioStandardCandidateResponse as Candidate, QuartaTaglioAggregateValueResponse as Value
import test_quarta_taglio_docx_content_controls as docx_fixture


def build_sample(path, basis="A50mm", alloy="7003", long=False):
    detail = docx_fixture.QuartaTaglioDocxContentControlTests._minimal_detail()
    detail.header = {"lega": alloy, "colata": "7003-TEST", "ddt": "100-09/10/2026",
                     "cliente": "CLIENTE DI PROVA", "data_certificato": "09/10/2026"}
    detail.selected_standard = Candidate(id=901, code="TEST", label="TEST", lega_base=alloy,
        norma="EN AW 755-2", trattamento_termico="T6", elongation_basis=basis, confidence="confermata", score=999)
    detail.properties = [Value(field=f, value=v, standard_min=m, method="min", status="ok") for f,v,m in
                         [("HB",110,100),("diametro",150,0),("S",150,0),("Rp0.2", 1234.56 if long else 290,280),
                          ("Rm",2345.67 if long else 350,340),("A%",9.99 if long else 9,8 if basis=="A50mm" else 10),
                          ("Rp0.2 / Rm",0.83,None),("IACS%",38.5,35)]]
    detail.chemistry = [Value(field=f, value=v, standard_max=1, method="weighted", status="ok")
                        for f,v in [("Si",0.12),("Fe",0.18),("Cu",0.05),("Mn",0.08),("Mg",0.8),("Zn",6.2),("Ti",0.04)]]
    user = User(name="Operatore di prova", email="test@example.invalid", role="admin")
    build_forgialluminio_draft_docx(detail=detail, output_path=path, draft_number="7003_00_00/26", certified_by=user, quality_manager=user)
    return detail


@pytest.mark.parametrize("basis,alloy,expected", [("A50mm","7003","A50mm (%)"),("A","7003","A(%)"),
    (None,"7003","A(%)"),("A50mm","7055","A(%)"),(None,"6082","A(%)")])
def test_real_word_header_and_numeric_values(tmp_path, basis, alloy, expected):
    path = tmp_path / "sample.docx"
    build_sample(path, basis, alloy)
    doc = Document(path)
    table = next(t for t in doc.tables if "Rp0,2" in " ".join(c.text for c in t.rows[0].cells) or "Rm" in " ".join(c.text for c in t.rows[0].cells))
    headers = [c.text for c in table.rows[0].cells]
    assert expected in headers
    col = headers.index(expected)
    assert table.rows[2].cells[col].text == "9"
    runs = table.rows[0].cells[col].paragraphs[0].runs
    assert any(r.text == "50mm" and r.font.subscript for r in runs) == (expected == "A50mm (%)")
    assert all(r.bold for r in runs if r.text)


if __name__ == "__main__":
    # Dedicated QA output only; use the exact application PDF conversion path.
    import fitz
    from app.core.pdf.converter import convert_docx_to_pdf
    target = Path("/tmp/certi_7003_visual")
    target.mkdir(exist_ok=True)
    for name, basis, alloy, long in [("a50", "A50mm", "7003", False), ("ordinary", "A", "7003", False),
                                     ("long", "A50mm", "7003", True), ("other", None, "7055", False)]:
        word = target / (name + ".docx")
        build_sample(word, basis, alloy, long)
        pdf = target / (name + ".pdf")
        convert_docx_to_pdf(word, pdf)
        with fitz.open(pdf) as document:
            assert len(document) == 1, (name, len(document))
            for index, page in enumerate(document):
                page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(target / f"{name}-{index+1}.png")
            print(name, "pages", len(document), "allungamento", [line for line in document[0].get_text().splitlines() if "50mm" in line or "A(%)" in line])
