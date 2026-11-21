
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from openai import OpenAI

TODAY = datetime.now(
    ZoneInfo("Europe/Paris")
).date().isoformat()

OUTPUT = Path("docs/signal.json")

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    timeout=240.0,
    max_retries=0
)

# Dernière édition pour éviter les répétitions
previous = {}
if OUTPUT.exists():
    try:
        previous = json.loads(
            OUTPUT.read_text(encoding="utf-8")
        )
    except (ValueError, OSError):
        pass

previous_titles = [
    x.get("title", "")
    for group in ("news", "readings")
    for x in previous.get(group, [])
]

prompt = f"""
Tu es le rédacteur en chef de THE SIGNAL,
Executive Intelligence Brief.

DATE : {TODAY}
LECTRICE : journaliste et consultante Tech,
spécialiste de l'économie, de l'industrie,
de l'innovation et des rapports de puissance.

OBJECTIF :
Sélectionner 3 actualités récentes et 2 lectures
exceptionnelles pour un widget iPhone.

Réalise une recherche web. Privilégie les
développements publiés ou confirmés dans les
48 dernières heures.

DOMAINES :
IA, industrie, semi-conducteurs, macroéconomie,
startups, capital-risque, cyber, renseignement,
espionnage, défense, géopolitique, deeptech.

SÉLECTION :
- Exactement 3 actualités importantes et distinctes.
- Au moins 2 grands domaines représentés.
- Aucun sujet répété entre les 3 actualités.
- Chaque actualité doit expliquer un fait nouveau.
- Évite les spéculations et les annonces secondaires.
- Préfère les faits chiffrés et documentés.

SOURCES :
Privilégie Reuters, FT, WSJ, médias français,
documents officiels, entreprises, régulateurs,
agences de renseignement et presse spécialisée.

N'invente aucun événement, chiffre ou article.
Ne présente jamais une accusation comme un fait.
Une source doit étayer précisément le titre.
Les événements extraordinaires exigent une
confirmation indépendante solide.
Si une information n'est pas suffisamment
étayée, sélectionne un autre sujet.

TITRES :
- Maximum 65 caractères pour chaque actualité.
- Maximum 48 caractères pour chaque lecture.
- Courts mais précis, en français pour les news.
- Ne coupe pas les titres avec "...".
- Pas de titres vagues ou sensationnalistes.
- Catégories de 35 caractères maximum.

READING ROOM :
Sélectionne 2 vrais articles de fond :
enquête, reportage, portrait ou analyse longue.
Privilégie The New Yorker, FT, WSJ,
Rest of World, MIT Technology Review,
Foreign Affairs ou des médias spécialisés.
Ils peuvent dater des 90 derniers jours.
Varie les médias et les disciplines.
Indique un titre abrégé fidèle à l'original.
Les URLs doivent mener aux articles précis.

ÉVITE AUTANT QUE POSSIBLE LES TITRES PRÉCÉDENTS :
{json.dumps(previous_titles, ensure_ascii=False)}

FORMAT :
Renvoie UNIQUEMENT un objet JSON valide,
sans commentaires ni Markdown.

{{
  "news": [
    {{
      "title": "Titre court",
      "category": "INDUSTRIE · TECH",
      "url": "https://source/article"
    }}
  ],
  "readings": [
    {{
      "title": "Titre court fidèle",
      "source": "THE NEW YORKER",
      "url": "https://media/article"
    }}
  ]
}}
"""

response = client.responses.create(
    model="gpt-5-mini",
    tools=[{"type": "web_search"}],
    tool_choice="required",
    input=prompt
)

raw = response.output_text.strip()

# Retirer d'éventuelles balises Markdown
if raw.startswith("```"):
    raw = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        raw,
        flags=re.IGNORECASE
    ).strip()

data = json.loads(raw)

# CONTRÔLES AVANT PUBLICATION

if not isinstance(data, dict):
    raise ValueError("Réponse JSON invalide")

news = data.get("news")
readings = data.get("readings")

if not isinstance(news, list) or len(news) != 3:
    raise ValueError("Il faut exactement 3 actualités")

if not isinstance(readings, list) or len(readings) != 2:
    raise ValueError("Il faut exactement 2 lectures")

seen_urls = set()
seen_titles = set()

for group, items, limit in [
    ("news", news, 65),
    ("readings", readings, 48)
]:
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Entrée invalide")

        title = item.get("title", "")
        url = item.get("url", "")

        if not isinstance(title, str) or not title.strip():
            raise ValueError("Titre manquant")

        if len(title) > limit:
            raise ValueError(
                f"Titre trop long ({len(title)} caractères)"
            )

        if "..." in title or "…" in title:
            raise ValueError("Titre tronqué")

        normalized = title.casefold().strip()
        if normalized in seen_titles:
            raise ValueError("Titre dupliqué")
        seen_titles.add(normalized)

        if not isinstance(url, str):
            raise ValueError("URL invalide")

        parsed = urlparse(url)

        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.path in ("", "/")
        ):
            raise ValueError("Lien trop générique : " + url)

        if url in seen_urls:
            raise ValueError("URL dupliquée")
        seen_urls.add(url)

        field = "category" if group == "news" else "source"

        if not isinstance(item.get(field), str):
            raise ValueError("Catégorie ou média manquant")

        if not item[field].strip():
            raise ValueError("Catégorie ou média vide")

        if group == "news" and len(item[field]) > 35:
            raise ValueError("Catégorie trop longue")

# Vérifier que les lectures ne sont pas
# exactement celles de l'édition précédente.
old_reading_urls = {
    x.get("url")
    for x in previous.get("readings", [])
}

if len(
    {x["url"] for x in readings} & old_reading_urls
) == 2:
    raise ValueError(
        "Les deux lectures répètent l'édition précédente"
    )

# Écriture uniquement après validation
data["date"] = TODAY
data["edition"] = "THE SIGNAL"

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

OUTPUT.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8"
)

print("THE SIGNAL :", TODAY)
print("Actualités :")
for item in news:
    print("-", item["title"])

print("Reading Room :")
for item in readings:
    print("-", item["title"])

print("Fichier généré avec succès.")
