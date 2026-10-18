"""Pure compatibility checks: no database, documents, or external connections."""
import unittest
from types import SimpleNamespace

from app.modules.quarta_taglio.ddt_word_reuse import _compatible_materials, _equivalent_source


class ReuseCompatibilityTest(unittest.TestCase):
    def material(self, lots=None, **changes):
        return dict(dict(cdq='CDQ1', colata='HEAT1', cod_art='001230',
                         lotti=['L1', 'L2'] if lots is None else lots), **changes)

    def test_same_lots_reordered_or_repeated_are_compatible(self):
        self.assertTrue(_compatible_materials([self.material()], [self.material(['L2', 'L1', 'L1'])]))

    def test_additional_lots_of_identical_material_are_compatible(self):
        self.assertTrue(_compatible_materials([self.material()], [self.material(['L1', 'L2', 'L3'])]))

    def test_removed_or_replaced_lots_are_not_compatible(self):
        for lots in [['L1'], ['L1', 'L3'], []]:
            with self.subTest(lots=lots):
                self.assertFalse(_compatible_materials([self.material()], [self.material(lots)]))

    def test_no_inference_from_missing_lot_evidence(self):
        self.assertTrue(_compatible_materials([self.material([])], [self.material([])]))
        self.assertFalse(_compatible_materials([self.material([])], [self.material(['L1'])]))

    def test_changed_certificate_heat_article_each_blocks(self):
        for field in ['cdq', 'colata', 'cod_art']:
            with self.subTest(field=field):
                self.assertFalse(_compatible_materials([self.material()], [self.material(**{field:'OTHER'})]))

    def test_added_or_removed_material_blocks(self):
        a,b=self.material(),self.material(cdq='CDQ2')
        self.assertFalse(_compatible_materials([a], [a,b]))
        self.assertFalse(_compatible_materials([a,b], [a]))

    def test_multiple_materials_lot_growth_requires_weighted_chemistry_review(self):
        a, b = self.material(), self.material(cdq='CDQ2')
        self.assertFalse(_compatible_materials(
            [a, b], [self.material(['L1', 'L2', 'L3']), b]))

    def test_multiple_materials_unchanged_lots_remain_compatible(self):
        a, b = self.material(), self.material(cdq='CDQ2')
        self.assertTrue(_compatible_materials([a, b], [b, a]))

    def test_incomplete_malformed_or_duplicate_material_blocks(self):
        for values in [None, [], [None], [self.material(lotti=None)], [self.material(lotti='L1,L2')],
                       [self.material([''])], [self.material([1])], [self.material(cdq='')],
                       [self.material(),self.material()]]:
            with self.subTest(values=values):
                self.assertFalse(_compatible_materials(values, [self.material()]))

    def candidate(self, id, operator=None, manager=None):
        return (SimpleNamespace(id=id,certified_by_user_id=operator,quality_manager_user_id=manager), {}, [])

    def test_missing_legacy_references_select_complete_equivalent_not_oldest(self):
        legacy,good=self.candidate(1),self.candidate(2,4,3)
        self.assertIs(_equivalent_source([legacy,good]),good)
        self.assertIsNone(legacy[0].certified_by_user_id)

    def test_partial_reference_can_agree_with_complete_source(self):
        partial,good=self.candidate(1,4),self.candidate(2,4,3)
        self.assertIs(_equivalent_source([partial,good]),good)

    def test_conflicting_known_operator_or_manager_is_never_ignored(self):
        for other in [self.candidate(2,9,3),self.candidate(2,4,9)]:
            self.assertIsNone(_equivalent_source([self.candidate(1,4,3),other]))

    def test_do_not_assemble_signers_from_two_incomplete_records(self):
        self.assertIsNone(_equivalent_source([self.candidate(1,4),self.candidate(2,None,3)]))

    def test_old_equivalent_sources_and_all_unknown_keep_deterministic_choice(self):
        for operator,manager in [(4,3),(None,None)]:
            old,new=self.candidate(1,operator,manager),self.candidate(2,operator,manager)
            self.assertIs(_equivalent_source([new,old]),old)
