"""DMG source fidelity, routing scale, and bounded-history isolation regressions.

These tests never contact providers. A schema-valid fixture is not an actual opinion.
"""
from __future__ import annotations

from copy import deepcopy
from itertools import combinations
import json
import random
import re
import unittest
from unittest.mock import patch

from support import ROOT, SourceCopy, project, runtime as rt
from test_deliberation import ENV, RuntimeFixture, response, reply

SOURCE_SHA256 = 'f9efb432e8234f84d209de759dc0fd89b4685f65e2ed6a3f54a9bd716fba6327'


class SourceFidelityTests(SourceCopy):
    def test_source_table_is_the_exact_four_column_table(self):
        raw = (self.root / rt.SOURCE_PATH).read_bytes()
        self.assertEqual(rt.SOURCE_PATH, 'sources/hikmah.md')
        self.assertEqual(rt.digest(raw), SOURCE_SHA256)
        lines = raw.decode('utf-8').splitlines()
        self.assertEqual(len(lines), 101)
        self.assertEqual(lines[:2], ['| No. | DMG | Meaning | Vision core |', '|---:|---|---|---|'])
        self.assertEqual(rt.SOURCE_FIELDS, ('number', 'dmg', 'meaning', 'vision_core'))
        config, _ = rt.resources(self.root)
        rt.validate_source(config, raw)

    def test_wrong_header_is_rejected_and_no_legacy_identity_remains(self):
        config, _ = rt.resources(self.root)
        raw = (self.root / rt.SOURCE_PATH).read_bytes()
        for header in (b'| No. | DMG transliteration | Meaning | Vision core |', b'| No. | DMG | Meaning |'):
            with self.subTest(header=header), self.assertRaisesRegex(rt.HikmahError, 'No., DMG, Meaning, Vision core'):
                rt.validate_source(config, raw.replace(b'| No. | DMG | Meaning | Vision core |', header, 1))
        # Product identifiers are hikmah everywhere. Capitalized references to God in the
        # religious-boundary rules are intentional and are not product identifiers.
        old = 'al' + 'lah'  # split so this guard does not match itself
        retired = re.compile('|'.join((old, old.upper(), old.title() + 'Error', 'atom' + '_en')).encode())
        tree = {**project.source_inputs(self.root), **project.repository_inputs(self.root)}
        for name, data in tree.items():
            self.assertIsNone(retired.search(data), name)
            self.assertIsNone(retired.search(name.encode()), name)

    def test_all_four_fields_of_every_row_match_the_source(self):
        config, personas = rt.resources(self.root)
        lines = (self.root / rt.SOURCE_PATH).read_text(encoding='utf-8').splitlines()
        for number, line in enumerate(lines[2:], 1):
            ref = config['references'][f'ref-dmg-{number:03}']
            fields = [v.strip() for v in line.strip('|').split('|')]
            self.assertEqual(ref['record'], dict(zip(rt.SOURCE_FIELDS, fields)))
            self.assertEqual(ref['row_sha256'], rt.digest(line.encode('utf-8')))
            self.assertEqual(ref['source_sha256'], SOURCE_SHA256)
            self.assertEqual((ref['path'], len(fields)), ('sources/hikmah.md', 4))
            self.assertEqual(ref['line_number'], number + 2)
            meta = rt.persona_metadata(personas[f'dmg-{number:03}'], f'dmg-{number:03}', config)
            self.assertEqual(meta['name'], fields[1])

    def test_similar_labels_are_distinct_not_normalized_or_merged(self):
        config, personas = rt.resources(self.root)
        names = {m: rt.persona_metadata(raw, m, config)['name'] for m, raw in personas.items()}
        for member, label in {'dmg-048': 'al-Maǧīd', 'dmg-065': 'al-Māǧid',
                              'dmg-055': 'al-Waliyy', 'dmg-077': 'al-Wālī',
                              'dmg-085': 'Ḏū l-ǧalāl wa-l-ikrām', 'dmg-099': 'aṣ-Ṣabūr'}.items():
            self.assertEqual(names[member], label)
        self.assertEqual(len(set(names.values())), 99)

    def test_source_byte_edits_fail_before_synchronization_writes(self):
        self.append(rt.SOURCE_PATH, '\n')
        before = {p.name: p.read_bytes() for p in (self.root / 'personas').glob('*.md')}
        with self.assertRaises(rt.HikmahError):
            project.sync_personas(self.root)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.root / 'personas').glob('*.md')})
        with self.assertRaises(project.ProjectError):
            project.validate(self.root)

    def test_source_row_order_and_malformed_utf8_rejected(self):
        config, _ = rt.resources(self.root)
        original = (self.root / rt.SOURCE_PATH).read_bytes()
        lines = original.splitlines(keepends=True)
        lines[2], lines[3] = lines[3], lines[2]
        for raw in (b''.join(lines), original + b'\xff', b'not a table', original[:-100]):
            with self.subTest(size=len(raw)), self.assertRaises(rt.HikmahError):
                rt.validate_source(config, raw)

    def test_forged_source_record_cannot_keep_an_original_hash(self):
        self.edit_json('config/panels.json', lambda c: c['references']['ref-dmg-019']['record'].update(
            meaning='A silently invented interpretation.'))
        with self.assertRaisesRegex(project.ProjectError, 'source record differs'):
            project.validate(self.root)

    def test_inconsistent_source_hashes_are_not_independent_sources(self):
        config, _ = rt.resources(self.root)
        config['references']['ref-dmg-019']['source_sha256'] = 'a' * 64
        with self.assertRaisesRegex(rt.HikmahError, 'same source bytes'):
            rt.validate_config(config)

    def test_missing_or_extra_source_rows_are_rejected(self):
        config, _ = rt.resources(self.root)
        del config['references']['ref-dmg-099']
        with self.assertRaisesRegex(rt.HikmahError, 'every supplied DMG row'):
            rt.validate_config(config)
        config, _ = rt.resources(self.root)
        config['references']['ref-dmg-100'] = {**config['references']['ref-dmg-099'], 'row_number': 100}
        with self.assertRaisesRegex(rt.HikmahError, 'source row number'):
            rt.validate_config(config)

    def test_source_directory_symlink_cannot_bypass_package_validation(self):
        original = self.root / 'sources'
        held = self.root / 'held-source'
        original.rename(held)
        self.symlink(original, held, directory=True)
        with self.assertRaises(project.ProjectError):
            project.validate(self.root)

    def test_runtime_rejects_resource_directory_symlinks_before_reading_bytes(self):
        for folder in ('sources', 'personas', 'config'):
            with self.subTest(folder=folder):
                path = self.root / folder
                held = self.root / ('held-' + folder)
                path.rename(held)
                self.symlink(path, held, directory=True)
                try:
                    with patch.object(rt, 'load_file', side_effect=AssertionError('must reject before reading')):
                        with self.assertRaisesRegex(rt.HikmahError, 'non-symlink directory'):
                            rt.resources(self.root)
                finally:
                    path.unlink()
                    held.rename(path)

    def test_runtime_rejects_symlink_resource_root(self):
        link = self.root.parent / 'resource-alias'
        self.symlink(link, self.root, directory=True)
        with self.assertRaisesRegex(rt.HikmahError, 'non-symlink directory'):
            rt.resources(link)

    def test_profile_cannot_borrow_a_neighbor_source_or_change_display_label(self):
        config, personas = rt.resources(self.root)
        for raw in (personas['dmg-019'].replace('reference_ids: ["ref-dmg-019"]',
                                              'reference_ids: ["ref-dmg-020"]'),
                    personas['dmg-019'].replace('name: "al-ʿAlīm"', 'name: "guessed-ascii"')):
            with self.assertRaises(rt.HikmahError):
                rt.persona_metadata(raw, 'dmg-019', config)

    def test_original_source_embedded_in_both_standalone_plugins(self):
        meta, inputs = project.validate(self.root)
        for host in project.HOSTS:
            packaged = project.package_files(host, meta, inputs)
            source = packaged['skills/hikmah/references/sources/hikmah.md']
            self.assertEqual(rt.digest(source), SOURCE_SHA256)
            self.assertEqual(source, inputs[rt.SOURCE_PATH])
            info = json.loads(packaged['skills/hikmah/references/build.json'])
            self.assertEqual(info['source_group_count'], 1)
            self.assertEqual(info['persona_count'], 99)

    def test_catalog_and_method_limits_are_explicit_in_every_profile(self):
        config, personas = rt.resources(self.root)
        for member, raw in personas.items():
            core, _ = rt.split_persona_catalog(raw)
            self.assertIn('editorial', core)
            self.assertIn('not Allah', core)
            self.assertIn('supplied labels, not measured effects, causal proof, or project evidence', core)
            self.assertIn('not decision evidence', core)
            self.assertEqual(rt.persona_metadata(raw, member, config)['reference_ids'], ['ref-' + member])


class ScalableRoutingTests(unittest.TestCase):
    def test_small_graphs_match_an_exhaustive_cut_and_balance_oracle(self):
        rng = random.Random(741)
        for n in range(2, 10):
            members = [f'n-{i:02}' for i in range(n)]
            for _ in range(5):
                edges = [list(e) for e in combinations(members, 2) if rng.random() < .4]
                plan = rt.route(members, ['openai', 'anthropic'], edges)
                indexed = [(members.index(a), members.index(b)) for a, b in edges]
                oracle = max((sum(((mask >> a) ^ (mask >> b)) & 1 for a, b in indexed),
                              -abs(n - 2 * mask.bit_count())) for mask in range(1 << n))
                actual = (plan['separated_pairs'], -abs(plan['provider_load']['openai'] - plan['provider_load']['anthropic']))
                self.assertEqual(actual, oracle)
                self.assertTrue(plan['routing_optimal'])

    def test_all_99_supplied_lenses_have_exact_full_separation(self):
        config, _ = rt.resources()
        plan = rt.route(config['members'], ['anthropic', 'openai'], rt.polarity_edges(config))
        self.assertEqual(plan['routing_algorithm'], 'exact-bipartite-dp')
        self.assertTrue(plan['routing_optimal'])
        self.assertEqual(plan['separated_pairs'], 50)
        self.assertEqual(plan['unseparated_pairs'], [])
        self.assertEqual(plan['provider_load'], {'anthropic': 50, 'openai': 49})
        self.assertEqual(plan['seats'][-1]['seat_id'], 'S99')

    def test_large_star_preserves_separation_over_balance(self):
        members = [f'n-{i:03}' for i in range(99)]
        plan = rt.route(members, ['anthropic', 'openai'], [[members[0], m] for m in members[1:]])
        self.assertEqual(plan['separated_pairs'], 98)
        self.assertEqual(sorted(plan['provider_load'].values()), [1, 98])
        self.assertTrue(plan['routing_optimal'])

    def test_large_disconnected_graph_orients_components_for_global_balance(self):
        members = [f'n-{i:03}' for i in range(99)]
        edges = [[members[i], members[i + j]] for i in range(0, 90, 5) for j in range(1, 5)]
        plan = rt.route(members, ['anthropic', 'openai'], edges)
        self.assertEqual(plan['separated_pairs'], len(edges))
        self.assertEqual(sorted(plan['provider_load'].values()), [49, 50])
        self.assertEqual(plan['routing_algorithm'], 'exact-bipartite-dp')

    def test_large_odd_cycle_uses_honestly_labeled_bounded_heuristic(self):
        members = [f'n-{i:03}' for i in range(99)]
        edges = [[members[i], members[(i + 1) % 99]] for i in range(99)]
        first = rt.route(members, ['anthropic', 'openai'], edges)
        second = rt.route(members, ['openai', 'anthropic'], list(reversed(edges)))
        self.assertEqual(first, second)
        self.assertEqual(first['routing_algorithm'], 'bounded-local-search')
        self.assertFalse(first['routing_optimal'])
        self.assertGreaterEqual(len(first['unseparated_pairs']), 1)
        self.assertLessEqual(first['separated_pairs'], 98)

    def test_isolated_large_graph_is_balanced_without_invented_tensions(self):
        members = [f'n-{i:03}' for i in range(99)]
        plan = rt.route(members, ['anthropic', 'openai'], [])
        self.assertEqual(sorted(plan['provider_load'].values()), [49, 50])
        self.assertEqual(plan['active_polarity_pairs'], [])
        self.assertEqual(plan['separated_pairs'], 0)

    def test_more_than_99_seats_or_review_rows_are_rejected(self):
        with self.assertRaises(rt.HikmahError):
            rt.route([f'n-{i}' for i in range(100)], ['openai'], [])
        with self.assertRaises(rt.HikmahError):
            rt.maximum_review_matching([[0] * 100 for _ in range(100)])


class ProductAndViewTests(RuntimeFixture):
    def capture(self, *, members=None):
        seen = []
        def caller(provider, req):
            seen.append(deepcopy(req))
            return reply(req)
        return seen, self.execute(caller, members=members)

    def test_another_product_catalog_cannot_enter_this_runtime(self):
        changed = deepcopy(self.config)
        changed['product'] = 'other-project'
        with self.assertRaisesRegex(rt.HikmahError, 'another product'):
            rt.validate_config(changed)

    def test_contributions_require_exact_product_identity(self):
        for other in ('other-project', 'Hikmah', None, True):
            value = response(self.initial)
            value['product'] = other
            with self.assertRaisesRegex(rt.HikmahError, 'product'):
                rt.validate_contribution(value, self.initial)
        value = response(self.initial)
        del value['product']
        with self.assertRaises(rt.HikmahError):
            rt.validate_contribution(value, self.initial)

    def test_foreign_product_prior_position_is_rejected(self):
        _, packet = self.capture()
        history = deepcopy(packet['rounds'][:1])
        history[0]['results'][1]['response']['product'] = 'other-project'
        assignment = next(a for a in packet['plan']['review_assignments'] if a['reviewer_seat'] == 'S01')
        with self.assertRaisesRegex(rt.HikmahError, 'stale'):
            rt.compile_request(self.brief, self.seat, self.personas[self.seat['member']], 'test-run', 2,
                               history, config=self.config, review_assignment=assignment)

    def test_first_view_has_no_peer_roots_relations_or_foreign_references(self):
        self.assertEqual(self.initial['peer_snapshot_roots'], [])
        self.assertEqual(self.initial['peer_rounds'], [])
        self.assertEqual([r['id'] for r in self.initial['method_references']], ['ref-dmg-019'])
        self.assertNotIn(rt.CATALOG_START, self.initial['persona'])
        self.assertNotIn('## Relations', self.initial['persona'])
        self.assertIsNone(self.initial['review_assignment'])
        self.assertNotIn('relations', self.initial)

    def test_scoped_views_reference_complete_frozen_snapshot_roots(self):
        seen, packet = self.capture(members=self.config['profiles']['decision']['members'])
        self.assertEqual(packet['status'], 'rounds-complete')
        for req in seen:
            number = req['expected_metadata']['round']
            self.assertEqual(req['peer_context_policy'], rt.PEER_CONTEXT_POLICY[number])
            self.assertEqual(req['peer_context_policy'], 'peer-blind' if number == 1 else 'assigned-review-neighborhood')
            self.assertEqual(len(req['peer_snapshot_roots']), number - 1)
            for root, view in zip(req['peer_snapshot_roots'], req['peer_rounds']):
                history = packet['rounds'][root['round'] - 1]
                full = {'round': history['round'], 'positions': [r['response'] for r in history['results'] if r['status'] == 'ok']}
                self.assertEqual(root['sha256'], rt.digest(rt.json_bytes(full)))
                self.assertEqual(root['available_positions'], 6)
                self.assertTrue(all(p in full['positions'] for p in view['positions']))
                self.assertLessEqual(len(view['positions']), 3)
            self.assertLessEqual(len(rt.json_bytes(req)), rt.MAX_REQUEST_BYTES)

    def test_round_two_view_is_exactly_self_and_assigned_target(self):
        seen, _ = self.capture(members=self.config['profiles']['decision']['members'])
        for req in seen:
            if req['expected_metadata']['round'] != 2:
                continue
            expected = {req['expected_metadata']['seat_id'], req['review_assignment']['target_seat']}
            self.assertEqual({p['seat_id'] for p in req['peer_rounds'][0]['positions']}, expected)

    def test_round_three_view_is_own_incoming_and_outgoing_neighborhood(self):
        seen, packet = self.capture(members=self.config['profiles']['decision']['members'])
        assignments = {a['reviewer_seat']: a for a in packet['plan']['review_assignments']}
        for req in seen:
            if req['expected_metadata']['round'] != 3:
                continue
            sid = req['expected_metadata']['seat_id']
            reviewers = {c['reviewer_seat'] for c in req['incoming_challenges']}
            self.assertEqual(len(reviewers), 1)
            # Round 1 view: own, reviewer, and reviewed target. Round 2 view: own and reviewer only;
            # the target's own challenge quotes a further seat and is not this seat's task.
            first, second = req['peer_rounds']
            self.assertEqual({p['seat_id'] for p in first['positions']}, {sid, assignments[sid]['target_seat'], *reviewers})
            self.assertEqual({p['seat_id'] for p in second['positions']}, {sid, *reviewers})
            self.assertEqual({p['challenge']['target_seat'] for p in second['positions']}, {sid, assignments[sid]['target_seat']})

    def test_round_three_request_names_only_its_three_seat_neighborhood_in_a_four_cycle(self):
        # These four lenses share no catalog relation and agree in the fixture, so the deterministic
        # matching forms one four-cycle: the case where a target's own challenge would name a fourth seat.
        seen, packet = self.capture(members=['dmg-001', 'dmg-003', 'dmg-004', 'dmg-005'])
        self.assertEqual(packet['status'], 'rounds-complete')
        following = {a['reviewer_seat']: a['target_seat'] for a in packet['plan']['review_assignments']}
        cycle, seat = [], 'S01'
        while seat not in cycle:
            cycle.append(seat)
            seat = following[seat]
        self.assertEqual(len(cycle), 4)
        for req in seen:
            if req['expected_metadata']['round'] != 3:
                continue
            sid = req['expected_metadata']['seat_id']
            neighborhood = {sid, following[sid], *[c['reviewer_seat'] for c in req['incoming_challenges']]}
            self.assertEqual(len(neighborhood), 3)
            self.assertEqual(set(re.findall(r'\bS[0-9]{2}\b', json.dumps(req))), neighborhood)

    def test_snapshot_roots_and_context_policy_are_request_bound(self):
        seen, _ = self.capture()
        req = next(r for r in seen if r['expected_metadata']['round'] == 2)
        for alter in (lambda r: r['peer_snapshot_roots'][0].update(sha256='0' * 64),
                      lambda r: r.update(peer_context_policy='silently-show-all')):
            changed = deepcopy(req)
            alter(changed)
            with self.assertRaisesRegex(rt.HikmahError, 'changed after sealing'):
                rt.validate_contribution(response(req), changed)

    def test_out_of_view_dissent_remains_in_complete_packet(self):
        seen = []
        concern = 'A low-frequency irreversible downside is unresolved.'
        def caller(provider, req):
            seen.append(deepcopy(req))
            return reply(req, dissent=[concern] if req['expected_metadata']['seat_id'] == 'S01' else [])
        packet = self.execute(caller, members=self.config['profiles']['decision']['members'])
        views_without = [r for r in seen if r['expected_metadata']['round'] == 2
                         and 'S01' not in {p['seat_id'] for p in r['peer_rounds'][0]['positions']}]
        self.assertTrue(views_without)
        self.assertTrue(any(concern in item['dissent'] for item in packet['unresolved']))
        self.assertEqual(len(packet['challenge_ledger']), 6)
        self.assertEqual(packet['method_source_coverage'], {'scope': 'persona-method-provenance', 'source_groups': ['user-table-001'], 'underlying_source_count': 1})
        self.assertIsNone(packet['verdict'])

    def test_decision_evidence_cannot_reuse_the_method_reference_namespace(self):
        for identifier in ('ref-dmg-019', 'ref-anything'):
            brief = deepcopy(self.brief)
            brief['evidence'][0]['id'] = identifier
            with self.assertRaisesRegex(rt.HikmahError, 'reserved method-reference namespace'):
                rt.validate_brief(brief)

    def test_full_catalog_requires_explicit_billable_budget_before_any_request(self):
        with patch.object(rt, 'request_api') as api:
            with self.assertRaisesRegex(rt.HikmahError, 'call budget'):
                rt.run_api(self.brief, self.config['members'], self.config, self.personas,
                           ['anthropic', 'openai'], allow_network=True, confirm_data_sharing=True, env=ENV)
            api.assert_not_called()

    def test_invalid_or_excessive_request_budgets_are_rejected(self):
        for budget in (True, 0, 8, 298, 10.5):
            with self.subTest(budget=budget), self.assertRaises(rt.HikmahError):
                self.execute(max_calls=budget)


if __name__ == '__main__':
    unittest.main()
