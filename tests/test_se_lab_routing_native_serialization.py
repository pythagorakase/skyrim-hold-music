"""Pinned public-seed reconstructions, never raw credential-bearing captures."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from hold_music import se_lab_skyrimnet_routing as routing


FIXTURES = Path(__file__).parent / 'fixtures'
HASHES = {
    'OpenRouter': '87f15080268d5bee81dd64f0dd73ea8de5fe33b053f0441b39781fd73e401179',
    'Providers': 'b26625cf5364f9dc6842d03530fab55be8c841c947eeb16077f6fadad0f34adf',
}
SECRET = 'PRIVATE-KEY-ENDPOINT-UNKNOWN-SENTINEL'


def raw_config():
    return [(FIXTURES/f'skyrimnet-beta26-rc4-public-{name}.json').read_bytes()
            for name in ('OpenRouter', 'Providers')]


def documents():
    return [json.loads(raw) for raw in raw_config()]


def audit(docs):
    return routing._audit_graph([json.dumps(doc, separators=(',', ':')).encode() for doc in docs]
        + [b'{"fields":[]}', b'{"fields":[]}'])


class NativeSerializationTests(unittest.TestCase):
    def test_public_reconstruction_matches_retained_config_hashes_and_counts(self):
        raw = raw_config()
        self.assertEqual([len(b) for b in raw], [2155, 1813])
        self.assertEqual([hashlib.sha256(b).hexdigest() for b in raw], list(HASHES.values()))
        result = routing._audit_graph(raw + [b'{"fields":[]}', b'{"fields":[]}'])
        self.assertEqual(result['issues'], [])
        self.assertTrue(result['configured_graph_fake_only'])
        self.assertEqual(result['native_serialization_normalization'], {
            'contract': 'beta26-rc4-sparse-save-to-node-v1',
            'counts': {'provider_empty_api_key_from': 6, 'routing_empty_profile': 1,
                'routing_empty_quantization_floor': 1, 'routing_default_ttft_multiplier': 1,
                'routing_default_ttft_floor': 1, 'base_empty_stop_sequences': 1,
                'variant_empty_stop_sequences': 1}})
        for key in ('native_fallback_verified', 'native_inheritance_verified',
                    'actor_group_overrides_verified', 'diagnostic_ready', 'egress_verified'):
            self.assertFalse(result[key], key)
        self.assertEqual(result['counts']['passthrough_nulls'], 10)
        self.assertEqual(result['counts']['providers'], 6)
        self.assertEqual(result['counts']['slots'], 2)
        self.assertEqual(result['counts']['disabled_slots'], 1)

    def test_explicit_values_never_replaced_by_omission_defaults(self):
        cases = [('profile',None), ('profile',SECRET), ('quantization_floor',None),
            ('quantization_floor',SECRET), ('ttft_abort_multiplier',None),
            ('ttft_abort_multiplier',False), ('ttft_abort_multiplier',-1),
            ('ttft_abort_floor_ms',None), ('ttft_abort_floor_ms',False),
            ('ttft_abort_floor_ms',-1), ('ttft_abort_floor_ms',2.5)]
        for key,value in cases:
            docs=documents();docs[0]['data']['routing'][key]=value
            with self.subTest(key=key,value=value):
                result=audit(docs)
                self.assertFalse(result['configured_graph_fake_only'])
                self.assertNotIn(SECRET,json.dumps(result))

    def test_other_missing_routing_controls_never_get_safe_defaults(self):
        for key in ('mode','ttft_early_abort','ttft_abort_ceiling_ms',
                    'local_slow_demote','ttft_race_first_token'):
            docs=documents();del docs[0]['data']['routing'][key]
            with self.subTest(key=key):
                self.assertFalse(audit(docs)['configured_graph_fake_only'])

    def test_unsafe_routing_values_remain_rejected(self):
        for key,value in [('mode','smart'),('mode','directive'),('ttft_early_abort',True),
                          ('local_slow_demote',True),('ttft_race_first_token',True)]:
            docs=documents();docs[0]['data']['routing'][key]=value
            with self.subTest(key=key):
                self.assertIn('unsupported_routing_policy',audit(docs)['issues'])

    def test_explicit_bad_lender_and_missing_or_null_credentials_still_rejected(self):
        for key,value in [('api_key_from',None),('api_key_from',SECRET),
                          ('endpoint',None),('endpoint',SECRET),('api_key',None),('api_key',SECRET)]:
            docs=documents();docs[1]['data']['providers'][0][key]=value
            with self.subTest(key=key,value=value):
                result=audit(docs)
                self.assertFalse(result['configured_graph_fake_only'])
                self.assertNotIn(SECRET,json.dumps(result))
        for key in ('api_key','endpoint','id','api_style','use_sse'):
            docs=documents();del docs[1]['data']['providers'][0][key]
            with self.subTest(missing=key):
                self.assertFalse(audit(docs)['configured_graph_fake_only'])

    def test_null_slot_control_and_stop_sequence_never_normalized(self):
        for variant in (False, True):
            for key in ('ttft_abort_multiplier','ttft_abort_floor_ms','request_timeout',
                        'connect_timeout','max_retries','stop_sequences','rotation_weight'):
                docs=documents();rotation=docs[0]['data']['openrouter']
                if variant:rotation=rotation['variants']['decisions']
                rotation['model_params'][0][key]=None
                with self.subTest(variant=variant,key=key):
                    self.assertFalse(audit(docs)['configured_graph_fake_only'])

    def test_default_stop_sequence_normalization_is_typed_and_path_scoped(self):
        for variant in (False,True):
            for value in ('',SECRET,False,0,{},[None]):
                docs=documents();rotation=docs[0]['data']['openrouter']
                if variant:rotation=rotation['variants']['decisions']
                rotation['default_params']['stop_sequences']=value
                with self.subTest(variant=variant,value=value):
                    self.assertIn('invalid_typed_value',audit(docs)['issues'])
        docs=documents();docs[0]['data']['routing']['stop_sequences']=None
        self.assertIn('unsupported_fields',audit(docs)['issues'])

    def test_missing_defaults_container_and_unknown_neighbor_field_still_rejected(self):
        docs=documents();del docs[0]['data']['openrouter']['default_params']
        self.assertIn('malformed_graph',audit(docs)['issues'])
        docs=documents();docs[0]['data']['routing'][SECRET]=None
        result=audit(docs)
        self.assertIn('unsupported_fields',result['issues'])
        self.assertNotIn(SECRET,json.dumps(result))

    def test_explicit_equivalent_values_do_not_report_native_normalization(self):
        docs=documents();root=docs[0]['data']
        root['routing'].update(profile='',quantization_floor='',ttft_abort_multiplier=2.0,
                               ttft_abort_floor_ms=2500)
        for provider in docs[1]['data']['providers']:provider['api_key_from']=''
        for rotation in [root['openrouter'],*root['openrouter']['variants'].values()]:
            rotation['default_params']['stop_sequences']=[]
        before=copy.deepcopy(docs)
        result=audit(docs)
        self.assertTrue(result['configured_graph_fake_only'])
        self.assertFalse(any(result['native_serialization_normalization']['counts'].values()))
        self.assertEqual(before,docs)


if __name__ == '__main__':
    unittest.main()
