"""Core product regressions. All replies and HTTP envelopes are test fixtures."""
from __future__ import annotations

from copy import deepcopy
import http.client
import io
import json
import os
import subprocess
import sys
import tempfile
from threading import Lock
import unittest
from unittest.mock import patch
import urllib.error

from support import ROOT, SourceCopy, project, runtime as rt

EXPECTED = {f'dmg-{n:03}' for n in range(1, 100)}
ENV = {'ANTHROPIC_API_KEY': 'fixture-anthropic-key-not-real', 'HIKMAH_ANTHROPIC_MODEL': 'fixture-claude-model',
       'OPENAI_API_KEY': 'fixture-openai-key-not-real', 'HIKMAH_OPENAI_MODEL': 'fixture-openai-model'}


def response(request, *, stance='keep', dissent=None):
    metadata = request['expected_metadata']
    result = {**metadata, 'stance': stance, 'rationale': f'Test claim from {metadata["seat_id"]}, round {metadata["round"]}.',
              'evidence_ids': ['E1'], 'assumptions': ['Fixture assumption.'],
              'uncertainties': ['Real production data is not supplied.'],
              'blind_spot': 'This is a deterministic fixture, not model judgment.',
              'confidence': 'low', 'confidence_reason': 'No live model has been evaluated.',
              'position_change': 'Fixture position, not a recommendation.',
              'dissent': [] if dissent is None else dissent,
              'kill_criteria': ['Stop the proposed pilot if an existing hard constraint is violated.'],
              'next_action': 'Obtain the missing measurement before deciding.', 'challenge': None,
              'method_reference_ids': [r['id'] for r in request['method_references']],
              'challenge_responses': [
                  {'challenge_id': c['challenge_id'], 'disposition': 'unresolved',
                   'rationale': 'The fixture cannot settle the supplied objection.', 'evidence_ids': ['E1'],
                   'remaining_test': 'Collect the missing decision-relevant measurement.'}
                  for c in request['incoming_challenges']]}

    if metadata['round'] == 2:
        peers = [p for p in request['peer_rounds'][0]['positions'] if p['seat_id'] != metadata['seat_id']]
        peer = next(p for p in peers if p['seat_id'] == request['review_assignment']['target_seat'])
        result['challenge'] = {'target_seat': peer['seat_id'], 'target_round': 1,
                               'relation_id': request['review_assignment']['relation_id'],
                               'disagreement_kind': 'evidence', 'target_claim': peer['rationale'],
                               'assessment': 'qualify', 'reason': 'The supplied observation is insufficient to settle the option.',
                               'resolution_test': 'Collect the missing measurements.'}
    return result


def reply(request, **kwargs):
    return {'text': json.dumps(response(request, **kwargs)), 'model': 'fixture-model',
            'response_id': 'fixture-response-id', 'usage': {'input_tokens': 1, 'output_tokens': 1}}


def http_envelope(provider, text='READY', *, completed=True):
    if provider == 'anthropic':
        return {'model': 'reported-claude', 'id': 'msg_fixture',
                'stop_reason': 'end_turn' if completed else 'max_tokens',
                'content': [{'type': 'text', 'text': text}], 'usage': {'input_tokens': 1, 'output_tokens': 1}}
    return {'model': 'reported-openai', 'id': 'resp_fixture', 'status': 'completed' if completed else 'incomplete',
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}],
            'usage': {'input_tokens': 1, 'output_tokens': 1}}


class ProductContractTests(SourceCopy):
    def test_exact_supplied_99_lenses_and_unique_methods(self):
        config, personas = rt.resources(self.root)
        self.assertEqual(set(config['members']), EXPECTED)
        self.assertEqual(set(personas), EXPECTED)
        methods = []
        for member, raw in personas.items():
            metadata, body = project.parse_frontmatter(raw, member)
            methods.append(metadata['reasoning_method'])
            for heading in ('Grounding protocol', 'Method', 'Blind spots', 'Contribution contract'):
                self.assertIn(f'## {heading}\n', body)
            self.assertIn('not Allah', body)
        self.assertEqual(len(set(methods)), 99)

    def test_removed_persona_is_rejected(self):
        (self.root / 'personas/dmg-019.md').unlink()
        with self.assertRaisesRegex(project.ProjectError, '99-persona catalog'):
            project.validate(self.root)

    def test_missing_grounding_protocol_rejected(self):
        path = self.root / 'personas/dmg-019.md'
        path.write_text(path.read_text(encoding='utf-8').replace('## Grounding protocol', '## Removed'), encoding='utf-8')
        with self.assertRaisesRegex(project.ProjectError, 'Grounding protocol'):
            project.validate(self.root)

    def test_changed_persona_id_rejected(self):
        path = self.root / 'personas/dmg-019.md'
        path.write_text(path.read_text(encoding='utf-8').replace('id: "dmg-019"', 'id: "not-dmg-019"'), encoding='utf-8')
        with self.assertRaisesRegex(project.ProjectError, 'persona ID'):
            project.validate(self.root)

    def test_presets_resolve_and_duplicate_polarity_rejected(self):
        config, _ = rt.resources(self.root)
        for triad in config['triads']:
            self.assertEqual(len(rt.select_members(config, triad=triad)), 3)
        for duo in config['pairs']:
            self.assertEqual(len(rt.select_members(config, duo=duo)), 2)
        self.assertEqual(len(rt.select_members(config, full=True)), 99)
        self.assertEqual(len(rt.select_members(config, profile='decision')), 6)
        duplicate = deepcopy(config['relations'][0])
        duplicate['id'] = 'rel-99'
        config['relations'].append(duplicate)
        with self.assertRaisesRegex(rt.HikmahError, 'duplicate relation'):
            rt.validate_config(config)

    def test_unknown_member_duplicate_member_and_mixed_selectors_rejected(self):
        config, _ = rt.resources(self.root)
        for kwargs in ({'members': ['dmg-019', 'missing']}, {'members': ['dmg-019', 'dmg-019']},
                       {'members': ['dmg-019']}, {'triad': 'missing'}, {'triad': 'evidence', 'full': True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(rt.HikmahError):
                rt.select_members(config, **kwargs)

    def test_full_catalog_in_both_packages_and_runtime_is_standalone(self):
        meta, inputs = project.validate(self.root)
        for host in project.HOSTS:
            files = project.package_files(host, meta, inputs)
            for member in EXPECTED:
                self.assertEqual(files[f'skills/hikmah/references/personas/{member}.md'], inputs[f'personas/{member}.md'])
            target = self.root / 'scratch' / host
            for name, data in files.items():
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            result = subprocess.run([sys.executable, '-B', '-I', str(target / 'skills/hikmah/scripts/deliberation.py'),
                                     'plan', '--brief', str(self.root / 'examples/decision.json'),
                                     '--duo', 'restraint-expansion', '--providers', 'anthropic,openai'],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan['round_count'], 3)
            self.assertEqual(plan['plan']['separated_pairs'], 1)
            self.assertEqual(plan['execution'], 'not-run')

    def test_verdict_contract_cannot_be_removed(self):
        path = self.root / 'agents/hikmah.md'
        path.write_text(path.read_text(encoding='utf-8').replace('## Verdict contract', '## Removed'), encoding='utf-8')
        with self.assertRaisesRegex(project.ProjectError, 'Verdict contract'):
            project.validate(self.root)


class RoutingAndDetectionTests(unittest.TestCase):
    def test_pair_separation_and_deterministic_provider_order(self):
        args = (['dmg-019', 'dmg-094'], ['anthropic', 'openai'], [['dmg-019', 'dmg-094']])
        planned = rt.route(*args)
        self.assertEqual(planned['separated_pairs'], 1)
        self.assertEqual(planned['provider_load'], {'anthropic': 1, 'openai': 1})
        self.assertEqual(planned, rt.route(args[0], list(reversed(args[1])), args[2]))
        self.assertTrue(planned['planning_only'])

    def test_separation_has_priority_over_incompatible_exact_balance(self):
        plan = rt.route(['a', 'b', 'c', 'd'], ['anthropic', 'openai'], [['a', 'b'], ['a', 'c'], ['a', 'd']])
        self.assertEqual(plan['separated_pairs'], 3)
        self.assertEqual(sorted(plan['provider_load'].values()), [1, 3])
        self.assertEqual(plan['unseparated_pairs'], [])

    def test_odd_cycle_reports_unavoidable_unseparated_pair(self):
        plan = rt.route(['a', 'b', 'c'], ['anthropic', 'openai'], [['a', 'b'], ['b', 'c'], ['c', 'a']])
        self.assertEqual(plan['separated_pairs'], 2)
        self.assertEqual(len(plan['unseparated_pairs']), 1)

    def test_one_or_no_provider_does_not_invent_diversity(self):
        for providers in ([], ['anthropic']):
            plan = rt.route(['dmg-019', 'dmg-094'], providers, [['dmg-019', 'dmg-094']])
            self.assertEqual(plan['family_diversity'], len(providers))
            self.assertEqual(plan['separated_pairs'], 0)
            self.assertEqual(len(plan['unseparated_pairs']), 1)

    def test_unsupported_duplicate_providers_and_invalid_edges_rejected(self):
        for providers in (['other'], ['anthropic', 'anthropic'], ['anthropic', 'openai', 'other']):
            with self.subTest(providers=providers), self.assertRaises(rt.HikmahError):
                rt.route(['dmg-019', 'dmg-094'], providers, [['dmg-019', 'dmg-094']])
        with self.assertRaises(rt.HikmahError):
            rt.route(['dmg-019', 'dmg-094'], ['openai'], [['dmg-019']])

    def test_full_roster_routes_with_reported_coverage(self):
        config, _ = rt.resources()
        result = rt.route(config['members'], ['anthropic', 'openai'], rt.polarity_edges(config))
        self.assertEqual(len(result['seats']), 99)
        self.assertEqual(result['separated_pairs'] + len(result['unseparated_pairs']), len(rt.polarity_edges(config)))
        self.assertEqual(sum(result['provider_load'].values()), 99)

    def test_detect_is_offline_and_never_prints_keys(self):
        with patch.object(rt, 'post_json', side_effect=AssertionError('network forbidden')) as post:
            result = rt.detect(ENV)
        self.assertFalse(post.called)
        self.assertFalse(result['network_used'])
        self.assertEqual(result['verified_available_count'], 0)
        self.assertTrue(all(x['availability'] == 'unverified' for x in result['providers']))
        for key in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY'):
            self.assertNotIn(ENV[key], json.dumps(result))

    def test_invalid_missing_model_or_key_is_not_available(self):
        for env in ({}, {'ANTHROPIC_API_KEY': 'fixture'}, {'HIKMAH_ANTHROPIC_MODEL': 'fixture'},
                    {'ANTHROPIC_API_KEY': 'fixture', 'HIKMAH_ANTHROPIC_MODEL': 'bad\nmodel'}):
            result = rt.detect(env)
            self.assertFalse(any(p['configured'] for p in result['providers']))
            self.assertEqual(result['verified_available_count'], 0)

    def test_probe_needs_network_optin_before_any_request(self):
        with patch.object(rt, 'request_api') as call:
            with self.assertRaisesRegex(rt.HikmahError, 'allow-network'):
                rt.probe(ENV, allow_network=False)
            call.assert_not_called()

    def test_probe_records_ready_or_failed_without_sending_decision_evidence(self):
        def call(provider, model, key, instructions, content, *args):
            self.assertEqual(content, 'READY')
            if provider == 'openai':
                raise rt.ProviderError('http-401')
            return {'text': 'READY', 'model': 'reported-claude'}
        with patch.object(rt, 'request_api', side_effect=call):
            result = rt.probe(ENV, allow_network=True)
        self.assertEqual(result['verified_available_count'], 1)
        self.assertEqual([p['availability'] for p in result['providers']], ['ready', 'failed'])


class RuntimeFixture(unittest.TestCase):
    def setUp(self):
        self.config, self.personas = rt.resources()
        self.brief = rt.load_json(ROOT / 'examples/decision.json')
        self.members = ['dmg-019', 'dmg-094', 'dmg-046']
        self.seat = {'seat_id': 'S01', 'member': 'dmg-019', 'provider': 'anthropic'}
        self.initial = rt.compile_request(self.brief, self.seat, self.personas['dmg-019'], 'test-run', 1, [], config=self.config)

    def execute(self, caller=None, members=None, **kwargs):
        return rt.run_rounds(self.brief, members or self.members, self.config, self.personas,
                             ['anthropic', 'openai'], caller or (lambda p, req: reply(req)),
                             run_id='test-run', **kwargs)


class ContractTests(RuntimeFixture):
    def test_brief_is_required_and_changes_alter_snapshot(self):
        for field in ('decision', 'constraints', 'evidence', 'reversibility', 'deadline', 'options'):
            changed = deepcopy(self.brief)
            del changed[field]
            with self.subTest(field=field), self.assertRaises(rt.HikmahError):
                rt.validate_brief(changed)
        changed = deepcopy(self.brief)
        changed['deadline'] = 'New constraint.'
        self.assertNotEqual(rt.snapshot_id(changed), rt.snapshot_id(self.brief))

    def test_brief_rejects_duplicate_options_evidence_ids_and_boolean_version(self):
        for mutate in (lambda b: b['options'].append(b['options'][0]),
                       lambda b: b['evidence'].append(b['evidence'][0]),
                       lambda b: b.update(schema_version=True)):
            bad = deepcopy(self.brief)
            mutate(bad)
            with self.assertRaises(rt.HikmahError):
                rt.validate_brief(bad)

    def test_empty_evidence_is_explicitly_allowed(self):
        self.brief['evidence'] = []
        rt.validate_brief(self.brief)

    def test_initial_request_contains_no_peer_positions_or_polarity_assignments(self):
        self.assertEqual(self.initial['peer_rounds'], [])
        self.assertIsNone(self.initial['review_assignment'])
        self.assertEqual(self.initial['incoming_challenges'], [])
        self.assertNotIn('plan', self.initial)
        self.assertNotIn('provider', self.initial)

    def test_round_barrier_and_boolean_round_are_rejected(self):
        for round_number, prior in ((2, []), (3, []), (True, [])):
            with self.assertRaises(rt.HikmahError):
                rt.compile_request(self.brief, self.seat, self.personas['dmg-019'], 'test-run', round_number, prior, config=self.config)

    def test_valid_contract_and_explicit_abstention(self):
        value = response(self.initial)
        rt.validate_contribution(value, self.initial)
        value['stance'] = None
        rt.validate_contribution(value, self.initial)

    def test_stale_snapshot_run_round_and_foreign_seat_rejected(self):
        for key, value in (('snapshot_id', 'stale'), ('run_id', 'stale'), ('round', 2),
                           ('round', True), ('seat_id', 'S99')):
            bad = response(self.initial)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(rt.HikmahError):
                rt.validate_contribution(bad, self.initial)

    def test_unknown_option_evidence_extra_field_and_peer_in_round1_rejected(self):
        mutations = ({'stance': 'invented'}, {'evidence_ids': ['invented']}, {'extra': 'not allowed'}, {'challenge': {}})
        for mutation in mutations:
            bad = response(self.initial)
            bad.update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(rt.HikmahError):
                rt.validate_contribution(bad, self.initial)

    def round_two_request(self):
        packet = self.execute()
        histories = packet['rounds'][:1]
        assigned = next(a for a in packet['plan']['review_assignments'] if a['reviewer_seat'] == self.seat['seat_id'])
        return rt.compile_request(self.brief, self.seat, self.personas['dmg-019'], 'test-run', 2, histories,
                                  config=self.config, review_assignment=assigned)

    def test_cross_examination_requires_real_nonself_quoted_peer_claim(self):
        request = self.round_two_request()
        for mutation in ({'target_seat': 'S01'}, {'target_seat': 'S99'}, {'target_claim': 'Invented quotation.'}):
            bad = response(request)
            bad['challenge'].update(mutation)
            with self.assertRaises(rt.HikmahError):
                rt.validate_contribution(bad, request)
        bad = response(request)
        bad['challenge'] = None
        with self.assertRaises(rt.HikmahError):
            rt.validate_contribution(bad, request)

    def test_direct_engagement_does_not_require_fake_disagreement(self):
        request = self.round_two_request()
        good = response(request)
        good['challenge']['assessment'] = 'no-material-disagreement'
        good['challenge']['disagreement_kind'] = 'stress-test'
        rt.validate_contribution(good, request)

    def test_stale_prior_history_cannot_be_compiled_into_new_round(self):
        history = self.execute()['rounds'][:1]
        history[0]['results'][0]['response']['snapshot_id'] = 'stale'
        with self.assertRaisesRegex(rt.HikmahError, 'stale'):
            rt.compile_request(self.brief, self.seat, self.personas['dmg-019'], 'test-run', 2, history, config=self.config)

    def test_stated_string_limits_are_the_enforced_limits(self):
        # The system message, the validator, and the schema docs must state one contract.
        value = response(self.initial)
        value['rationale'] = 'r' * rt.MAX_TEXT_CHARS
        value['dissent'] = ['d' * rt.MAX_LIST_ENTRY_CHARS]
        value['assumptions'] = [f'assumption {i}' for i in range(rt.MAX_LIST_ENTRIES)]
        rt.validate_contribution(value, self.initial)
        for mutate in (lambda v: v.update(rationale='r' * (rt.MAX_TEXT_CHARS + 1)),
                       lambda v: v.update(dissent=['d' * (rt.MAX_LIST_ENTRY_CHARS + 1)]),
                       lambda v: v.update(assumptions=[f'assumption {i}' for i in range(rt.MAX_LIST_ENTRIES + 1)])):
            bad = response(self.initial)
            mutate(bad)
            with self.assertRaises(rt.HikmahError):
                rt.validate_contribution(bad, self.initial)
        for phrase in (f'one line of at most {rt.MAX_TEXT_CHARS} characters',
                       f'at most {rt.MAX_LIST_ENTRIES} distinct entries',
                       f'each one line of at most {rt.MAX_LIST_ENTRY_CHARS} characters'):
            self.assertIn(phrase, rt.SYSTEM)

    def test_json_contract_rejects_duplicates_nonfinite_and_unknown_fields(self):
        for raw in ('{"stance":"keep","stance":"pilot"}', '{"x":NaN}', '{"x":1e99999}'):
            with self.assertRaises(rt.HikmahError):
                rt.decode_json(raw, 'model')
        self.assertEqual(set(rt.response_schema()['required']), rt.RESPONSE_KEYS)
        self.assertFalse(rt.response_schema()['additionalProperties'])


class ExecutionTests(RuntimeFixture):
    def test_three_rounds_share_snapshot_roots_with_isolated_views_and_barriers(self):
        seen = []
        lock = Lock()
        def call(provider, request):
            with lock:
                number = request['expected_metadata']['round']
                earlier = [x for x in seen if x['expected_metadata']['round'] == number - 1]
                if number > 1:
                    self.assertEqual(len(earlier), 3)
                seen.append(deepcopy(request))
            return reply(request)
        packet = self.execute(call)
        self.assertEqual(packet['status'], 'rounds-complete')
        self.assertEqual(packet['api_request_attempts'], 9)
        self.assertEqual([r['round'] for r in packet['rounds']], [1, 2, 3])
        for number in (1, 2, 3):
            batch = [r for r in seen if r['expected_metadata']['round'] == number]
            self.assertTrue(all(r['peer_snapshot_roots'] == batch[0]['peer_snapshot_roots'] for r in batch))
            self.assertEqual(len(batch[0]['peer_rounds']), number - 1)
            for prior in batch[0]['peer_rounds']:
                for pos in prior['positions']:
                    self.assertNotIn('member', pos)
                    self.assertNotIn('provider', pos)
        self.assertIsNone(packet['verdict'])

    def test_duo_has_three_rounds_with_one_peer(self):
        packet = self.execute(members=['dmg-020', 'dmg-021'])
        self.assertEqual(packet['api_request_attempts'], 6)
        self.assertEqual(packet['status'], 'rounds-complete')
        self.assertEqual(packet['plan']['separated_pairs'], 1)

    def test_first_round_failure_is_missing_not_replaced_or_abstained(self):
        calls = []
        def call(provider, request):
            meta = request['expected_metadata']
            calls.append((meta['seat_id'], meta['round'], provider))
            if meta['seat_id'] == 'S01':
                raise rt.ProviderError('http-401')
            return reply(request)
        packet = self.execute(call)
        self.assertEqual(packet['status'], 'partial')
        self.assertEqual(packet['coverage']['missing_seats'], ['S01'])
        self.assertEqual(packet['abstentions'], [])
        self.assertEqual(packet['advisory_counts']['keep'], 2)
        self.assertEqual(len([x for x in calls if x[0] == 'S01']), 1)
        self.assertEqual(packet['api_request_attempts'], 7)

    def test_fewer_than_two_survivors_stops_before_cross_examination(self):
        def call(provider, req):
            if req['expected_metadata']['seat_id'] != 'S01':
                raise rt.ProviderError('http-503')
            return reply(req)
        packet = self.execute(call)
        self.assertEqual(len(packet['rounds']), 1)
        self.assertEqual(packet['api_request_attempts'], 3)
        self.assertEqual(packet['coverage']['final_responses'], 0)
        self.assertEqual(packet['status'], 'partial')

    def test_invalid_or_stale_response_never_enters_peer_snapshot(self):
        seen = []
        def call(provider, req):
            seen.append(deepcopy(req))
            result = response(req)
            if req['expected_metadata']['seat_id'] == 'S01':
                result['snapshot_id'] = 'stale'
            return {'text': json.dumps(result), 'model': 'fixture', 'response_id': 'fixture'}
        packet = self.execute(call)
        self.assertEqual(packet['rounds'][0]['results'][0]['status'], 'invalid-response')
        for req in seen:
            for history in req['peer_rounds']:
                self.assertFalse(any(x['seat_id'] == 'S01' for x in history['positions']))

    def test_earlier_dissent_and_kill_criteria_survive_later_agreement(self):
        objection = 'A material rollout risk remains unresolved.'
        def call(provider, req):
            meta = req['expected_metadata']
            return reply(req, dissent=[objection] if meta['seat_id'] == 'S01' and meta['round'] == 1 else [])
        packet = self.execute(call)
        self.assertEqual(packet['advisory_counts']['keep'], 3)
        self.assertTrue(any(objection in x['dissent'] for x in packet['unresolved']))
        self.assertTrue(all(x['kill_criteria'] for x in packet['unresolved']))
        self.assertIsNone(packet['verdict'])

    def test_abstention_is_separate_from_missing_seats(self):
        def call(provider, req):
            return reply(req, stance=None if req['expected_metadata']['seat_id'] == 'S01' else 'keep')
        packet = self.execute(call)
        self.assertEqual(packet['abstentions'], ['S01'])
        self.assertEqual(packet['coverage']['missing_seats'], [])
        self.assertEqual(packet['advisory_counts']['keep'], 2)

    def test_caller_cannot_mutate_shared_brief_or_round_snapshot(self):
        original = deepcopy(self.brief)
        def call(provider, req):
            result = reply(req)
            req['brief']['decision'] = 'Mutated local request.'
            req['peer_rounds'].clear()
            return result
        packet = self.execute(call)
        self.assertEqual(packet['brief'], original)
        self.assertEqual(self.brief, original)
        self.assertEqual(packet['status'], 'rounds-complete')

    def test_review_assignment_failure_ends_with_a_partial_packet_not_a_traceback(self):
        calls = []
        def call(provider, req):
            calls.append(req['expected_metadata']['round'])
            return reply(req)
        with patch.object(rt, 'assign_reviews', side_effect=rt.HikmahError('fixture assignment failure')):
            packet = self.execute(call)
        self.assertEqual(packet['status'], 'partial')
        self.assertEqual(packet['failure'], rt.COMPILATION_FAILURE)
        self.assertEqual([r['round'] for r in packet['rounds']], [1])
        self.assertEqual(calls, [1, 1, 1])
        self.assertEqual(packet['api_request_attempts'], 3)
        self.assertEqual(packet['plan']['review_assignments'], [])
        self.assertEqual(packet['coverage']['missing_seats'], ['S01', 'S02', 'S03'])

    def test_packet_records_the_snapshot_roots_every_request_carried(self):
        seen = []
        def call(provider, req):
            seen.append(deepcopy(req))
            return reply(req)
        packet = self.execute(call)
        self.assertEqual([root['round'] for root in packet['snapshot_roots']], [1, 2, 3])
        for root, history in zip(packet['snapshot_roots'], packet['rounds']):
            self.assertEqual(root, rt.snapshot_root(rt.frozen_round(history)))
            self.assertEqual(root['available_positions'], 3)
        for req in seen:
            number = req['expected_metadata']['round']
            self.assertEqual(req['peer_snapshot_roots'], packet['snapshot_roots'][:number - 1])
            self.assertEqual(req['peer_context_policy'], rt.PEER_CONTEXT_POLICY[number])

    def test_budget_is_checked_before_any_call(self):
        with patch.object(rt, 'request_api') as call:
            for extra in ({'max_calls': 8}, {'max_calls': True}, {'concurrency': 0}):
                with self.assertRaises(rt.HikmahError):
                    rt.run_api(self.brief, self.members, self.config, self.personas, ['anthropic', 'openai'],
                               allow_network=True, confirm_data_sharing=True, env=ENV, **extra)
            call.assert_not_called()

    def test_network_and_data_sharing_are_both_required(self):
        with patch.object(rt, 'request_api') as call:
            for network, sharing in ((False, False), (True, False), (False, True)):
                with self.assertRaises(rt.HikmahError):
                    rt.run_api(self.brief, self.members, self.config, self.personas, ['anthropic'],
                               allow_network=network, confirm_data_sharing=sharing, env=ENV)
            call.assert_not_called()

    def test_unconfigured_provider_fails_before_sending_evidence(self):
        with patch.object(rt, 'request_api') as call:
            with self.assertRaises(rt.HikmahError):
                rt.run_api(self.brief, self.members, self.config, self.personas, ['anthropic', 'openai'],
                           allow_network=True, confirm_data_sharing=True, env={})
            call.assert_not_called()

    def test_invalid_output_token_budget_fails_before_requests(self):
        with patch.object(rt, 'request_api') as call:
            for cap in (0, 127, 8193, True):
                with self.assertRaises(rt.HikmahError):
                    rt.run_api(self.brief, self.members, self.config, self.personas, ['anthropic'],
                               allow_network=True, confirm_data_sharing=True, max_tokens=cap, env=ENV)
            call.assert_not_called()


class HttpContractTests(unittest.TestCase):
    def test_official_request_shapes_are_fresh_tool_free_and_structured(self):
        for provider in rt.PROVIDERS:
            with patch.object(rt, 'post_json', return_value=http_envelope(provider)) as post:
                result = rt.request_api(provider, 'fixture-model', 'fixture-key', 'Instructions', 'Payload', 512, 30, rt.response_schema())
            args = post.call_args.args
            body = args[1]
            self.assertNotIn('tools', body)
            self.assertNotIn('previous_response_id', body)
            self.assertNotIn('conversation', body)
            self.assertEqual(body['model'], 'fixture-model')
            self.assertNotIn('fixture-key', json.dumps(body))
            self.assertEqual(result['text'], 'READY')
            if provider == 'openai':
                self.assertFalse(body['store'])
                self.assertTrue(body['text']['format']['strict'])
            else:
                self.assertEqual(body['output_config']['format']['type'], 'json_schema')

    def test_unrequested_openai_tool_output_is_rejected_even_with_text(self):
        raw = http_envelope('openai')
        raw['output'].append({'type': 'function_call', 'name': 'unrequested', 'arguments': '{}'})
        with patch.object(rt, 'post_json', return_value=raw), self.assertRaises(rt.ProviderError):
            rt.request_api('openai', 'fixture-model', 'fixture-key', 'Instructions', 'Payload', 512, 30)

    def test_incomplete_refused_and_empty_responses_rejected(self):
        for provider in rt.PROVIDERS:
            bad = http_envelope(provider, completed=False)
            with patch.object(rt, 'post_json', return_value=bad), self.assertRaises(rt.ProviderError):
                rt.request_api(provider, 'fixture-model', 'fixture-key', 'Instructions', 'Payload', 512, 30)
        for raw in ({'model': 'fixture', 'id': 'fixture', 'status': 'completed', 'output': []},
                    {'model': 'fixture', 'id': 'fixture', 'status': 'completed', 'output': [
                        {'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'No.'}]}]}):
            with patch.object(rt, 'post_json', return_value=raw), self.assertRaises(rt.ProviderError):
                rt.request_api('openai', 'fixture-model', 'fixture-key', 'Instructions', 'Payload', 512, 30)

    def test_no_redirect_or_environment_proxy_for_credentials(self):
        self.assertIsNone(rt.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://invalid.example'))
        opener = unittest.mock.Mock()
        opener.open.return_value = io.BytesIO(json.dumps(http_envelope('openai')).encode())
        with patch.object(rt.urllib.request, 'build_opener', return_value=opener) as factory:
            rt.post_json('openai', {'input': 'fixture'}, 'fixture-key', 30)
        self.assertEqual(factory.call_args.args[0].proxies, {})
        req = opener.open.call_args.args[0]
        self.assertEqual(req.full_url, 'https://api.openai.com/v1/responses')
        self.assertEqual(req.get_header('Authorization'), 'Bearer fixture-key')

    def test_http_failure_does_not_expose_body_or_key(self):
        opener = unittest.mock.Mock()
        opener.open.side_effect = urllib.error.HTTPError('https://example.invalid', 401, 'fixture-secret', {}, io.BytesIO(b'fixture-secret'))
        with patch.object(rt.urllib.request, 'build_opener', return_value=opener):
            with self.assertRaises(rt.ProviderError) as caught:
                rt.post_json('openai', {'input': 'fixture'}, 'fixture-key', 30)
        self.assertEqual(str(caught.exception), 'http-401')
        self.assertNotIn('fixture-secret', str(caught.exception))

    def test_oversized_response_is_rejected(self):
        opener = unittest.mock.Mock()
        opener.open.return_value = io.BytesIO(b'x' * (rt.MAX_RESPONSE_BYTES + 1))
        with patch.object(rt.urllib.request, 'build_opener', return_value=opener), self.assertRaises(rt.ProviderError):
            rt.post_json('openai', {'input': 'fixture'}, 'fixture-key', 30)

    def test_api_model_ids_cannot_override_endpoint(self):
        with patch.object(rt, 'post_json') as post:
            with self.assertRaises(rt.HikmahError):
                rt.request_api('openai', 'https://untrusted.example/model', 'fixture-key', 'Instructions', 'Payload', 512, 30)
            post.assert_not_called()

    def test_truncated_or_malformed_http_is_a_sanitized_transport_failure(self):
        # http.client errors are not OSError; they once escaped as tracebacks and lost the run.
        truncated = unittest.mock.MagicMock()
        truncated.__enter__.return_value.read.side_effect = http.client.IncompleteRead(b'fixture-partial')
        for side_effect, value in ((None, truncated), (http.client.BadStatusLine('fixture'), None),
                                   (http.client.RemoteDisconnected('fixture'), None)):
            opener = unittest.mock.Mock()
            opener.open.side_effect, opener.open.return_value = side_effect, value
            with self.subTest(error=side_effect or 'IncompleteRead'), \
                 patch.object(rt.urllib.request, 'build_opener', return_value=opener):
                with self.assertRaises(rt.ProviderError) as caught:
                    rt.post_json('openai', {'input': 'fixture'}, 'fixture-key', 30)
                self.assertEqual(caught.exception.code, 'network-or-timeout')


class RuntimeRegressionTests(unittest.TestCase):
    def test_detect_and_transport_share_credential_rules(self):
        padded = {'ANTHROPIC_API_KEY': ' fixture-key \n', 'HIKMAH_ANTHROPIC_MODEL': ' fixture-model '}
        self.assertEqual(rt.configuration(padded)['ANTHROPIC_API_KEY'], 'fixture-key')
        self.assertTrue(rt.detect(padded)['providers'][0]['configured'])
        for key in ('fixture key', 'fixture\tkey', 'fixture-kéy'):
            with self.subTest(key=key):
                env = {'ANTHROPIC_API_KEY': key, 'HIKMAH_ANTHROPIC_MODEL': 'fixture-model'}
                self.assertFalse(rt.detect(env)['providers'][0]['configured'])
                self.assertFalse(rt.credential_ok(rt.configuration(env)['ANTHROPIC_API_KEY']))

    def test_empty_preset_name_is_rejected_not_defaulted(self):
        config, _ = rt.resources()
        for selector in ('triad', 'duo', 'profile'):
            with self.subTest(selector=selector), self.assertRaisesRegex(rt.HikmahError, 'unknown panel preset'):
                rt.select_members(config, **{selector: ''})
        self.assertEqual(rt.select_members(config), config['triads'][config['default_triad']]['members'])

    def test_system_instructions_state_the_enforced_response_limits(self):
        for phrase in ('expected_metadata', 'verbatim', 'one line of at most 6000 characters', 'at most 16 distinct entries',
                       'each one line of at most 4000 characters'):
            self.assertIn(phrase, rt.SYSTEM)
        self.assertEqual((rt.MAX_TEXT_CHARS, rt.MAX_LIST_ENTRIES, rt.MAX_LIST_ENTRY_CHARS), (6000, 16, 4000))

    def test_packet_output_survives_a_non_utf8_console(self):
        brief = json.loads((ROOT / 'examples/decision.json').read_text(encoding='utf-8'))
        brief['decision'] += ' Threshold ≥ 95% (non-ASCII fixture).'
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'brief.json')
            with open(path, 'w', encoding='utf-8') as handle:
                json.dump(brief, handle, ensure_ascii=False)
            stream = io.BytesIO()
            console = io.TextIOWrapper(stream, encoding='cp1252', errors='strict')
            with patch.object(sys, 'stdout', console):
                code = rt.main(['plan', '--brief', path])
            console.flush()
        self.assertEqual(code, 0)
        self.assertIn('≥ 95%', json.loads(stream.getvalue().decode('utf-8'))['brief']['decision'])


if __name__ == '__main__':
    unittest.main()
