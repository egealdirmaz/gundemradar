import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect

class CollectorTests(unittest.TestCase):
    def test_legacy_timestamp_and_two_windows(self):
        now = dt.datetime(2026,11,17,18,0,tzinfo=dt.timezone.utc)
        payload = {'timeline': [{'data': [
            {'date':'20261117T170000Z','value':18},
            {'date':'20261117T050000Z','value':7},
            {'date':'20261116T170000Z','value':4},
            {'date':'20261115T130000Z','value':100}
        ]}]}
        self.assertEqual(collect.sum_timeline(payload,now),(25,4))
    def test_empty_valid_timeline(self):
        now = dt.datetime(2026,11,17,tzinfo=dt.timezone.utc)
        self.assertEqual(collect.sum_timeline({'timeline':[]},now),(0,0))
    def test_missing_timeline_rejected(self):
        with self.assertRaises(ValueError):
            collect.sum_timeline({},dt.datetime.now(dt.timezone.utc))
    def test_date_with_colons(self):
        self.assertEqual(collect.parse_gdelt_date('2026-11-17T12:00:00Z').hour,12)

if __name__ == '__main__':unittest.main()

class RankingV2Tests(unittest.TestCase):
    def test_volume_wins_over_small_sample_growth(self):
        self.assertGreater(collect.calc_score(500, 470),collect.calc_score(20, 2))
    def test_fast_rising_person_can_overtake_similar_volume(self):
        self.assertGreater(collect.calc_score(150, 5),collect.calc_score(140, 140))
    def test_no_score_for_zero_articles(self):
        self.assertEqual(collect.calc_score(0, 0, True), 0)
    def test_candidate_extraction(self):
        candidates=collect.name_candidates(['Haluk Bilginer Türkiye Sineması sözleri yeniden gündemde', 'Haluk Bilginer sözleri gündem oldu'])
        self.assertIn('Haluk Bilginer',candidates)
        self.assertNotIn('Türkiye Sineması',candidates)
    def test_finalize_ranks_by_score(self):
        when = dt.datetime(2026, 11, 17, 12, tzinfo=dt.timezone.utc)
        data=[{'name':'Test Alfa','count24h':150,'previous24h':5,'articles':[]},
              {'name':'Test Beta','count24h':140,'previous24h':140,'articles':[]}]
        out=collect.finalize(data, [], {}, when)
        self.assertEqual(out[0]['name'],'Test Alfa')
        self.assertEqual(out[0]['indexScore'],100)
        self.assertEqual(out[0]['rank'],1)

class WikimediaContactTests(unittest.TestCase):
    def test_github_actions_repository_is_contact_url(self):
        self.assertEqual(collect.wikimedia_contact({'GITHUB_REPOSITORY': 'example-user/gundemradar'}), 'https://github.com/example-user/gundemradar')
    def test_explicit_email_takes_priority(self):
        env = {'GUNDEMRADAR_CONTACT': 'contact@example.org', 'GITHUB_REPOSITORY': 'user/repo'}
        self.assertEqual(collect.wikimedia_contact(env), 'contact@example.org')
    def test_no_fake_contact_when_missing(self):
        self.assertEqual(collect.wikimedia_contact({}), '')

class TurkishRosterTests(unittest.TestCase):
    def test_exact_50_unique_people(self):
        import json
        people = json.loads(collect.PEOPLE.read_text(encoding='utf-8'))
        self.assertEqual(len(people), 50)
        self.assertEqual(len({collect.normalize_person_name(p['name']) for p in people}), 50)
        self.assertFalse(any(p.get('discovered') for p in people))
        self.assertNotIn('James Bond', {p['name'] for p in people})
        self.assertNotIn('Mauro Icardi', {p['name'] for p in people})

    def test_fixed_mode_prevents_extra_discoveries(self):
        from unittest.mock import patch
        import json
        import tempfile
        from pathlib import Path
        import datetime as dt
        people = json.loads(collect.PEOPLE.read_text(encoding='utf-8'))
        now=dt.datetime(2026, 11, 17, 19, tzinfo=dt.timezone.utc)
        fake_items=[dict(name=p['name'],category=p['category'],count24h=i+1,previous24h=i,articles=[]) for i,p in enumerate(people)]
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'rankings.json'
            out.write_text(json.dumps({'updatedAt':'2026-11-17T17:00:00Z', 'items':[{'name':'James Bond','discovered':True,'count24h':90}]}),encoding='utf-8')
            with patch.object(collect, 'OUTPUT', out), patch.object(collect,'fetch_all',return_value=fake_items), patch.object(collect,'fetch_trends',return_value=[]), patch.object(collect,'discover_people',side_effect=AssertionError('Discovery must not run')):
                with patch('sys.argv', ['collect.py','--source','google']):
                    self.assertEqual(collect.main(),0)
            output=json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual(len(output['items']),50)
            self.assertEqual(output['rosterMode'],'fixed_50_turkish_people')
            self.assertNotIn('James Bond',[v['name'] for v in output['items']])
            self.assertTrue(all(v['previousRank'] is None for v in output['items']))
