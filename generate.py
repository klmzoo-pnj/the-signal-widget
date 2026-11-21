import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from openai import OpenAI

TODAY = datetime.now(ZoneInfo('Europe/Paris')).date().isoformat()
OUT = Path('docs/signal.json')

prompt = f'''Tu es la rédaction de THE SIGNAL, veille quotidienne exécutive en français.
Date de référence {TODAY} (heure de Paris). Effectue une recherche web réelle et récente.
Concentre-toi sur technologie, IA, startups, capital, économie, géopolitique,
cybersécurité, intelligence, défense, industrie et chaînes d'approvisionnement.
Sources primaires et médias sérieux (Reuters, AP, FT, WSJ, The New Yorker,
Rest of World, sources officielles) ; donne pour chaque élément une URL HTTPS
qui soutient EXACTEMENT le fait annoncé. N'invente jamais de noms, chiffres,
sommets, IPO, acquisitions ou publications. Distingue négociations, projets,
accusations et faits avérés. Actualités dans les 72 dernières heures si
possible, jusqu'à 7 jours si nécessaire. Pour les lectures : 90 derniers jours.
Évite tout doublon entre rubriques. Sois précis, sobre et analytique.

Génère UNIQUEMENT un objet JSON valide, sans Markdown, avec ces champs :
- critical : exactement 5 objets {{title, category, summary, url}} ;
  summary = 45-75 mots, faits et pourquoi cela compte ;
  les TROIS premiers title doivent faire 54 caractères maximum ;
- radar : exactement 8 objets {{title, category, summary, url}} ;
  summary = 20-35 mots ;
- intelligence : exactement 2 objets {{title, category, summary, url}} ;
  summary = 40-65 mots ;
- data_points : exactement 4 objets {{label, value, context, url}} ;
  value chiffrée, context explique périmètre et signification ;
- reading_room : exactement 5 objets {{title, source, why_read, url}} ;
  deux premiers title de 48 caractères maximum, lectures de fond variées,
  why_read de 20-40 mots ;
- editorial : objet {{title, text}} ; text = réflexion originale 60-90 mots.
Les URLs doivent mener à des pages d'articles ou documents, pas à des accueils.
Les 3 critical du widget couvrent au moins deux domaines différents.
N'utilise jamais les points de suspension dans les 3 premiers titres
ni les 2 premières lectures. En cas d'incertitude, choisis un autre sujet.
'''

client = OpenAI(api_key=os.environ['OPENAI_API_KEY'], timeout=300.0, max_retries=1)
response = client.responses.create(
    model='gpt-5-mini',
    tools=[{'type': 'web_search'}],
    tool_choice='required',
    input=prompt,
)
raw = response.output_text.strip()
if raw.startswith('```'):
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.I).strip()
data = json.loads(raw)

def validate_section(name, n, fields):
    items = data.get(name)
    if not isinstance(items, list) or len(items) != n:
        raise ValueError(f'{name}: attendu {n} éléments')
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f'{name}: élément non objet')
        for field in fields:
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f'{name}: champ manquant {field}')
        parsed = urlparse(item['url'])
        if parsed.scheme != 'https' or not parsed.netloc or parsed.path in ('', '/'):
            raise ValueError(f'{name}: URL invalide {item["url"]}')
    return items

critical = validate_section('critical', 5, ['title','category','summary','url'])
radar = validate_section('radar', 8, ['title','category','summary','url'])
intel = validate_section('intelligence', 2, ['title','category','summary','url'])
points = validate_section('data_points', 4, ['label','value','context','url'])
readings = validate_section('reading_room', 5, ['title','source','why_read','url'])
if not isinstance(data.get('editorial'), dict) or not all(
    isinstance(data['editorial'].get(k), str) and data['editorial'][k].strip()
    for k in ['title','text']
):
    raise ValueError('Editorial manquant')

for section, limit in [(critical[:3], 54),(readings[:2], 48)]:
    for item in section:
        if len(item['title']) > limit or '…' in item['title'] or '...' in item['title']:
            raise ValueError('Titre widget trop long : ' + item['title'])

seen = set()
for item in critical + radar + intel + readings:
    if item['url'] in seen:
        raise ValueError('Lien dupliqué : ' + item['url'])
    seen.add(item['url'])

# Compatibilité avec le widget Scriptable actuel
# (il n'utilise que ces deux listes, la date et l'édition).
data['news'] = [
    {'title': x['title'], 'category': x['category'], 'url': x['url']}
    for x in critical[:3]
]
data['readings'] = [
    {'title': x['title'], 'source': x['source'], 'url': x['url']}
    for x in readings[:2]
]
data['date'] = TODAY
data['edition'] = 'THE SIGNAL'

OUT.parent.mkdir(parents=True, exist_ok=True)
# En cas d'échec de validation, le dernier JSON reste intact.
OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('THE SIGNAL publiée :', TODAY)
print('5 développements / 8 Radar / 2 signaux / 4 chiffres / 5 lectures')
