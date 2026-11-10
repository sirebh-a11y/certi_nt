"""App-owned attachment pagination only; temporary files, no production DB."""
import hashlib
import os
from pathlib import Path
import zipfile
from unittest.mock import patch

import fitz
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree
import pytest

from app.core.pdf.converter import convert_docx_to_pdf
from app.modules.quarta_taglio import certificate_docx as word, ddt_word_reuse as reuse, service
from test_certificate_header_height import build, parts, rewrite_headers, assert_heights

COLORS = [(0.94, 0.84, 0.78), (0.78, 0.94, 0.84), (0.82, 0.84, 0.96)]
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}


def make_pdf(path, sizes, offset=0, blank=False):
    with fitz.open() as pdf:
        for index, spec in enumerate(sizes):
            width, height, rotation = spec
            page = pdf.new_page(width=width, height=height)
            color = COLORS[(offset + index) % len(COLORS)]
            if not blank:
                page.draw_rect(page.rect, fill=color, color=color)
                page.insert_text((35, 55), f'ATTACHMENT {offset + index + 1}', fontsize=16)
            page.set_rotation(rotation)
        pdf.save(path)


def legacy_breaks(path, *, old_maximum=False):
    """Reproduce old app-generated files, including the empty break paragraph."""
    doc = Document(path)
    old_cap = (int(doc.sections[-1].page_height) - int(doc.sections[-1].top_margin)
               - int(doc.sections[-1].bottom_margin) - int(word.Inches(0.10)))
    new_cap = old_cap - int(word.Inches(0.10))
    count = 0
    for paragraph in doc.paragraphs:
        if paragraph.text == word.PDF_ATTACHMENT_PAGE_MARKER:
            if old_maximum:
                from docx.shape import InlineShape
                inline = paragraph._p.getnext().xpath('.//wp:inline')[0]
                picture = InlineShape(inline)
                if picture.height >= new_cap - 635:
                    picture.width = round(picture.width * old_cap / picture.height)
                    picture.height = old_cap
            paragraph.paragraph_format.keep_with_next = None
            paragraph.paragraph_format.page_break_before = None
            if count:
                before = OxmlElement('w:p')
                run, br = OxmlElement('w:r'), OxmlElement('w:br')
                br.set(qn('w:type'), 'page')
                run.append(br)
                before.append(run)
                paragraph._p.addprevious(before)
            count += 1
    assert count >= 2
    doc.save(path)


def picture_facts(path):
    doc = Document(path)
    result = []
    children = list(doc._body._element)
    for index, child in enumerate(children[:-1]):
        if ''.join(child.itertext()).strip() != word.PDF_ATTACHMENT_PAGE_MARKER:
            # python-docx element itertext can repeat w:t via proxy access.
            if ''.join(n.text or '' for n in child.iter(qn('w:t'))).strip() != word.PDF_ATTACHMENT_PAGE_MARKER:
                continue
        drawing = children[index + 1]
        blips = drawing.xpath('.//a:blip')
        assert len(blips) == 1
        blob = doc.part.related_parts[blips[0].get(qn('r:embed'))].blob
        pixmap = fitz.Pixmap(blob)
        result.append((pixmap.width, pixmap.height, hashlib.sha256(pixmap.samples).hexdigest()))
    return result


def source_picture_facts(paths):
    result = []
    for path in paths:
        with fitz.open(path) as pdf:
            for page in pdf:
                image = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                result.append((image.width, image.height, hashlib.sha256(image.samples).hexdigest()))
    return result


def test_old_attachment_breaks_are_repaired_without_changing_other_parts(tmp_path):
    pdf, path = tmp_path / 'two.pdf', tmp_path / 'word.docx'
    make_pdf(pdf, [(595, 842, 0)] * 2)
    build(path, attachments=[(pdf, 'two.pdf')])
    expected = picture_facts(path)
    legacy_breaks(path)
    before = parts(path)
    assert word.certificate_docx_needs_layout_update(path)
    word.normalize_certificate_docx_layout(path)
    after = parts(path)
    assert_heights(path)
    assert picture_facts(path) == expected == source_picture_facts([pdf])
    for name, data in before.items():
        if name != 'word/document.xml':
            assert after[name] == data, name
    stable = path.read_bytes()
    word.normalize_certificate_docx_layout(path)
    assert path.read_bytes() == stable


def test_old_new_comparison_does_not_weaken_raw_integrity_or_hide_user_text(tmp_path):
    pdf = tmp_path / 'two.pdf'
    make_pdf(pdf, [(595, 842, 0)] * 2)
    current, old = tmp_path / 'new.docx', tmp_path / 'old.docx'
    build(current, attachments=[(pdf, 'two.pdf')])
    old.write_bytes(current.read_bytes())
    legacy_breaks(old)
    # python-docx save rewrites Word metadata; use the same save round trip for
    # both, so the comparison is specifically about attachment pagination.
    Document(current).save(current)
    with patch.object(service, '_certificate_storage_path', side_effect=Path):
        assert reuse.word_facts(str(current))[1] != reuse.word_facts(str(old))[1]
        assert reuse.word_facts(str(current), compare_managed_layout=True)[1] == reuse.word_facts(str(old), compare_managed_layout=True)[1]
        doc = Document(old)
        doc.add_paragraph('USER LABORATORY TEXT MUST NOT BE IGNORED')
        doc.save(old)
        assert reuse.word_facts(str(current), compare_managed_layout=True)[1] != reuse.word_facts(str(old), compare_managed_layout=True)[1]


@pytest.mark.parametrize('reason', ['visible_marker', 'caption', 'bookmark_break'])
def test_normalizer_keeps_unverified_or_user_owned_page_boundaries(tmp_path, reason):
    pdf, path = tmp_path / 'two.pdf', tmp_path / 'word.docx'
    make_pdf(pdf, [(595, 842, 0)] * 2)
    build(path, attachments=[(pdf, 'two.pdf')])
    legacy_breaks(path)
    doc = Document(path)
    for paragraph in doc.paragraphs:
        if paragraph.text == word.PDF_ATTACHMENT_PAGE_MARKER:
            if reason == 'visible_marker':
                for run in paragraph.runs:
                    run.font.hidden = False
            elif reason == 'caption':
                from docx.text.paragraph import Paragraph
                Paragraph(paragraph._p.getnext(), doc._body).add_run('USER CAPTION')
            elif paragraph._p.getprevious() is not None:
                bookmark = OxmlElement('w:bookmarkStart')
                bookmark.set(qn('w:id'), '50')
                bookmark.set(qn('w:name'), 'UserBookmark')
                paragraph._p.getprevious().append(bookmark)
    doc.save(path)
    before = parts(path)['word/document.xml']
    if reason == 'bookmark_break':
        # First marker still receives only the safe keep-with-next property.
        normalized = word.canonical_app_attachment_breaks(before.decode())
        assert 'UserBookmark' in normalized
        assert '<w:br w:type="page"' in normalized
    else:
        assert word.canonical_app_attachment_breaks(before.decode()).encode() == before


@pytest.mark.skipif(os.environ.get('CERTI_TEST_RENDER_PDF') != '1', reason='opt-in real LibreOffice render')
@pytest.mark.parametrize('kind,extra', [('portrait', False), ('two_files', True), ('mixed', False), ('rotated', True), ('blank_original', False), ('legacy_repair', True)])
def test_real_pdf_has_exactly_one_page_per_attachment_without_loss(tmp_path, kind, extra):
    sizes = [(595, 842, 0)] * 2
    if kind == 'mixed':
        sizes = [(842, 595, 0), (420, 595, 0), (400, 1000, 0)]
    elif kind == 'rotated':
        sizes = [(595, 842, 90), (842, 595, 270)]
    paths = []
    if kind == 'two_files':
        for index, size in enumerate(sizes):
            pdf = tmp_path / f'attachment_{index}.pdf'
            make_pdf(pdf, [size], offset=index)
            paths.append(pdf)
    else:
        pdf = tmp_path / 'attachment.pdf'
        make_pdf(pdf, sizes, blank=kind == 'blank_original')
        paths.append(pdf)
    original = {p: p.read_bytes() for p in paths}
    template = None
    if extra:
        template = tmp_path / 'template.docx'
        word.build_additional_page_template_docx(template)
    path = tmp_path / 'word.docx'
    build(path, extra=template, attachments=[(p, p.name) for p in paths])
    if kind == 'legacy_repair':
        legacy_breaks(path, old_maximum=True)
        preserved = tmp_path / 'preserved_source.docx'
        preserved.write_bytes(path.read_bytes())
        word.update_docx_content_controls(preserved, path, {})
        assert preserved.read_bytes() != path.read_bytes()
    assert picture_facts(path) == source_picture_facts(paths)
    output = tmp_path / 'result.pdf'
    convert_docx_to_pdf(path, output)
    base_pages = 2 if extra else 1
    with fitz.open(output) as final:
        assert len(final) == base_pages + len(sizes)
        for index, page in enumerate(final):
            assert 'Operator:' in page.get_text() and 'Quality Manager:' in page.get_text()
            if index < base_pages:
                assert f'Pag. {index + 1} / {len(final)}' in page.get_text()
            else:
                images = [i for i in page.get_image_info(xrefs=True) if fitz.Rect(i['bbox']).get_area() > 50000]
                assert len(images) == 1  # A large white source page is retained too.
                image = fitz.Pixmap(final, images[0]['xref'])
                pixel = image.pixel(image.width // 2, image.height // 2)[:3]
                color = (1, 1, 1) if kind == 'blank_original' else COLORS[(index - base_pages) % 3]
                assert all(abs(actual - round(expected * 255)) <= 4 for actual, expected in zip(pixel, color))
    assert all(p.read_bytes() == original[p] for p in paths)


def test_reupload_strip_and_reattach_preserve_manual_content_and_signatures(tmp_path):
    pdf, path = tmp_path / 'two.pdf', tmp_path / 'word.docx'
    make_pdf(pdf, [(595, 842, 0)] * 2)
    build(path, attachments=[(pdf, 'two.pdf')])
    doc = Document(path)
    doc.add_page_break()
    doc.add_paragraph('MANUAL LABORATORY PAGE AFTER ATTACHMENTS')
    doc.save(path)
    footer = parts(path)['word/footer1.xml']
    base = tmp_path / 'manual_base.docx'
    word.prepare_manual_docx_base(path, base)
    assert 'MANUAL LABORATORY PAGE AFTER ATTACHMENTS' in '\n'.join(p.text for p in Document(base).paragraphs)
    assert not picture_facts(base)
    assert parts(base)['word/footer1.xml'] == footer
    again = tmp_path / 'attached_again.docx'
    from app.core.users.models import User
    actor = User(name='Operatore di prova', email='qa@example.invalid', role='admin')
    word.append_pdf_attachments_to_docx(base_docx_path=base, output_path=again,
        pdf_attachments=[(pdf, 'two.pdf')], certified_by=actor, quality_manager=actor)
    assert picture_facts(again) == source_picture_facts([pdf])
    assert 'MANUAL LABORATORY PAGE AFTER ATTACHMENTS' in '\n'.join(p.text for p in Document(again).paragraphs)
