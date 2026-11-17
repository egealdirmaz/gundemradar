#!/usr/bin/env python3
"""GündemRadar: 6-hour Turkish news mentions collector, no API key required.

Source priority: GDELT DOC TimelineVolRaw; if the whole run fails, Google News RSS.
Either source is used uniformly across people in a run. No fabricated counts.
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PEOPLE = ROOT / 'scripts' / 'people.json'
OUTPUT = ROOT / 'site' / 'data' / 'rankings.json'
GDELT_API = 'https://api.gdeltproject.org/api/v2/doc/doc'
GOOGLE_RSS = 'https://news.google.com/rss/search'
TRENDS_RSS = 'https://trends.google.com/trending/rss?geo=TR'
WIKIDATA_API = 'https://www.wikidata.org/w/api.php'
TREND_NS = {'ht': 'https://trends.google.com/trending/rss'}
UTC = dt.timezone.utc
HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; GundemRadar/0.2; news trend research)',
    'Accept': 'application/json, application/xml, text/xml, */*',
}


def tr_lower(text: str) -> str:
    """Türkçe karakter duyarlı küçük harfe çevirme (İ->i, I->ı)."""
    return text.replace('İ', 'i').replace('I', 'ı').lower()


def wikimedia_contact(env=None) -> str:
    """A public project URL or contact email for Wikimedia API identification."""
    env = os.environ if env is None else env
    explicit = env.get('GUNDEMRADAR_CONTACT', '').strip()
    if re.fullmatch(r'https?://\S+|[^@\s]+@[^@\s]+\.[^@\s]+', explicit):
        return explicit
    repo = env.get('GITHUB_REPOSITORY', '').strip()
    if re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        return f'https://github.com/{repo}'
    return ''


WIKIMEDIA_CONTACT = wikimedia_contact()
WIKIMEDIA_HEADERS = {
    'User-Agent': f'GundemRadar/0.2 ({WIKIMEDIA_CONTACT}; person discovery)',
    'Api-User-Agent': f'GundemRadar/0.2 ({WIKIMEDIA_CONTACT}; person discovery)',
    'Accept': 'application/json',
} if WIKIMEDIA_CONTACT else {}


def get_url(url: str, *, timeout: int = 18, max_attempts: int = 2, headers: dict | None = None) -> bytes:
    error = None
    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HTTP_HEADERS if headers is None else headers), timeout=timeout) as response:
                return response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
            error = e
            if attempt + 1 < max_attempts:
                if isinstance(e, urllib.error.HTTPError) and e.code not in (429, 500, 502, 503, 504):
                    break
                retry_after = e.headers.get('Retry-After') if isinstance(e, urllib.error.HTTPError) else None
                sleep_for = min(int(retry_after), 45) if retry_after and retry_after.isdigit() else 8 + 6 * attempt
                time.sleep(sleep_for)
    raise RuntimeError(f'İstek başarısız: {url.split("?")[0]} ({error})')


def parse_gdelt_date(value: str) -> dt.datetime:
    if len(value) == 16 and value.endswith('Z'):
        return dt.datetime.strptime(value, '%Y%m%dT%H%M%SZ').replace(tzinfo=UTC)
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(UTC)


def sum_timeline(payload: dict, now: dt.datetime) -> tuple[int, int]:
    if 'timeline' not in payload or not isinstance(payload['timeline'], list):
        raise ValueError('GDELT JSON timeline alanı içermiyor')
    current = previous = 0
    start = now - dt.timedelta(hours=48)
    divider = now - dt.timedelta(hours=24)
    for series in payload['timeline']:
        for point in series.get('data', []):
            at = parse_gdelt_date(str(point['date']))
            amount = max(0, int(round(float(point['value']))))
            if divider <= at <= now:
                current += amount
            elif start <= at < divider:
                previous += amount
    return current, previous


def gdelt_person(person: dict, now: dt.datetime) -> dict:
    query = f'"{person["name"]}" sourcelang:turkish'
    params = urllib.parse.urlencode({
        'query': query, 'mode': 'timelinevolraw', 'timespan': '2d', 'format': 'json'
    })
    body = get_url(GDELT_API + '?' + params)
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError('GDELT JSON olmayan yanıt verdi (erişim limiti veya hata olabilir)') from exc
    current, previous = sum_timeline(parsed, now)
    return {
        'name': person['name'],
        'category': person['category'],
        'count24h': current,
        'previous24h': previous,
        'headline': None,
        'headlineUrl': None,
        'articles': [],
        'discovered': bool(person.get('discovered', False)),
    }


def gdelt_articles(person: dict, limit: int = 10) -> list[dict]:
    query = f'"{person["name"]}" sourcelang:turkish'
    params = urllib.parse.urlencode({
        'query': query, 'mode': 'artlist', 'timespan': '1d', 'maxrecords': str(limit),
        'format': 'json', 'sort': 'datedesc'
    })
    parsed = json.loads(get_url(GDELT_API + '?' + params))
    articles, seen = [], set()
    wanted_name = tr_lower(person['name'])
    for article in parsed.get('articles', []):
        title = (article.get('title') or '').strip()
        url = (article.get('url') or '').strip()
        if not title or not url.startswith(('https://', 'http://')) or url in seen:
            continue
        if wanted_name not in tr_lower(title):
            continue
        articles.append({'title': title[:180], 'url': url})
        seen.add(url)
    return articles


def google_person(person: dict, now: dt.datetime) -> dict:
    phrase = person.get('googleQuery') or person['name']
    # Tek kelimelik isimlerde (Hadise, Sefo, Tarkan) cins isimlerle karışmaması için kategori ekle
    if len(phrase.split()) == 1 and not person.get('googleQuery'):
        cat = person.get('category', '')
        query_str = f'"{phrase}" ({cat} OR şarkıcı OR konser OR klip OR ünlü) when:2d'
    else:
        query_str = f'"{phrase}" when:2d'

    params = urllib.parse.urlencode({'q': query_str, 'hl': 'tr', 'gl': 'TR', 'ceid': 'TR:tr'})
    data = get_url(GOOGLE_RSS + '?' + params, timeout=20)
    root = ET.fromstring(data)
    if root.find('channel') is None:
        raise ValueError('Google News RSS kanal yanıtı bulunamadı')

    current = previous = 0
    newest_title = newest_url = None
    articles = []
    lower_limit = now - dt.timedelta(hours=48)
    mid = now - dt.timedelta(hours=24)
    seen = set()
    wanted_name = tr_lower(person['name'])

    for item in root.findall('./channel/item'):
        published = item.findtext('pubDate')
        if not published:
            continue
        at = email.utils.parsedate_to_datetime(published).astimezone(UTC)
        title = (item.findtext('title') or '').strip()
        url = (item.findtext('link') or '').strip()

        # KRİTİK FİLTRE: Ünlünün adı haber başlığında geçmiyorsa alakasız yan menü haberidir, atla.
        if wanted_name not in tr_lower(title):
            continue

        unique = (tr_lower(title), url)
        if unique in seen:
            continue
        seen.add(unique)

        if mid <= at <= now:
            current += 1
            if title and url.startswith(('https://', 'http://')):
                articles.append({'title': title[:180], 'url': url})
            if newest_title is None:
                newest_title, newest_url = title[:180], url
        elif lower_limit <= at < mid:
            previous += 1

    return {
        'name': person['name'],
        'category': person['category'],
        'count24h': current,
        'previous24h': previous,
        'headline': newest_title,
        'headlineUrl': newest_url,
        'articles': articles[:3],
        'discovered': bool(person.get('discovered', False)),
    }


def fetch_trends() -> list[dict]:
    """Google Trends Turkey RSS with related headlines; approximate traffic is not a universal search counter."""
    try:
        feed = ET.fromstring(get_url(TRENDS_RSS, timeout=12, max_attempts=1))
        trends = []
        for item in feed.findall('./channel/item'):
            title = (item.findtext('title') or '').strip()
            news_titles = [n.findtext('ht:news_item_title', default='', namespaces=TREND_NS)
                           for n in item.findall('ht:news_item', TREND_NS)]
            if title:
                trends.append({'title': title, 'newsTitles': [n.strip() for n in news_titles if n]})
        return trends
    except (RuntimeError, ET.ParseError) as exc:
        print(f'Google Trends alınamadı, ana liste devam ediyor: {exc}', file=sys.stderr)
        return []


def normalize_person_name(name: str) -> str:
    return ' '.join(tr_lower(name).split())


def name_candidates(titles: list[str]) -> list[str]:
    """Build 2-3 word proper-name candidates; external verification is still mandatory."""
    appearance = {}
    pattern = r'(?<![\w])[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)*'
    excluded = {
        'Son Dakika', 'Türk Sineması', 'Türkiye Sineması', 'Yeni Yıl', 'Sosyal Medya',
        'Google Trends', 'Ekşi Sözlük', 'Real Madrid', 'Fenerbahçe Spor', 'Milli Takım',
        'Hava Durumu', 'Canlı Yayın', 'Süper Lig', 'Anadolu Ajansı', 'Cumhuriyet Bayramı'
    }
    for text in titles:
        seen = set()
        for match in re.finditer(pattern, text):
            words = match.group(0).split()
            for n in (2, 3):
                for pos in range(len(words) - n + 1):
                    candidate = ' '.join(words[pos:pos + n])
                    if 6 <= len(candidate) <= 55 and candidate not in excluded:
                        seen.add(candidate)
        for candidate in seen:
            appearance[candidate] = appearance.get(candidate, 0) + 1
    return sorted(appearance, key=lambda v: (-appearance[v], len(v.split()), v))


def wikidata_human(name: str) -> bool:
    """A name is accepted only if an exact label/alias points to a Wikidata human (P31=Q5)."""
    if not WIKIMEDIA_CONTACT:
        raise RuntimeError('Wikidata erişimi için GUNDEMRADAR_CONTACT (e-posta / URL) gerekli')
    params = urllib.parse.urlencode({
        'action': 'wbsearchentities', 'search': name,
        'language': 'tr', 'uselang': 'tr', 'type': 'item',
        'limit': 5, 'format': 'json'
    })
    found = json.loads(get_url(WIKIDATA_API + '?' + params, timeout=12, max_attempts=1, headers=WIKIMEDIA_HEADERS))
    wanted = normalize_person_name(name)
    ids = []
    for hit in found.get('search', []):
        labels = [hit.get('label', ''), hit.get('match', {}).get('text', '')]
        if any(normalize_person_name(v) == wanted for v in labels):
            ids.append(hit['id'])
    if not ids:
        return False
    query = urllib.parse.urlencode({
        'action': 'wbgetentities', 'ids': '|'.join(ids[:3]),
        'props': 'claims', 'format': 'json'
    })
    entities = json.loads(get_url(WIKIDATA_API + '?' + query, timeout=12, max_attempts=1, headers=WIKIMEDIA_HEADERS)).get('entities', {})
    for entity in entities.values():
        claims = entity.get('claims', {}).get('P31', [])
        if any(c.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('id') == 'Q5' for c in claims):
            return True
    return False


def discover_people(trends: list[dict], headlines: list[str], known: list[dict], limit: int = 8) -> list[dict]:
    """Discover new names without a paid LLM; failures leave static monitored names intact."""
    if not WIKIMEDIA_CONTACT:
        print('Wikidata kişi keşfi atlandı: GUNDEMRADAR_CONTACT tanımlayın (GitHub Actions otomatik repo adresi kullanır).', file=sys.stderr)
        return []
    trend_names = name_candidates([t['title'] for t in trends])
    for trend in trends:
        title = trend['title'].strip()
        if title and title.islower() and len(title.split()) in (2, 3) and all(w.isalpha() for w in title.split()):
            words = []
            for word in title.split():
                words.append({'i': 'İ', 'ı': 'I'}.get(word[0], word[0].upper()) + word[1:])
            trend_names.append(' '.join(words))
    counts = {}
    for title in headlines + [h for t in trends for h in t['newsTitles']]:
        for candidate in set(name_candidates([title])):
            key = normalize_person_name(candidate)
            counts[key] = (candidate, counts.get(key, ('', 0))[1] + 1)
    repeated = [candidate for candidate, n in counts.values() if n >= 2]
    possibles = list(dict.fromkeys(trend_names + repeated))
    existing = {normalize_person_name(p['name']) for p in known}
    accepted, checked = [], 0
    for candidate in possibles:
        if normalize_person_name(candidate) in existing or checked >= 18 or len(accepted) >= limit:
            continue
        checked += 1
        try:
            if wikidata_human(candidate):
                accepted.append({'name': candidate, 'category': 'Gündemdeki isim', 'discovered': True})
                existing.add(normalize_person_name(candidate))
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            print(f'Yeni isim doğrulaması atlandı ({candidate}): {exc}', file=sys.stderr)
        time.sleep(0.75)
    return accepted


def calc_score(current: int, previous: int, trending: bool = False) -> float:
    """Conversation VOLUME dominates; growth can add at most 20%, Trends adds 5%."""
    if current <= 0:
        return 0.0
    ratio = (current + 5) / (previous + 5)
    boost = 0.20 * min(1.0, max(0.0, math.log2(ratio) / 3))
    return round(current * (1 + boost + (0.05 if trending else 0)), 2)


def build_history(previous_payload: dict, items: list[dict], now: dt.datetime) -> None:
    """Keep up to 10 successful snapshots for a lightweight inline chart."""
    old = {normalize_person_name(p['name']): p for p in previous_payload.get('items', [])}
    timestamp = now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    for item in items:
        past = old.get(normalize_person_name(item['name']), {})
        history = past.get('history', [])[-9:]
        item['history'] = (history + [{'at': timestamp, 'count': item['count24h']}])[-10:]
        item['previousRank'] = past.get('rank')


def finalize(items: list[dict], trends: list[dict], previous_payload: dict, now: dt.datetime) -> list[dict]:
    trending = [tr_lower(t['title']) for t in trends]
    for item in items:
        name = tr_lower(item['name'])
        item['googleTrending'] = any(name in t for t in trending)
        item['score'] = calc_score(item['count24h'], item['previous24h'], item['googleTrending'])
        if item.get('articles') and not item.get('headline'):
            item['headline'] = item['articles'][0]['title']
            item['headlineUrl'] = item['articles'][0]['url']
    items.sort(key=lambda x: (-x['score'], -x['count24h'], x['name']))
    build_history(previous_payload, items, now)
    for index, item in enumerate(items, 1):
        item['rank'] = index
        item['indexScore'] = round((100 * item['score'] / items[0]['score']), 1) if items[0]['score'] else 0
    return items


def fetch_all(people: list[dict], now: dt.datetime, mode: str, delay: float) -> list[dict]:
    result = []
    for i, person in enumerate(people):
        print(f'[{i+1:02d}/{len(people)}] {person["name"]} — {mode}', flush=True)
        if i and delay:
            time.sleep(delay)
        if mode == 'gdelt':
            item = gdelt_person(person, now)
        else:
            item = google_person(person, now)
        result.append(item)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', choices=['auto', 'gdelt', 'google'], default='auto',
                    help='auto: GDELT hata verirse tüm liste için Google News RSS')
    ap.add_argument('--dry-run', action='store_true', help='JSON yazma')
    ap.add_argument('--delay', type=float, default=5.5,
                    help='GDELT istekleri arasında saniye (hız sınırı için 5.5 önerilir)')
    args = ap.parse_args(argv)
    people = json.loads(PEOPLE.read_text(encoding='utf-8'))
    now = dt.datetime.now(UTC)
    previous_payload = {}
    if OUTPUT.exists():
        try:
            previous_payload = json.loads(OUTPUT.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            pass

    if len(people) != 50 or len({normalize_person_name(p['name']) for p in people}) != 50:
        print('Sabit test listesi tam 50 benzersiz kişi içermeli.', file=sys.stderr)
        return 1
    if any(p.get('discovered') for p in people):
        print('Sabit test listesinde otomatik keşif açık olmamalı.', file=sys.stderr)
        return 1

    source = 'gdelt'
    delay = max(0, args.delay)
    if args.source == 'google':
        items = fetch_all(people, now, 'google', 1.0)
        source = 'google_news_rss'
    else:
        try:
            items = fetch_all(people, now, 'gdelt', delay)
            source = 'gdelt_timelinevolraw'
        except (RuntimeError, ValueError, KeyError, ET.ParseError) as exc:
            if args.source == 'gdelt':
                print(f'GDELT başarısız: {exc}', file=sys.stderr)
                return 1
            print(f'GDELT taraması tamamlanamadı: {exc}. TÜM isimler için Google News RSS deneniyor.', file=sys.stderr)
            try:
                items = fetch_all(people, now, 'google', 1.0)
                source = 'google_news_rss'
            except (RuntimeError, ValueError, KeyError, ET.ParseError) as exc2:
                print(f'Yedek kaynak da başarısız. Eski veriyi koruyoruz: {exc2}', file=sys.stderr)
                return 1

    if not items or all(x['count24h'] == 0 and x['previous24h'] == 0 for x in items):
        print('Bütün isimlerin 48 saatlik verisi sıfır; güvenilmez tarama, eski dosyayı koruyoruz.', file=sys.stderr)
        return 1

    items.sort(key=lambda x: -x['count24h'])
    if source == 'gdelt_timelinevolraw':
        for item in items[:8]:
            try:
                time.sleep(delay)
                articles = gdelt_articles(item, limit=10)
                item['articles'] = articles[:3]
                item['headline'] = articles[0]['title'] if articles else None
                item['headlineUrl'] = articles[0]['url'] if articles else None
            except (RuntimeError, ValueError, KeyError) as exc:
                print(f'Manşet bulunamadı ({item["name"]}): {exc}', file=sys.stderr)

    trends = fetch_trends()
    for item in items:
        item.pop('_discovery_titles', None)

    comparison_base = previous_payload if previous_payload.get('rosterMode') == 'fixed_50_turkish_people' else {}
    items = finalize(items, trends, comparison_base, now)
    payload = {
        'status': 'ok',
        'updatedAt': now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
        'periodHours': 24,
        'refreshHours': 6,
        'source': source,
        'coverage': 'turkish_news',
        'sourceCaveat': (
            'GDELT Türkçe haber verileri; tüm medya veya sosyal ağları kapsamaz.'
            if source.startswith('gdelt') else
            'Google News RSS yedek veri; sonuçlar sınırlı olabilir, tam haber sayısı değildir.'
        ),
        'countedPeople': len(items),
        'rankingMethod': 'volume_plus_capped_growth',
        'discovery': 'disabled_fixed_turkish_roster',
        'rosterMode': 'fixed_50_turkish_people',
        'rosterSize': 50,
        'items': items,
    }
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:1800])
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(OUTPUT)
    print(f'Kaydedildi: {OUTPUT} ({source}, {len(items)} isim)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
