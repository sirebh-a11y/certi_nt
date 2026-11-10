"""Header geometry only: isolated files/DB, never Alpha or company services."""
from copy import deepcopy
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

from lxml import etree
import pytest

from app.core.users.models import User
from app.modules.quarta_taglio import certificate_docx as word, service, word_reference as refs
from app.modules.quarta_taglio import ddt_word_reuse as reuse
import test_quarta_taglio_docx_content_controls as fixtures
import test_quarta_taglio_word_lifecycle as lifecycle
import test_quarta_taglio_ddt_word_reuse as reuse_tests

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{" + NS["w"] + "}"


def parts(path):
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def rewrite_headers(path, change):
    contents = parts(path)
    for name, data in contents.items():
        if name.startswith("word/header") and name.endswith(".xml"):
            root = etree.fromstring(data)
            change(root)
            contents[name] = etree.tostring(root)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in contents.items():
            archive.writestr(name, data)


def flow_rows(root):
    return root.xpath('//w:tbl[w:tr//w:tag[@w:val="COD_F3_RAW"]]/w:tr', namespaces=NS)


def assert_heights(path):
    found = 0
    for name, data in parts(path).items():
        if name.startswith("word/header") and name.endswith(".xml"):
            for index, row in enumerate(flow_rows(etree.fromstring(data))):
                h = row.find("./w:trPr/w:trHeight", NS)
                expected = word.HEADER_FLOW_ROW_HEIGHT if index == 0 else word.HEADER_FLOW_DETAIL_ROW_HEIGHT
                assert h is not None
                assert h.get(W + "val") == str(expected.twips)
                assert h.get(W + "hRule") == "atLeast"
                found += 1
    assert found >= 4
    assert not word.certificate_docx_needs_layout_update(path)


def old_geometry(root):
    for row in flow_rows(root):
        row.find("./w:trPr/w:trHeight", NS).set(W + "val", "355")


def build(path, *, empty=False, long=False, extra=None, attachments=None):
    detail = fixtures.QuartaTaglioDocxContentControlTests._minimal_detail()
    detail.header.update({
        "cliente": "CLIENTE DI PROVA", "ordine_cliente": "ORD-2026-001234",
        "conferma_ordine": "CDO-123456", "data_certificato": "10/11/2026",
        "codice_f3_raw": "096001100", "codice_f3_finished": "096001101",
        "descrizione_raw": "GREZZO DI PROVA", "descrizione_finished": "FINITO DI PROVA",
        "ddt_raw": "" if empty else "2026/DDT-000123456789-10/11/2026" if long else "1133-10/11/2026",
        "ddt_finished": "" if empty else "1456-10/11/2026",
        "quantita_raw": "" if empty else "999,999 of 1,999,999" if long else "200 of 23000",
        "quantita_finished": "" if empty else "208",
    })
    user = User(name="Operatore di prova", email="qa@example.invalid", role="admin")
    word.build_forgialluminio_draft_docx(detail=detail, output_path=path,
        draft_number="7000_00_00/26", certified_by=user, quality_manager=user,
        additional_pages_path=extra, pdf_attachments=attachments)
    return detail


@pytest.mark.parametrize("empty,long", [(True, False), (False, False), (False, True)])
def test_generated_header_has_shared_order_ddt_quantity_height(tmp_path, empty, long):
    path = tmp_path / "generated.docx"
    build(path, empty=empty, long=long)
    assert_heights(path)
    before = path.read_bytes()
    word.normalize_certificate_docx_layout(path)
    assert path.read_bytes() == before


def test_a4_rounding_does_not_resave_an_already_normalized_document(tmp_path):
    from docx.document import Document as DocxDocument
    path = tmp_path / 'a4.docx'
    build(path)
    with patch.object(DocxDocument, 'save', side_effect=AssertionError('already-A4 must not be re-saved')):
        word._ensure_docx_a4_page_size(path)


@pytest.mark.parametrize("rule", ["atLeast", "exact", "missing", "missing_properties", "missing_with_attributes"])
def test_motor_restores_height_without_touching_text_fonts_or_other_parts(tmp_path, rule):
    path = tmp_path / "manual.docx"
    build(path)
    def changed(root):
        for row in flow_rows(root)[1:]:
            h = row.find("./w:trPr/w:trHeight", NS)
            if rule == "missing_properties":
                row.remove(h.getparent())
            elif rule == "missing":
                h.getparent().remove(h)
            elif rule == "missing_with_attributes":
                prop = h.getparent()
                prop.remove(h)
                prop.set('{urn:certi-test}audit', 'preserve')
            else:
                h.set(W + "val", "1700")
                h.set(W + "hRule", rule)
    rewrite_headers(path, changed)
    before = parts(path)
    assert word.certificate_docx_needs_layout_update(path)
    word.normalize_certificate_docx_layout(path)
    assert_heights(path)
    if rule == 'missing_with_attributes':
        root = etree.fromstring(parts(path)['word/header1.xml'])
        for row in flow_rows(root)[1:]:
            assert len(row.findall('w:trPr', NS)) == 1
            assert row.find('w:trPr', NS).get('{urn:certi-test}audit') == 'preserve'
    after = parts(path)
    for name, data in before.items():
        if name.startswith("word/header") and name.endswith(".xml"):
            left, right = etree.fromstring(data), etree.fromstring(after[name])
            for root in (left, right):
                for row in flow_rows(root):
                    for h in row.xpath("./w:trPr/w:trHeight", namespaces=NS):
                        h.getparent().remove(h)
                    # Ignore an empty/new row-properties wrapper, not its contents.
                    for prop in row.xpath("./w:trPr[not(*)]", namespaces=NS):
                        prop.getparent().remove(prop)
            assert etree.tostring(left, method="c14n") == etree.tostring(right, method="c14n")
        else:
            assert after[name] == data, name


def test_motor_does_not_change_other_header_tables(tmp_path):
    path = tmp_path / "custom.docx"
    build(path)
    custom = ('<w:tbl xmlns:w="' + NS['w'] + '"><w:tr><w:trPr>'
              '<w:trHeight w:val="1200" w:hRule="exact"/></w:trPr><w:tc>'
              '<w:p><w:r><w:t>Quantity: ordinary user table</w:t></w:r></w:p>'
              '</w:tc></w:tr></w:tbl>')
    def changed(root):
        root.insert(0, etree.fromstring(custom))
        old_geometry(root)
    rewrite_headers(path, changed)
    before = parts(path)["word/header1.xml"]
    word.normalize_certificate_docx_layout(path)
    after = parts(path)["word/header1.xml"]
    for data in (before, after):
        first = etree.fromstring(data).find("w:tbl", NS)
        assert first.find("./w:tr/w:trPr/w:trHeight", NS).get(W + 'val') == '1200'
    assert_heights(path)


def test_legacy_labels_without_sdt_tags_are_still_normalized(tmp_path):
    path = tmp_path / "legacy.docx"
    build(path)
    def changed(root):
        old_geometry(root)
        for tag in root.xpath('//w:tag', namespaces=NS):
            tag.getparent().remove(tag)
    rewrite_headers(path, changed)
    word.normalize_certificate_docx_layout(path)
    root = etree.fromstring(parts(path)["word/header1.xml"])
    table = next(t for t in root.findall("w:tbl", NS) if "Cod. F3 Raw:" in ''.join(t.itertext()))
    assert [r.find('./w:trPr/w:trHeight', NS).get(W+'val') for r in table.findall('w:tr', NS)] == ['355', '538', '538', '538']


def test_manual_input_empty_fields_and_next_ddt_keep_geometry_and_typography(tmp_path):
    source, manual, base, next_ddt = [tmp_path / name for name in ('source.docx', 'manual.docx', 'base.docx', 'next.docx')]
    build(source, empty=True)
    values = {'DDT_RAW': '2679-10/11/2026', 'QUANTITY_RAW': '200 of 23000'}
    # Equivalent to typing only inside the existing Word text controls.
    word.update_docx_content_controls(source, manual, values)
    word.prepare_manual_docx_base(manual, base)
    assert_heights(manual)
    assert_heights(base)
    word.update_docx_content_controls(base, next_ddt, {'DDT_RAW': '2680-11/11/2026', 'QUANTITY_RAW': '999,999 of 1,999,999'})
    assert_heights(next_ddt)
    for tag in values:
        properties = []
        for path in (source, manual, next_ddt):
            root = etree.fromstring(parts(path)['word/header1.xml'])
            rpr = root.xpath('//w:sdt[w:sdtPr/w:tag[@w:val="' + tag + '"]]/w:sdtContent/w:r/w:rPr', namespaces=NS)[0]
            properties.append(etree.tostring(rpr, method='c14n'))
        assert properties[0] == properties[1] == properties[2]


@pytest.mark.parametrize('difference', ['profile_only', 'custom_height', 'first_row_custom_height', 'exact_rule', 'font', 'text'])
def test_comparison_ignores_only_known_app_height_profiles(tmp_path, difference):
    source, other = tmp_path / 'source.docx', tmp_path / 'other.docx'
    build(source)
    other.write_bytes(source.read_bytes())
    def changed(root):
        old_geometry(root)
        row = flow_rows(root)[2]
        height = row.find('./w:trPr/w:trHeight', NS)
        if difference == 'custom_height':
            height.set(W+'val', '1200')
        elif difference == 'first_row_custom_height':
            flow_rows(root)[0].find('./w:trPr/w:trHeight', NS).set(W+'val', '538')
        elif difference == 'exact_rule':
            height.set(W+'hRule', 'exact')
        elif difference == 'font':
            row.xpath('.//w:rPr/w:sz', namespaces=NS)[0].set(W+'val', '28')
        elif difference == 'text':
            row.xpath('.//w:t', namespaces=NS)[0].text = 'MANUAL TECHNICAL TEXT'
    rewrite_headers(other, changed)
    with patch.object(service, '_certificate_storage_path', side_effect=Path):
        raw = [reuse.word_facts(str(path))[1] for path in (source, other)]
        comparison = [reuse.word_facts(str(path), compare_managed_layout=True)[1] for path in (source, other)]
    assert raw[0] != raw[1]
    assert (comparison[0] == comparison[1]) == (difference == 'profile_only')


class HeaderHeightLifecycleTest(lifecycle.WordLifecycleTest):
    def test_old_closed_word_with_legacy_attachment_breaks_remains_reusable(self):
        import test_certificate_pdf_attachments_layout as attachments
        from app.modules.quarta_taglio.certificate_docx import append_pdf_attachments_to_docx
        _, source = self.base_word(closed=True)
        original = service._certificate_storage_path(source.storage_key_docx)
        pdf = Path(self.files.name) / 'historic_attachment.pdf'
        attachments.make_pdf(pdf, [(595, 842, 0)] * 2)
        append_pdf_attachments_to_docx(base_docx_path=original, output_path=original,
            pdf_attachments=[(pdf, 'historic.pdf')], certified_by=self.actor, quality_manager=self.actor)
        attachments.legacy_breaks(original, old_maximum=True)
        old = original.read_bytes()
        original_pdf = service._certificate_storage_path(source.storage_key_pdf).read_bytes()
        item = self.later()
        assert self.run_worker()['prepared'] == 1
        target = self.target(item)
        target_path = service._certificate_storage_path(target.storage_key_docx)
        assert not word.certificate_docx_needs_layout_update(target_path)
        assert attachments.picture_facts(target_path) == attachments.picture_facts(original)
        third = self.later(IdDocumento='301', IdRigaDoc='3', DDT='2601-10/11/2026')
        plan = reuse.plan_item(self.db, third)
        assert plan['action'] == 'reuse', plan.get('reason')
        assert original.read_bytes() == old
        assert service._certificate_storage_path(source.storage_key_pdf).read_bytes() == original_pdf

    def test_unpublished_height_edit_is_still_rejected_by_raw_integrity_check(self):
        _, source = self.base_word(closed=False)
        self.publish(source)
        path = service._certificate_storage_path(source.storage_key_docx)
        rewrite_headers(path, old_geometry)
        assert refs.integrity_reason(source) == 'reference_file_changed'
        before = path.read_bytes()
        assert service._sync_word_fields_for_download(self.db, certificate=source, path=path) == path
        assert path.read_bytes() == before

    def test_old_closed_source_and_new_copy_do_not_conflict_for_third_ddt(self):
        _, source = self.base_word(closed=True)
        original = service._certificate_storage_path(source.storage_key_docx)
        rewrite_headers(original, old_geometry)
        before_word = original.read_bytes()
        item = self.later()
        assert reuse.plan_item(self.db, item)['action'] == 'reuse'
        assert self.run_worker()['prepared'] == 1
        assert_heights(service._certificate_storage_path(self.target(item).storage_key_docx))
        third = self.later(IdDocumento='300', IdRigaDoc='3', DDT='2600-10/11/2026')
        plan = reuse.plan_item(self.db, third)
        assert plan['action'] == 'reuse', plan.get('reason')
        assert original.read_bytes() == before_word
        assert source.status == 'pdf_final'

    def test_open_reference_upgrade_is_tracked_copy_once_not_technical_regeneration(self):
        _, source = self.base_word(closed=False)
        self.upload(source, text='MANUAL SECOND PAGE MUST REMAIN')
        with patch.object(service, '_build_standard_conformity', return_value=('conforme', [])):
            service._sync_word_fields_for_download(self.db, certificate=source,
                path=service._certificate_storage_path(source.storage_key_docx))
        original = service._certificate_storage_path(source.storage_key_docx)
        rewrite_headers(original, old_geometry)
        self.publish(source)
        before_hash = reuse.file_hash(source.storage_key_docx)
        before_meta = deepcopy(refs.metadata(source))
        identity = (source.id, source.certificate_number, source.quantita, source.ddt, source.certified_by_user_id, source.quality_manager_user_id)
        with patch.object(service, '_build_standard_conformity', return_value=('conforme', [])), patch.object(service, '_docx_needs_content_control_update', return_value=False), patch.object(service, '_rebuild_generated_certificate_word', side_effect=AssertionError('must not rebuild')):
            path = service._sync_word_fields_for_download(self.db, certificate=source, path=original)
            assert path != original
            assert_heights(path)
            assert (source.id, source.certificate_number, source.quantita, source.ddt, source.certified_by_user_id, source.quality_manager_user_id) == identity
            assert refs.metadata(source)['revision'] == before_meta['revision']
            assert refs.integrity_reason(source) is None
            current_key = source.storage_key_docx
            assert service._sync_word_fields_for_download(self.db, certificate=source, path=path) == path
            assert source.storage_key_docx == current_key
        import hashlib
        assert hashlib.sha256(original.read_bytes()).hexdigest() == before_hash
        assert parts(path)['word/document.xml'] == parts(original)['word/document.xml']
        assert parts(path)['word/footer1.xml'] == parts(original)['word/footer1.xml']
        assert reuse.plan_item(self.db, self.later())['action'] == 'reuse'

    def test_reused_open_copy_upgrade_does_not_modify_reference_or_break_integrity(self):
        _, source = self.base_word(closed=False)
        self.publish(source)
        item = self.later()
        self.run_worker()
        target = self.target(item)
        original = service._certificate_storage_path(target.storage_key_docx)
        rewrite_headers(original, old_geometry)
        refs.mark_copy(target, source)
        self.db.commit()
        source_hash = reuse.file_hash(source.storage_key_docx)
        revision = refs.metadata(target)['revision']
        with patch.object(service, '_build_standard_conformity', return_value=('conforme', [])):
            path = service._sync_word_fields_for_download(self.db, certificate=target, path=original)
        assert path != original
        assert_heights(path)
        assert refs.integrity_reason(target) is None
        assert refs.metadata(target)['revision'] == revision
        assert reuse.file_hash(source.storage_key_docx) == source_hash

    def test_closed_pdf_and_its_word_are_never_reformatted(self):
        _, source = self.base_word(closed=True)
        path = service._certificate_storage_path(source.storage_key_docx)
        rewrite_headers(path, old_geometry)
        before_word = path.read_bytes()
        before_pdf = service._certificate_storage_path(source.storage_key_pdf).read_bytes()
        assert service._sync_word_fields_for_download(self.db, certificate=source, path=path) == path
        assert path.read_bytes() == before_word
        assert service._certificate_storage_path(source.storage_key_pdf).read_bytes() == before_pdf


for parent in (lifecycle.WordLifecycleTest, *lifecycle.WordLifecycleTest.__mro__[1:]):
    for name in parent.__dict__:
        if name.startswith('test_') and name not in HeaderHeightLifecycleTest.__dict__:
            setattr(HeaderHeightLifecycleTest, name, None)


@unittest.skipUnless(os.environ.get('DDT_TEST_POSTGRES_URL'), 'isolated PostgreSQL URL not supplied')
class HeaderHeightPostgresTest(HeaderHeightLifecycleTest):
    setUp = reuse_tests.DdtWordReusePostgresTest.setUp
