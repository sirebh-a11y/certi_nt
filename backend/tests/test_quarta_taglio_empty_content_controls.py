"""Anticipated Word shipment controls can legitimately have no runs/text yet."""
import unittest
import xml.etree.ElementTree as ET

from app.modules.quarta_taglio.certificate_docx import _replace_content_control_text

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}


class EmptyContentControlTests(unittest.TestCase):
    def wrap(self, content, properties='<w:text/>'):
        return ('<w:hdr xmlns:w="' + NS['w'] + '"><w:p><w:r><w:t>Label unchanged</w:t></w:r>'
                '<w:sdt><w:sdtPr><w:tag w:val="DDT_RAW"/>' + properties + '</w:sdtPr>'
                + content + '</w:sdt><w:r><w:t>After unchanged</w:t></w:r></w:p></w:hdr>')

    def test_empty_forms_fill_exactly_and_remain_editable(self):
        for content in (
            '<w:sdtContent/>', '<w:sdtContent />', '<w:sdtContent></w:sdtContent>',
            '<w:sdtContent> </w:sdtContent>', '<w:sdtContent><w:r/></w:sdtContent>',
            '<w:sdtContent><w:r></w:r></w:sdtContent>',
            '<w:sdtContent><w:r><w:rPr><w:sz w:val="18"/></w:rPr></w:r></w:sdtContent>',
            '<w:sdtContent><w:r><w:t/></w:r></w:sdtContent>',
            '<w:sdtContent><w:r><w:t xml:space="preserve"/></w:r></w:sdtContent>',
            '<w:sdtContent><w:r><w:t></w:t></w:r></w:sdtContent>',
        ):
            with self.subTest(content=content):
                before = self.wrap(content)
                after, changed = _replace_content_control_text(before, 'DDT_RAW', '2626 & <next>')
                self.assertTrue(changed)
                root = ET.fromstring(after)
                self.assertEqual(''.join(root.find('.//w:sdtContent', NS).itertext()), '2626 & <next>')
                self.assertEqual([t.text for t in root.findall('./w:p/w:r/w:t', NS)],
                                 ['Label unchanged', 'After unchanged'])
                self.assertIn('<w:tag w:val="DDT_RAW"/>', after)
                again, changed = _replace_content_control_text(after, 'DDT_RAW', 'NEXT DELIVERY')
                self.assertTrue(changed)
                self.assertEqual(''.join(ET.fromstring(again).find('.//w:sdtContent', NS).itertext()), 'NEXT DELIVERY')

    def test_default_and_existing_run_formatting_are_preserved(self):
        style = '<w:rPr><w:b/><w:sz w:val="18"/></w:rPr>'
        xml = self.wrap('<w:sdtContent/>', '<w:text/>' + style)
        after, changed = _replace_content_control_text(xml, 'DDT_RAW', '2626')
        self.assertTrue(changed)
        self.assertIn('<w:sdtContent><w:r>' + style, after)
        xml = self.wrap('<w:sdtContent><w:r w:rsidR="ABCD">' + style + '</w:r></w:sdtContent>')
        after, changed = _replace_content_control_text(xml, 'DDT_RAW', '2626')
        self.assertTrue(changed)
        self.assertIn('<w:r w:rsidR="ABCD">' + style, after)

    def test_missing_run_uses_generator_blue_table_style_not_label_style(self):
        for content in ('<w:sdtContent/>', '<w:sdtContent><w:r/></w:sdtContent>',
                        '<w:sdtContent><w:r></w:r></w:sdtContent>'):
            with self.subTest(content=content):
                after, _ = _replace_content_control_text(self.wrap(content), 'DDT_RAW', '2626')
                run = ET.fromstring(after).find('.//w:sdtContent/w:r', NS)
                self.assertEqual(run.find('w:rPr/w:color', NS).get('{' + NS['w'] + '}val'), '0070C0')
                self.assertEqual(run.find('w:rPr/w:rFonts', NS).get('{' + NS['w'] + '}ascii'), 'Times New Roman')
                self.assertEqual(run.find('w:rPr/w:sz', NS).get('{' + NS['w'] + '}val'), '20')

    def test_empty_value_and_missing_tags_do_not_take_neighbouring_text(self):
        xml = self.wrap('<w:sdtContent/>')
        after, changed = _replace_content_control_text(xml, 'DDT_RAW', '')
        self.assertIn('Label unchanged</w:t>', after)
        self.assertTrue(changed)
        self.assertEqual(''.join(ET.fromstring(after).find('.//w:sdtContent', NS).itertext()), '')
        self.assertEqual(_replace_content_control_text(xml, 'NOT_PRESENT', 'no'), (xml, False))

    def test_non_plain_or_non_empty_structure_is_not_reconstructed(self):
        for content, props in (
            ('<w:sdtContent/>', '<w:date/>'),
            ('<w:sdtContent/>', ''),
            ('<w:sdtContent><w:r><w:drawing/></w:r></w:sdtContent>', '<w:text/>'),
            ('<w:sdtContent><w:p/></w:sdtContent>', '<w:text/>'),
            ('<w:sdtContent><w:r><w:br/></w:r></w:sdtContent>', '<w:text/>'),
        ):
            with self.subTest(content=content, props=props):
                xml = self.wrap(content, props)
                self.assertEqual(_replace_content_control_text(xml, 'DDT_RAW', '2626'), (xml, False))

    def test_duplicate_controls_all_receive_the_value(self):
        xml = self.wrap('<w:sdtContent/>')
        control = xml[xml.index('<w:sdt>'):xml.index('</w:sdt>') + len('</w:sdt>')]
        xml = xml.replace('</w:p>', control + '</w:p>')
        after, changed = _replace_content_control_text(xml, 'DDT_RAW', '2626')
        self.assertTrue(changed)
        self.assertEqual([''.join(n.itertext()) for n in ET.fromstring(after).findall('.//w:sdtContent', NS)], ['2626', '2626'])
