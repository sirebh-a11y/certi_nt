"""The PDF assertions use the real app converter, not Word XML as a proxy."""
import os

from docx import Document
import fitz
import pytest

from app.core.pdf.converter import convert_docx_to_pdf
from app.modules.quarta_taglio import certificate_docx as word
from app.modules.quarta_taglio.schemas import QuartaTaglioAggregateValueResponse, QuartaTaglioNoteResponse
from test_certificate_header_height import build, assert_heights
from test_certificate_pdf_attachments_layout import make_pdf
from test_quarta_taglio_docx_content_controls import QuartaTaglioDocxContentControlTests


def full_detail():
    detail = QuartaTaglioDocxContentControlTests._minimal_detail()
    detail.chemistry = [QuartaTaglioAggregateValueResponse(field=key, value=0.21, standard_max=0.35,
        method='test', status='ok') for key in ('Si','Fe','Cu','Mn','Mg','Cr','Zn','Ti','Ni','Pb','Zr')]
    detail.properties = [QuartaTaglioAggregateValueResponse(field=key, value=number, standard_min=number,
        method='test', status='ok') for key, number in (('HB',85),('Rp0.2',283.1),('Rm',310.4),('A%',11.2))]
    detail.notes = [QuartaTaglioNoteResponse(code='print', label='Note', status='ok', message='',
        value=('Material identification and shipment references were verified before final release. ' * 12)
        + 'FINE NOTA TECNICA')]
    return detail


def test_only_first_page_body_text_is_twelve_points(tmp_path):
    sample, additional, empty = [tmp_path / name for name in ('sample.docx','additional.docx','empty.docx')]
    word.build_additional_page_template_docx(additional)
    build(sample, long=True, extra=additional, detail=full_detail())
    build(empty, empty=True)
    doc = Document(sample)
    by_text = {p.text: p for p in doc.paragraphs if p.text.strip()}
    for text, paragraph in by_text.items():
        if text.startswith(('•', 'Notes:', 'Material identification')):
            assert all(r.font.size.pt == 12 for r in paragraph.runs if r.text.strip())
    assert any('FINE NOTA TECNICA' in text for text in by_text)
    assert by_text['Testo o descrizione breve'].runs[0].font.size.pt == 10
    assert by_text['Titolo pagina aggiuntiva'].runs[0].font.size.pt == 12
    assert doc.styles['Normal'].font.size.pt == 9
    assert doc.tables[1].rows[0].cells[1].paragraphs[0].runs[0].font.size.pt == 8
    assert doc.tables[2].rows[0].cells[1].paragraphs[0].runs[0].font.size.pt == 10
    for p in Document(empty).paragraphs:
        if p.text.strip():
            assert all(r.font.size.pt == 12 for r in p.runs if r.text.strip())
    assert_heights(sample)


@pytest.mark.skipif(os.environ.get('CERTI_TEST_RENDER_PDF') != '1', reason='opt-in real LibreOffice render')
@pytest.mark.parametrize('with_pages', [False, True])
def test_pdf_signature_is_inside_printable_area_and_does_not_push_content(tmp_path, with_pages):
    sample, result = tmp_path / 'sample.docx', tmp_path / 'sample.pdf'
    extra = None
    attachments = []
    if with_pages:
        extra = tmp_path / 'additional.docx'
        word.build_additional_page_template_docx(extra)
        for index in range(2):
            path = tmp_path / f'annex{index}.pdf'
            make_pdf(path, [(595, 842, 0)], offset=index)
            attachments.append((path, path.name))
    build(sample, long=True, detail=full_detail(), extra=extra, attachments=attachments)
    convert_docx_to_pdf(sample, result)
    with fitz.open(result) as pdf:
        assert len(pdf) == (4 if with_pages else 1)
        assert 'FINE NOTA TECNICA' in pdf[0].get_text()
        assert 'Chemical composition' in pdf[0].get_text()
        assert 'Mechanical properties' in pdf[0].get_text()
        if with_pages:
            assert 'Titolo pagina aggiuntiva' in pdf[1].get_text()
        for index, page in enumerate(pdf):
            assert 'Operator:' in page.get_text() and 'Quality Manager:' in page.get_text()
            images = [fitz.Rect(info['bbox']) for info in page.get_image_info()]
            signatures = [box for box in images if 39 < box.width < 42]
            assert len(signatures) == 1
            signature = signatures[0]
            margin_mm = (page.rect.height - signature.y1) * 25.4 / 72
            assert 7.5 <= margin_mm <= 10, margin_mm
            if index >= 2:
                annexes = [box for box in images if box.get_area() > 50000]
                assert len(annexes) == 1 and annexes[0].y1 <= signature.y0 - 3
