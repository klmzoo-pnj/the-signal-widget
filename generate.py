
import json
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from openai import OpenAI

TODAY = datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()
OUTPUT = Path("docs/signal.json")

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

prompt = f"""
Tu es le rédacteur de THE SIGNAL, une veille Executive
Intelligence pour une journaliste experte en technologie,
industrie, renseignement, géopolitique et économie.

Date à Paris : {TODAY}.

Effectue des recherches web sur les 48 dernières heures,
avec une attention particulière aux sources primaires,
Reuters, FT, WSJ, presse française et médias spécialisés.

Produis exactement :
- 3 actualités majeures, distinctes et vérifiables.
- 2 recommandations de lectures approfondies, récentes
  ou publiées au cours des trois derniers mois.

Recherche des faits précis, chiffres et dates.
N'invente jamais de chiffre, d'article ou de lien.
Distingue annonces, accusations et résultats établis.
Privilégie la diversité des thèmes.
Évite les doublons entre les cinq entrées.

Chaque titre d'actualité : 90 caractères maximum,
informatif et compréhensible sans contexte.
Les catégories : 35 caractères maximum.

Pour les lectures, privilégie The New Yorker,
Financial Times, WSJ, Rest of World, grandes enquêtes
et reportages industriels. Utilise un titre raccourci
de 65 caractères maximum pour le widget.

Chaque URL doit pointer vers une véritable page d'article
ou une source primaire, jamais la page d'accueil.

Réponds UNIQUEMENT en JSON valide, de cette forme :
{{
  "news": [
    {{
      "title": "Titre",
      "category": "INDUSTRIE · GÉOPOLITIQUE",
      "url": "https://..."
    }}
  ],
  "readings": [
    {{
      "title": "Titre court",
      "source": "THE NEW YORKER",
      "url": "https://..."
    }}
  ]
}}
"""

response = client.responses.create(
    model="gpt-5-mini",
    tools=[{"type": "web_search"}],
    tool_choice="required",
    text={"format": {"type": "json_object"}},
    input=prompt,
)

data = json.loads(response.output_text)

if not isinstance(data, dict):
    raise ValueError("Réponse JSON invalide")

if len(data.get("news", [])) != 3:
    raise ValueError("Il faut exactement 3 actualités")

if len(data.get("readings", [])) != 2:
    raise ValueError("Il faut exactement 2 lectures")

urls = set()

for item in data["news"] + data["readings"]:
    if not isinstance(item, dict):
        raise ValueError("Entrée invalide")

    url = item.get("url", "")
    parsed = urlparse(url)

    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("URL non valide : " + url)

    if parsed.path in ("", "/"):
        raise ValueError("Lien trop générique : " + url)

    if url in urls:
        raise ValueError("Lien dupliqué : " + url)
    urls.add(url)

    if not item.get("title"):
        raise ValueError("Titre manquant")

data["date"] = TODAY
data["edition"] = "THE SIGNAL"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8"
)

print(f"THE SIGNAL : {TODAY}")
print("3 actualités et 2 lectures générées")
