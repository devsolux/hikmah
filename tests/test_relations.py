"""Relation-aware review and source provenance: deterministic, offline regressions."""
from __future__ import annotations

from copy import deepcopy
from itertools import permutations
import json
import random
import unittest
from unittest.mock import patch

from support import ROOT, SourceCopy, project, runtime as rt
from test_deliberation import RuntimeFixture, response, reply


class CatalogTests(SourceCopy):
    def test_all_99_have_tension_complement_and_a_scoped_reference(self):
        config, personas = rt.resources(self.root)
        self.assertEqual(len(config['relations']), 109)
        self.assertEqual(len(rt.polarity_edges(config)), 50)
        self.assertEqual(len(config['references']), 99)
        for member, raw in personas.items():
            with self.subTest(member=member):
                meta = rt.validate_persona(raw, member, config)
                relations = [r for r in config['relations'] if member in r['members']]
                self.assertEqual({r['kind'] for r in relations}, {'tension', 'complement'})
                self.assertTrue(meta['reference_ids'])
                for rid in meta['reference_ids']:
                    ref = config['references'][rid]
                    self.assertTrue(ref['supports'])
                    self.assertTrue(ref['limitations'])
                    self.assertTrue(ref['reviewed_scope'])
                    self.assertIn('../' + ref['path'], raw)
                    self.assertEqual(ref['source_group'], 'user-table-001')
                for relation in relations:
                    peer = next(p for p in relation['members'] if p != member)
                    self.assertIn(f']({peer}.md)', raw)
                    self.assertIn(relation['checks'][member], raw)

    def test_identity_and_hosts_unchanged(self):
        meta, _ = project.validate(self.root)
        self.assertEqual((meta['display_name'], meta['name'], meta['version']), ('Hikmah', 'hikmah', '1.0.0'))
        self.assertEqual(meta['supported_hosts'], ['claude', 'chatgpt'])
        self.assertEqual(set(p.name for p in (self.root / 'agents').iterdir()), {'hikmah.md'})

    def test_unknown_self_duplicate_and_asymmetric_relations_rejected(self):
        config, _ = rt.resources(self.root)
        mutations = (
            lambda r: r.update(members=['dmg-019', 'missing']),
            lambda r: r.update(members=['dmg-019', 'dmg-019']),
            lambda r: r.update(kind='opposes-everything'),
            lambda r: r.update(checks={'dmg-019': 'Incomplete direction.'}),
            lambda r: r.update(resolution_test=''),
        )
        for mutate in mutations:
            bad = deepcopy(config)
            mutate(bad['relations'][0])
            with self.assertRaises(rt.HikmahError):
                rt.validate_config(bad)
        for key in ('id', 'members'):
            bad = deepcopy(config)
            bad['relations'][1][key] = deepcopy(bad['relations'][0][key])
            with self.assertRaises(rt.HikmahError):
                rt.validate_config(bad)

    def test_isolated_persona_rejected(self):
        config, _ = rt.resources(self.root)
        config['relations'] = [r for r in config['relations'] if 'dmg-067' not in r['members']]
        with self.assertRaisesRegex(rt.HikmahError, 'every persona'):
            rt.validate_config(config)

    def test_old_polarity_source_and_boolean_config_version_rejected(self):
        config, _ = rt.resources(self.root)
        for mutation in ({'schema_version': 2}, {'schema_version': True}, {'polarity_pairs': []}):
            with self.assertRaises(rt.HikmahError):
                rt.validate_config({**config, **mutation})

    def test_bad_source_paths_hashes_scope_and_dates_rejected(self):
        config, _ = rt.resources(self.root)
        for mutation in ({'path': '../hikmah.md'}, {'path': 'https://example.org/source'},
                         {'source_group': 'fabricated-independent-work'}, {'source_sha256': 'bad'},
                         {'row_sha256': 'bad'}, {'line_number': True}, {'row_number': True},
                         {'reviewed_on': '2026-02-30'}, {'reviewed_on': '20261011'},
                         {'reviewed_scope': ''}, {'limitations': ''}, {'source_type': 'trust-the-name'}):
            bad = deepcopy(config)
            bad['references']['ref-dmg-019'].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(rt.HikmahError):
                rt.validate_config(bad)

    def test_duplicate_row_cannot_be_relabelled_as_another_source(self):
        config, _ = rt.resources(self.root)
        config['references']['ref-dmg-020'] = deepcopy(config['references']['ref-dmg-019'])
        with self.assertRaisesRegex(rt.HikmahError, 'reference ID must identify its source row'):
            rt.validate_config(config)

    def test_unknown_empty_and_duplicate_persona_reference_bindings_rejected(self):
        config, personas = rt.resources(self.root)
        for ids in ([], ['missing'], ['ref-dmg-019', 'ref-dmg-019']):
            raw = personas['dmg-019'].replace('reference_ids: ["ref-dmg-019"]', 'reference_ids: ' + json.dumps(ids))
            with self.assertRaises(rt.HikmahError):
                rt.persona_metadata(raw, 'dmg-019', config)

    def test_unbound_registry_entry_rejected(self):
        def add(config):
            config['references']['ref-unbound'] = deepcopy(config['references']['ref-dmg-019'])
        self.edit_json('config/panels.json', add)
        with self.assertRaisesRegex(project.ProjectError, 'invalid DMG method reference ID'):
            project.validate(self.root)

    def test_one_example_source_and_authorship_limits_are_explicit(self):
        config, _ = rt.resources(self.root)
        for ref in config['references'].values():
            self.assertEqual(ref['source_type'], 'user-provided-table')
            self.assertEqual(ref['source_group'], 'user-table-001')
            self.assertEqual(ref['authors'], 'Not stated in the source table.')
            self.assertIn('editorial', ref['supports'].lower())
            self.assertIn('not', ref['limitations'].lower())
        self.assertEqual(len({r['source_sha256'] for r in config['references'].values()}), 1)

    def test_shared_frontmatter_parser_is_one_implementation(self):
        self.assertIs(project.parse_frontmatter, rt.parse_frontmatter)

    def test_packaged_refs_relations_schema_and_docs_match_source(self):
        meta, inputs = project.validate(self.root)
        for host in project.HOSTS:
            files = project.package_files(host, meta, inputs)
            self.assertEqual(files['skills/hikmah/references/panels.json'], inputs['config/panels.json'])
            self.assertEqual(files['skills/hikmah/references/DELIBERATION_LOGIC.md'], inputs['docs/DELIBERATION_LOGIC.md'])
            info = json.loads(files['skills/hikmah/references/build.json'])
            self.assertEqual(info['version'], '1.0.0')
            self.assertEqual(info['contribution_schema_version'], 1)
            self.assertEqual(json.loads(files['skills/hikmah/references/response-schema.json']), rt.response_schema())


class SynchronizationTests(SourceCopy):
    def test_sync_is_idempotent_and_offline(self):
        before = project.source_inputs(self.root)
        with patch.object(rt, 'post_json', side_effect=AssertionError('network forbidden')):
            self.assertEqual(project.sync_personas(self.root), [])
        self.assertEqual(project.source_inputs(self.root), before)
        self.assertFalse((self.root / 'dist').exists())

    def test_catalog_changes_are_detected_then_synchronized_without_rewriting_methods(self):
        before = {p.name: rt.split_persona_catalog(p.read_text(encoding='utf-8'))[0] for p in (self.root / 'personas').glob('*.md')}
        self.edit_json('config/panels.json', lambda c: c['relations'][0].update(question='Which observation would distinguish these claims?'))
        with self.assertRaisesRegex(project.ProjectError, 'stale persona'):
            project.validate(self.root)
        changed = project.sync_personas(self.root)
        self.assertEqual(set(changed), {'personas/dmg-001.md', 'personas/dmg-091.md'})
        # Refreshed personas still leave the committed public marketplace stale until synced.
        with self.assertRaisesRegex(project.ProjectError, 'sync-marketplace'):
            project.validate(self.root)
        self.assertIn('plugins/hikmah/skills/hikmah/references/personas/dmg-001.md', self.sync_marketplace())
        project.validate(self.root)
        for p in (self.root / 'personas').glob('*.md'):
            self.assertEqual(rt.split_persona_catalog(p.read_text(encoding='utf-8'))[0], before[p.name])

    def test_sync_preserves_user_authored_method_edits(self):
        p = self.root / 'personas/dmg-019.md'
        p.write_text(p.read_text(encoding='utf-8').replace('## Focus\n\n', '## Focus\n\nA project-specific, user-authored clarification.\n\n'), encoding='utf-8')
        core = rt.split_persona_catalog(p.read_text(encoding='utf-8'))[0]
        self.edit_json('config/panels.json', lambda c: c['references']['ref-dmg-019'].update(locator='Supplied row 19; explicit editorial locator refinement.'))
        self.assertEqual(project.sync_personas(self.root), ['personas/dmg-019.md'])
        self.assertEqual(rt.split_persona_catalog(p.read_text(encoding='utf-8'))[0], core)
        self.sync_marketplace()
        project.validate(self.root)

    def test_malformed_late_marker_prevents_all_writes(self):
        self.edit_json('config/panels.json', lambda c: c['references']['ref-dmg-019'].update(locator='Updated locator.'))
        p = self.root / 'personas/dmg-067.md'
        p.write_text(p.read_text(encoding='utf-8').replace(rt.CATALOG_END, ''), encoding='utf-8')
        before = project.source_inputs(self.root)
        with self.assertRaises(rt.HikmahError):
            project.sync_personas(self.root)
        self.assertEqual(project.source_inputs(self.root), before)
        self.assertFalse((self.root / project.LOCK).exists())

    def test_marker_duplication_reversal_and_trailing_text_rejected(self):
        config, personas = rt.resources(self.root)
        for raw in (personas['dmg-019'] + 'Unexpected tail.\n',
                    personas['dmg-019'].replace(rt.CATALOG_START, rt.CATALOG_START * 2),
                    personas['dmg-019'].replace(rt.CATALOG_START, 'TEMP').replace(rt.CATALOG_END, rt.CATALOG_START).replace('TEMP', rt.CATALOG_END)):
            with self.assertRaises(rt.HikmahError):
                rt.persona_metadata(raw, 'dmg-019', config)

    def test_generated_appendix_sentences_are_complete(self):
        config, personas = rt.resources(self.root)
        for member, raw in personas.items():
            _, appendix = rt.split_persona_catalog(raw)
            self.assertNotIn('actually used;', appendix, member)
            self.assertNotIn('..\n', appendix, member)
            self.assertNotIn('not historical', appendix, member)

    def test_sync_refuses_existing_lock(self):
        (self.root / project.LOCK).mkdir()
        with self.assertRaisesRegex(project.ProjectError, 'already exists'):
            project.sync_personas(self.root)
        self.assertTrue((self.root / project.LOCK).is_dir())

    def test_sync_does_not_follow_a_persona_symlink(self):
        target = self.root / 'personas/dmg-019.md'
        held = self.root / 'scratch'
        held.mkdir()
        target.rename(held / 'dmg-019.md')
        self.symlink(target, held / 'dmg-019.md')
        original = (held / 'dmg-019.md').read_bytes()
        with self.assertRaises(project.ProjectError):
            project.sync_personas(self.root)
        self.assertEqual((held / 'dmg-019.md').read_bytes(), original)

    def test_interrupted_sync_is_recoverable_and_never_truncates_methods(self):
        before = {p.name: rt.split_persona_catalog(p.read_text(encoding='utf-8'))[0] for p in (self.root / 'personas').glob('*.md')}
        self.edit_json('config/panels.json', lambda c: c['relations'][0].update(question='A refined shared review question.'))
        real_replace = project.os.replace
        attempts = []
        def interrupted(source, target):
            attempts.append(target)
            if len(attempts) == 2:
                raise OSError('Simulated interrupted synchronization.')
            return real_replace(source, target)
        with patch.object(project.os, 'replace', side_effect=interrupted), self.assertRaises(OSError):
            project.sync_personas(self.root)
        self.assertFalse((self.root / project.LOCK).exists())
        self.assertTrue(project.sync_personas(self.root))
        self.sync_marketplace()
        project.validate(self.root)
        for p in (self.root / 'personas').glob('*.md'):
            self.assertEqual(rt.split_persona_catalog(p.read_text(encoding='utf-8'))[0], before[p.name])


class MatchingTests(RuntimeFixture):
    def first_positions(self, members=None, stances=None):
        chosen = members or self.members
        seats = rt.route(chosen, ['openai'], rt.polarity_edges(self.config))['seats']
        results = []
        for index, seat in enumerate(seats):
            req = rt.compile_request(self.brief, seat, self.personas[seat['member']], 'test-run', 1, [], config=self.config)
            value = response(req, stance=(stances[index] if stances is not None else 'keep'))
            rt.validate_contribution(value, req)
            results.append({**seat, 'status': 'ok', 'response': value})
        return seats, {'round': 1, 'results': results}

    def test_maximum_matching_agrees_with_exhaustive_small_oracle(self):
        rng = random.Random(103)
        for n in range(2, 8):
            for _ in range(3):
                weights = [[rng.randrange(25) for _ in range(n)] for _ in range(n)]
                actual = rt.maximum_review_matching(weights)
                expected = max(sum(weights[i][j] for i, j in enumerate(order))
                               for order in permutations(range(n)) if all(i != j for i, j in enumerate(order)))
                self.assertEqual(sum(weights[i][j] for i, j in enumerate(actual)), expected)
                self.assertEqual(len(set(actual)), n)
                self.assertTrue(all(i != j for i, j in enumerate(actual)))

    def test_matching_rejects_bad_matrices_and_forbids_even_valuable_self_review(self):
        for matrix in ([], [[1]], [[1, 2], [3]], [[True, 0], [0, 0]], [[-1, 0], [0, 0]]):
            with self.assertRaises(rt.HikmahError):
                rt.maximum_review_matching(matrix)
        self.assertEqual(rt.maximum_review_matching([[1_000_000, 0], [0, 1_000_000]]), [1, 0])

    def test_balanced_review_for_duo_triad_larger_and_full_catalog(self):
        for n in (2, 3, 5, 18, 99):
            seats, first = self.first_positions(self.config['members'][:n])
            assignments = rt.assign_reviews(self.config, seats, first)
            expected = {s['seat_id'] for s in seats}
            self.assertEqual({a['reviewer_seat'] for a in assignments}, expected)
            self.assertEqual({a['target_seat'] for a in assignments}, expected)
            self.assertEqual(len(assignments), n)
            self.assertTrue(all(a['target_seat'] != a['reviewer_seat'] for a in assignments))

    def test_actual_option_contrast_precedes_static_relationship_preference(self):
        seats, first = self.first_positions(['dmg-019', 'dmg-094', 'dmg-046', 'dmg-076'], ['keep', 'keep', 'pilot', 'pilot'])
        assignments = rt.assign_reviews(self.config, seats, first)
        self.assertEqual(sum(a['option_contrast'] for a in assignments), 4)
        # Knowledge-boundary and practical-guidance lenses have a tension, but chose the same option here.
        self.assertFalse(any({a['reviewer_seat'], a['target_seat']} == {'S01', 'S02'} for a in assignments))

    def test_tension_then_complement_guide_same_option_assignments(self):
        seats, first = self.first_positions(['dmg-019', 'dmg-094', 'dmg-076'])
        assignments = rt.assign_reviews(self.config, seats, first)
        self.assertEqual(sum(a['relation_kind'] == 'tension' for a in assignments), 1)
        self.assertEqual(sum(a['relation_kind'] == 'complement' for a in assignments), 1)
        self.assertFalse(any(a['option_contrast'] for a in assignments))

    def test_unrelated_pair_gets_a_neutral_fallback_not_an_extra_persona(self):
        seats, first = self.first_positions(['dmg-046', 'dmg-094'])
        assignments = rt.assign_reviews(self.config, seats, first)
        self.assertEqual(len(assignments), 2)
        self.assertTrue(all(a['relation_id'] is None and a['relation_kind'] == 'general' for a in assignments))

    def test_abstention_is_not_labeled_option_contrast(self):
        seats, first = self.first_positions(['dmg-019', 'dmg-094'], [None, 'keep'])
        self.assertFalse(any(a['option_contrast'] for a in rt.assign_reviews(self.config, seats, first)))

    def test_failed_initial_seat_not_assigned_and_no_input_mutation(self):
        seats, first = self.first_positions()
        first['results'][0] = {**seats[0], 'status': 'invalid-response'}
        original = deepcopy((self.config, seats, first))
        assignments = rt.assign_reviews(self.config, seats, first)
        self.assertEqual(len(assignments), 2)
        self.assertTrue(all('S01' not in (a['reviewer_seat'], a['target_seat']) for a in assignments))
        self.assertEqual((self.config, seats, first), original)

    def test_matching_is_stable_under_input_order_changes(self):
        seats, first = self.first_positions(self.config['members'][:6])
        expected = rt.assign_reviews(self.config, seats, first)
        first['results'].reverse()
        self.assertEqual(rt.assign_reviews(self.config, list(reversed(seats)), first), expected)

    def test_reviews_reject_mixed_runs_catalogs_and_bad_bindings(self):
        seats, first = self.first_positions()
        for key, value in (('run_id', 'foreign'), ('catalog_sha256', 'stale'), ('round', 2)):
            bad = deepcopy(first)
            bad['results'][0]['response'][key] = value
            with self.assertRaises(rt.HikmahError):
                rt.assign_reviews(self.config, seats, bad)
        bad = deepcopy(first)
        bad['results'][0]['member'] = 'dmg-046'
        with self.assertRaises(rt.HikmahError):
            rt.assign_reviews(self.config, seats, bad)

    def test_reviews_require_two_survivors(self):
        seats, first = self.first_positions()
        first['results'] = first['results'][:1]
        with self.assertRaises(rt.HikmahError):
            rt.assign_reviews(self.config, seats, first)


class ProvenanceContractTests(RuntimeFixture):
    def requests(self):
        seen = {}
        def call(provider, req):
            meta = req['expected_metadata']
            seen[meta['round'], meta['seat_id']] = deepcopy(req)
            return reply(req)
        packet = self.execute(call)
        self.assertEqual(packet['status'], 'rounds-complete')
        return seen, packet

    def test_first_inputs_exclude_relation_appendices_and_other_persona_references(self):
        for member in self.config['members']:
            seat = {'seat_id': 'S01', 'member': member, 'provider': 'openai'}
            req = rt.compile_request(self.brief, seat, self.personas[member], 'test-run', 1, [], config=self.config)
            self.assertIsNone(req['review_assignment'])
            self.assertEqual(req['peer_rounds'], [])
            self.assertEqual(req['incoming_challenges'], [])
            self.assertNotIn(rt.CATALOG_START, req['persona'])
            self.assertNotIn('## Relations', req['persona'])
            meta = rt.validate_persona(self.personas[member], member, self.config)
            self.assertEqual([r['id'] for r in req['method_references']], meta['reference_ids'])
            serialized = json.dumps(req)
            for relation in self.config['relations']:
                self.assertNotIn(relation['id'], serialized)
            for rid in set(self.config['references']) - set(meta['reference_ids']):
                self.assertNotIn(rid, serialized)

    def test_method_references_optional_but_not_foreign_or_duplicate(self):
        valid = response(self.initial)
        valid['method_reference_ids'] = []
        rt.validate_contribution(valid, self.initial)
        for ids in (['ref-dmg-076'], ['invented'], ['ref-dmg-019', 'ref-dmg-019']):
            bad = response(self.initial)
            bad['method_reference_ids'] = ids
            with self.assertRaises(rt.HikmahError):
                rt.validate_contribution(bad, self.initial)

    def test_method_reference_cannot_be_laundered_as_decision_evidence(self):
        bad = response(self.initial)
        bad['evidence_ids'] = ['ref-dmg-019']
        with self.assertRaisesRegex(rt.HikmahError, 'decision evidence'):
            rt.validate_contribution(bad, self.initial)
        brief = deepcopy(self.brief)
        brief['evidence'][0]['id'] = 'ref-dmg-019'
        with self.assertRaisesRegex(rt.HikmahError, 'collide'):
            rt.compile_request(brief, self.seat, self.personas['dmg-019'], 'test-run', 1, [], config=self.config)

    def test_changed_method_invalidates_response_even_for_same_brief_run_and_catalog(self):
        revised = self.personas['dmg-019'].replace('## Focus\n\n', '## Focus\n\nA material method revision.\n\n')
        new = rt.compile_request(self.brief, self.seat, revised, 'test-run', 1, [], config=self.config)
        self.assertEqual(new['expected_metadata']['catalog_sha256'], self.initial['expected_metadata']['catalog_sha256'])
        self.assertNotEqual(new['expected_metadata']['persona_sha256'], self.initial['expected_metadata']['persona_sha256'])
        self.assertNotEqual(new['expected_metadata']['request_sha256'], self.initial['expected_metadata']['request_sha256'])
        with self.assertRaisesRegex(rt.HikmahError, 'persona_sha256'):
            rt.validate_contribution(response(self.initial), new)

    def test_midrun_method_change_rejected_even_with_unchanged_catalog(self):
        _, packet = self.requests()
        revised = self.personas['dmg-019'].replace('## Focus\n\n', '## Focus\n\nA changed method after first positions.\n\n')
        assigned = next(a for a in packet['plan']['review_assignments'] if a['reviewer_seat'] == 'S01')
        with self.assertRaisesRegex(rt.HikmahError, 'stale persona'):
            rt.compile_request(self.brief, self.seat, revised, 'test-run', 2, packet['rounds'][:1],
                               config=self.config, review_assignment=assigned)

    def test_failed_seat_cannot_reenter_final_compilation(self):
        def call(provider, req):
            if req['expected_metadata']['round'] == 2 and req['expected_metadata']['seat_id'] == 'S01':
                raise rt.ProviderError('http-503')
            return reply(req)
        packet = self.execute(call)
        with self.assertRaisesRegex(rt.HikmahError, 'lacks a valid position'):
            rt.compile_request(self.brief, self.seat, self.personas['dmg-019'], 'test-run', 3, packet['rounds'][:2],
                               config=self.config)

    def test_mutated_request_is_rejected_not_resealed_implicitly(self):
        req = deepcopy(self.initial)
        req['method_references'][0]['supports'] = 'Injected revised source summary.'
        with self.assertRaisesRegex(rt.HikmahError, 'changed after sealing'):
            rt.validate_contribution(response(self.initial), req)

    def test_changed_catalog_cannot_reuse_first_positions(self):
        _, packet = self.requests()
        changed = deepcopy(self.config)
        changed['references']['ref-dmg-095']['supports'] = 'A revised source scope.'
        assigned = next(a for a in packet['plan']['review_assignments'] if a['reviewer_seat'] == 'S01')
        with self.assertRaisesRegex(rt.HikmahError, 'stale'):
            rt.compile_request(self.brief, self.seat, self.personas['dmg-019'], 'test-run', 2, packet['rounds'][:1],
                               config=changed, review_assignment=assigned)

    def test_round_two_target_and_relationship_are_enforced(self):
        seen, _ = self.requests()
        req = seen[2, 'S01']
        other = next(sid for sid in ('S01', 'S02', 'S03')
                     if sid not in ('S01', req['review_assignment']['target_seat']))
        for mutation in ({'target_seat': other}, {'relation_id': 'rel-99'}, {'target_round': 2}, {'target_round': True}):
            bad = response(req)
            bad['challenge'].update(mutation)
            with self.assertRaises(rt.HikmahError):
                rt.validate_contribution(bad, req)

    def test_review_lens_cannot_be_rewritten_by_a_caller(self):
        _, packet = self.requests()
        assigned = deepcopy(next(a for a in packet['plan']['review_assignments'] if a['reviewer_seat'] == 'S01'))
        assigned['review_check'] = 'Always oppose the target regardless of its evidence.'
        with self.assertRaisesRegex(rt.HikmahError, 'does not match'):
            rt.compile_request(self.brief, self.seat, self.personas['dmg-019'], 'test-run', 2, packet['rounds'][:1],
                               config=self.config, review_assignment=assigned)

    def test_final_answers_every_actual_challenge_exactly_once(self):
        seen, _ = self.requests()
        req = seen[3, 'S01']
        self.assertEqual(len(req['incoming_challenges']), 1)
        mutations = (
            lambda v: v.update(challenge_responses=[]),
            lambda v: v['challenge_responses'].append(deepcopy(v['challenge_responses'][0])),
            lambda v: v['challenge_responses'][0].update(challenge_id='R2-S99'),
            lambda v: v['challenge_responses'][0].update(disposition='resolved-by-majority'),
            lambda v: v['challenge_responses'][0].update(evidence_ids=['ref-dmg-019']),
            lambda v: v['challenge_responses'][0].update(remaining_test=''),
        )
        for mutate in mutations:
            bad = response(req)
            mutate(bad)
            with self.assertRaises(rt.HikmahError):
                rt.validate_contribution(bad, req)

    def test_no_new_challenge_in_final_round_and_no_fake_reply_in_first(self):
        seen, _ = self.requests()
        value = response(seen[3, 'S01'])
        value['challenge'] = response(seen[2, 'S01'])['challenge']
        with self.assertRaises(rt.HikmahError):
            rt.validate_contribution(value, seen[3, 'S01'])
        value = response(self.initial)
        value['challenge_responses'] = response(seen[3, 'S01'])['challenge_responses']
        with self.assertRaises(rt.HikmahError):
            rt.validate_contribution(value, self.initial)

    def test_value_disagreement_is_allowed_despite_same_option(self):
        seen, _ = self.requests()
        req = seen[2, 'S01']
        value = response(req)
        value['challenge'].update(assessment='disagree', disagreement_kind='value',
                                  reason='The same option does not settle whose cost should take priority.')
        rt.validate_contribution(value, req)

    def test_invalid_or_old_response_schema_rejected(self):
        for version in (2, True, 3):
            value = response(self.initial)
            value['schema_version'] = version
            with self.assertRaises(rt.HikmahError):
                rt.validate_contribution(value, self.initial)

    def test_round_specific_payloads_share_frozen_snapshots_not_concurrent_replies(self):
        seen, _ = self.requests()
        for number in (2, 3):
            requests = [req for (n, _), req in seen.items() if n == number]
            self.assertTrue(all(req['peer_snapshot_roots'] == requests[0]['peer_snapshot_roots'] for req in requests))
            self.assertTrue(all(h['round'] < number for h in requests[0]['peer_rounds']))
        self.assertTrue(all(seen[3, sid]['review_assignment'] is None for sid in ('S01', 'S02', 'S03')))


class LedgerTests(RuntimeFixture):
    def test_every_member_reviewed_and_every_challenge_retained(self):
        packet = self.execute()
        self.assertEqual(packet['schema_version'], 1)
        self.assertEqual(len(packet['challenge_ledger']), 3)
        self.assertTrue(all(not c['review_missing'] and not c['unanswered_challenge_ids'] for c in packet['review_coverage']))
        self.assertTrue(all(c['response_status'] == 'answered' for c in packet['challenge_ledger']))
        self.assertIsNone(packet['verdict'])

    def test_acceptance_or_rebuttal_does_not_delete_or_auto_resolve_objection(self):
        def call(provider, req):
            value = response(req)
            for answer in value['challenge_responses']:
                answer['disposition'] = 'accepted' if req['expected_metadata']['seat_id'] == 'S01' else 'rebutted'
            return {'text': json.dumps(value), 'model': 'fixture', 'response_id': 'fixture'}
        packet = self.execute(call)
        self.assertEqual(len(packet['challenge_ledger']), 3)
        self.assertEqual(packet['advisory_counts']['keep'], 3)
        self.assertTrue(all(c['challenge'] and c['resolution_authority'].startswith('coordinator') for c in packet['challenge_ledger']))
        self.assertTrue(all('resolved' not in c for c in packet['challenge_ledger']))

    def test_failed_reviewer_and_unanswered_target_are_visible(self):
        def call(provider, req):
            if req['expected_metadata']['seat_id'] == 'S01' and req['expected_metadata']['round'] == 2:
                raise rt.ProviderError('http-503')
            return reply(req)
        packet = self.execute(call)
        self.assertEqual(packet['status'], 'partial')
        self.assertEqual(packet['api_request_attempts'], 8)
        self.assertEqual(len(packet['plan']['review_assignments']), 3)
        self.assertEqual(len(packet['challenge_ledger']), 2)
        self.assertEqual(sum(c['review_missing'] for c in packet['review_coverage']), 1)
        self.assertEqual(sum(c['response_status'] == 'unanswered' for c in packet['challenge_ledger']), 1)
        self.assertEqual(packet['coverage']['missing_seats'], ['S01'])

    def test_invalid_final_reply_cannot_disappear_from_the_ledger(self):
        def call(provider, req):
            value = response(req)
            if req['expected_metadata']['round'] == 3 and req['expected_metadata']['seat_id'] == 'S01':
                value['challenge_responses'] = []
            return {'text': json.dumps(value), 'model': 'fixture', 'response_id': 'fixture'}
        packet = self.execute(call)
        self.assertEqual(packet['status'], 'partial')
        entry = next(c for c in packet['challenge_ledger'] if c['target_seat'] == 'S01')
        self.assertEqual(entry['response_status'], 'unanswered')
        self.assertIsNone(entry['response'])

    def test_full_catalog_still_three_rounds_no_extra_model_synthesis_and_honest_graph_coverage(self):
        packet = self.execute(members=self.config['members'])
        self.assertEqual(packet['status'], 'rounds-complete')
        self.assertEqual(packet['api_request_attempts'], 297)
        self.assertEqual(len(packet['challenge_ledger']), 99)
        self.assertEqual(packet['plan']['separated_pairs'], 50)
        self.assertEqual(packet['plan']['provider_load'], {'anthropic': 50, 'openai': 49})
        coverage = packet['relation_coverage']
        self.assertEqual(len(coverage['active_relation_ids']), 109)
        self.assertTrue(coverage['unreviewed_relation_ids'])
        self.assertEqual(set(coverage['reviewed_relation_ids']) | set(coverage['unreviewed_relation_ids']),
                         set(coverage['active_relation_ids']))
        self.assertFalse(set(coverage['reviewed_relation_ids']) & set(coverage['unreviewed_relation_ids']))
        self.assertIsNone(packet['verdict'])
        self.assertEqual(len(packet['snapshot_roots']), 3)
        report = rt.audit_packet(json.loads(rt.json_bytes(packet)), self.config, self.personas)
        self.assertEqual((report['consistent'], report['seats'], report['requests_recompiled']), (True, 99, 297))

    def test_compilation_budget_failure_aborts_before_any_model_calls(self):
        seen = []
        with patch.object(rt, 'MAX_REQUEST_BYTES', 20):
            packet = self.execute(lambda provider, req: seen.append(req))
        self.assertEqual(seen, [])
        self.assertEqual(packet['status'], 'partial')
        self.assertEqual(packet['failure'], 'request-compilation-failed')
        self.assertEqual(packet['challenge_ledger'], [])
        self.assertTrue(all(c['review_missing'] for c in packet['review_coverage']))


class AuditTests(RuntimeFixture):
    """The packet is a pure function of brief, catalog, methods, and recorded rounds."""

    def audit(self, packet):
        with patch.object(rt, 'post_json', side_effect=AssertionError('network forbidden')):
            return rt.audit_packet(json.loads(rt.json_bytes(packet)), self.config, self.personas)

    def test_complete_packet_rederives_byte_for_byte_offline(self):
        report = self.audit(self.execute())
        self.assertTrue(report['consistent'])
        self.assertFalse(report['network_used'])
        self.assertEqual((report['status'], report['rounds_recorded'], report['requests_recompiled']), ('rounds-complete', 3, 9))

    def test_partial_stopped_and_aborted_packets_audit_as_recorded(self):
        def reviewer_fails(provider, req):
            meta = req['expected_metadata']
            if (meta['seat_id'], meta['round']) == ('S01', 2):
                raise rt.ProviderError('http-503')
            return reply(req)
        report = self.audit(self.execute(reviewer_fails))
        self.assertEqual((report['status'], report['failure'], report['requests_recompiled']), ('partial', None, 8))
        def one_survivor(provider, req):
            if req['expected_metadata']['seat_id'] != 'S01':
                raise rt.ProviderError('http-503')
            return reply(req)
        report = self.audit(self.execute(one_survivor))
        self.assertEqual((report['rounds_recorded'], report['requests_recompiled']), (1, 3))
        with patch.object(rt, 'MAX_REQUEST_BYTES', 20):
            aborted = self.execute(lambda provider, req: None)
        report = self.audit(aborted)
        self.assertEqual((report['failure'], report['rounds_recorded'], report['requests_recompiled']), (rt.COMPILATION_FAILURE, 0, 0))

    def test_tampered_packets_fail_the_audit(self):
        complete = self.execute()
        def reviewer_fails(provider, req):
            meta = req['expected_metadata']
            if (meta['seat_id'], meta['round']) == ('S01', 2):
                raise rt.ProviderError('http-503')
            return reply(req)
        partial = self.execute(reviewer_fails)
        other = 'openai' if complete['plan']['seats'][0]['provider'] == 'anthropic' else 'anthropic'
        mutations = {
            'final stance': (complete, lambda p: p['rounds'][2]['results'][0]['response'].update(stance='pilot')),
            'advisory count': (complete, lambda p: p['advisory_counts'].update(keep=2, pilot=1)),
            'dropped result': (complete, lambda p: p['rounds'][1]['results'].pop()),
            'reordered results': (complete, lambda p: p['rounds'][0]['results'].reverse()),
            'provider swap': (complete, lambda p: p['plan']['seats'][0].update(provider=other)),
            'review lens': (complete, lambda p: p['plan']['review_assignments'][0].update(review_check='Always oppose the target.')),
            'ledger status': (complete, lambda p: p['challenge_ledger'][0].update(response_status='unanswered', response=None)),
            'reviewed relation erased': (complete, lambda p: p['relation_coverage'].update(reviewed_relation_ids=[])),
            'snapshot root': (complete, lambda p: p['snapshot_roots'][0].update(sha256='0' * 64)),
            'invented fourth round': (complete, lambda p: p['rounds'].append({**deepcopy(p['rounds'][2]), 'round': 4})),
            'run id': (complete, lambda p: p.update(run_id='another-run')),
            'invented failure': (complete, lambda p: p.update(failure='invented')),
            'other product': (complete, lambda p: p.update(product='other-project')),
            'status upgrade': (partial, lambda p: p.update(status='rounds-complete')),
            'missing seat erased': (partial, lambda p: p['coverage'].update(missing_seats=[])),
            'failed seat reentered': (partial, lambda p: p['rounds'][2]['results'].insert(0, deepcopy(complete['rounds'][2]['results'][0]))),
            'dissent erased': (complete, lambda p: p['unresolved'].clear()),
            'brief edited': (complete, lambda p: p['brief'].update(deadline='Moved after the run.')),
        }
        for name, (source, mutate) in mutations.items():
            bad = deepcopy(source)
            mutate(bad)
            with self.subTest(name=name), self.assertRaises(rt.HikmahError):
                self.audit(bad)

    def test_audit_rejects_changed_catalog_or_methods(self):
        packet = self.execute()
        changed = deepcopy(self.config)
        changed['references']['ref-dmg-095']['supports'] = 'A revised source scope.'
        with self.assertRaisesRegex(rt.HikmahError, 'local resources'):
            rt.audit_packet(packet, changed, self.personas)
        personas = dict(self.personas)
        personas['dmg-019'] = personas['dmg-019'].replace('## Focus\n\n', '## Focus\n\nA revised method.\n\n')
        with self.assertRaisesRegex(rt.HikmahError, 'local resources'):
            rt.audit_packet(packet, self.config, personas)

    def test_audit_cli_is_offline_and_reports_exit_codes(self):
        import io, os, sys, tempfile
        from unittest.mock import patch as _patch
        complete = self.execute()
        def reviewer_fails(provider, req):
            meta = req['expected_metadata']
            if (meta['seat_id'], meta['round']) == ('S01', 2):
                raise rt.ProviderError('http-503')
            return reply(req)
        partial = self.execute(reviewer_fails)
        tampered = deepcopy(complete)
        tampered['advisory_counts'].update(keep=2, pilot=1)
        with tempfile.TemporaryDirectory() as directory:
            for name, packet, code in (('complete', complete, 0), ('partial', partial, 3), ('tampered', tampered, 2)):
                path = os.path.join(directory, name + '.json')
                with open(path, 'wb') as handle:
                    handle.write(rt.json_bytes(packet))
                out, err = io.StringIO(), io.StringIO()
                with _patch.object(rt, 'post_json', side_effect=AssertionError('network forbidden')), \
                     _patch.object(sys, 'stdout', out), _patch.object(sys, 'stderr', err):
                    result = rt.main(['audit', '--packet', path])
                with self.subTest(name=name):
                    self.assertEqual(result, code, err.getvalue())
                    if code == 2:
                        self.assertIn('deterministic derivation', err.getvalue())
                    else:
                        report = json.loads(out.getvalue())
                        self.assertTrue(report['consistent'])
                        self.assertFalse(report['network_used'])


if __name__ == '__main__':
    unittest.main()
