
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from openai import OpenAI


# ==========================================
# THE SIGNAL — EXECUTIVE INTELLIGENCE BRIEF
# Génération quotidienne de la veille
# ==========================================

TODAY = datetime.now(
    ZoneInfo("Europe/Paris")
).date().isoformat()

OUT = Path("docs/signal.json")


# ==========================================
# INSTRUCTIONS ÉDITORIALES
# ==========================================

prompt = f"""
Tu es la rédaction en chef de THE SIGNAL,
une veille quotidienne exécutive en français.

Date de référence : {TODAY}, heure de Paris.

Effectue une recherche web réelle et récente.

DOMAINES :
Technologie, intelligence artificielle, startups,
capital-risque, économie, marchés, géopolitique,
cybersécurité, renseignement, espionnage, défense,
industrie, innovation et chaînes d'approvisionnement.

LIGNE ÉDITORIALE :
- Sélectionner les faits stratégiques les plus importants.
- Privilégier la précision, la pertinence et la diversité.
- Identifier les rapports de force et les conséquences.
- Éviter le sensationnalisme et les répétitions.
- Donner la priorité aux faits nouveaux et documentés.

SOURCES :
Reuters, AP, Financial Times, Wall Street Journal,
The New Yorker, Rest of World, sources officielles,
rapports institutionnels et presse spécialisée fiable.

Chaque URL doit soutenir précisément le fait annoncé.

N'invente jamais de noms, de chiffres, de sommets,
d'introductions en Bourse, d'acquisitions ou d'articles.

Distingue systématiquement :
- Les faits confirmés.
- Les négociations en cours.
- Les projets et annonces.
- Les accusations non encore établies.
- Les analyses et hypothèses.

PÉRIODE :
Actualités des 72 dernières heures si possible,
jusqu'à 7 jours pour les développements importants.

Reading Room : articles publiés dans les 90
derniers jours, avec préférence pour les enquêtes
et les grands reportages.

STRUCTURE OBLIGATOIRE :

1. critical
Exactement 5 objets :
{{title, category, summary, url}}

summary : 45 à 75 mots.
Présenter les faits, les chiffres essentiels
et expliquer pourquoi l'information compte.

Les 3 premiers titres doivent contenir
54 caractères maximum.

2. radar
Exactement 8 objets :
{{title, category, summary, url}}

summary : 20 à 35 mots.
Signaux brefs, précis et différents des
5 développements principaux.

3. intelligence
Exactement 2 objets :
{{title, category, summary, url}}

summary : 40 à 65 mots.
Renseignement, cyber, défense ou capacités
industrielles sensibles.

4. data_points
Exactement 4 objets :
{{label, value, context, url}}

RÈGLE IMPÉRATIVE :
Chaque objet data_points DOIT contenir
ces quatre champs, tous remplis :

- "label" : nom de l'indicateur.
- "value" : valeur chiffrée sous forme de texte.
- "context" : explication et périmètre du chiffre.
- "url" : lien HTTPS vers la source.

Exemple de structure :
{{
  "label": "Financement européen",
  "value": "290 M€",
  "context": "Montant des appels à projets annoncés.",
  "url": "https://commission.europa.eu/..."
}}

Ne remplace JAMAIS "value" par :
"figure", "number", "metric", "stat" ou "amount".

Ne renvoie jamais un objet sans "value".
Si une donnée est insuffisamment documentée,
sélectionne un autre indicateur vérifiable.

5. reading_room
Exactement 5 objets :
{{title, source, why_read, url}}

Sélectionner des enquêtes, reportages,
essais et analyses de fond.

why_read : 20 à 40 mots.

Les 2 premiers titres doivent contenir
48 caractères maximum.

Privilégier les lectures originales et les
médias reconnus pour leurs enquêtes.

6. editorial
Un objet :
{{title, text}}

text : 60 à 90 mots.
Une réflexion stratégique originale,
fondée sur les informations de l'édition.
Bien distinguer les analyses des faits.

RÈGLES FINALES :
- Aucun doublon entre les rubriques.
- URLs HTTPS vers les articles précis.
- Pas de liens vers les pages d'accueil.
- Les 3 premières actualités doivent couvrir
  au moins 2 domaines différents.
- Aucun point de suspension dans les titres
  destinés au widget.
- Ne pas inventer de faits pour remplir une rubrique.
- Respecter rigoureusement les noms des champs JSON.
- Vérifier les 4 objets data_points avant de répondre.
- Retourner UNIQUEMENT un objet JSON valide.
- Aucun commentaire, aucune balise Markdown.
"""


# ==========================================
# APPEL OPENAI
# ==========================================

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    timeout=300.0,
    max_retries=1
)

response = client.responses.create(
    model="gpt-5-mini",
    tools=[{"type": "web_search"}],
    tool_choice="required",
    input=prompt
)

raw = response.output_text.strip()

# Supprimer les éventuelles balises Markdown
if raw.startswith("```"):
    raw = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        raw,
        flags=re.I
    ).strip()

data = json.loads(raw)


# ==========================================
# VALIDATION DES RUBRIQUES
# ==========================================

def validate_section(name, count, fields):

    items = data.get(name)

    if not isinstance(items, list) or len(items) != count:
        raise ValueError(
            f"{name}: attendu {count} éléments"
        )

    for index, item in enumerate(items):

        if not isinstance(item, dict):
            raise ValueError(
                f"{name}[{index}]: élément non objet"
            )

        for field in fields:

            value = item.get(field)

            if (
                not isinstance(value, str)
                or not value.strip()
            ):
                raise ValueError(
                    f"{name}[{index}]: champ manquant {field}"
                )

        parsed = urlparse(item["url"])

        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.path in ("", "/")
        ):
            raise ValueError(
                f"{name}: URL invalide {item['url']}"
            )

    return items


critical = validate_section(
    "critical",
    5,
    ["title", "category", "summary", "url"]
)

radar = validate_section(
    "radar",
    8,
    ["title", "category", "summary", "url"]
)

intel = validate_section(
    "intelligence",
    2,
    ["title", "category", "summary", "url"]
)

points = validate_section(
    "data_points",
    4,
    ["label", "value", "context", "url"]
)

readings = validate_section(
    "reading_room",
    5,
    ["title", "source", "why_read", "url"]
)


# ==========================================
# VALIDATION DE L'ÉDITORIAL
# ==========================================

if (
    not isinstance(data.get("editorial"), dict)
    or not all(
        isinstance(data["editorial"].get(k), str)
        and data["editorial"][k].strip()
        for k in ["title", "text"]
    )
):
    raise ValueError("Editorial manquant")


# ==========================================
# CONTRÔLE DES TITRES DU WIDGET
# ==========================================

for section, limit in [
    (critical[:3], 54),
    (readings[:2], 48)
]:
    for item in section:

        title = item["title"]

        if (
            len(title) > limit
            or "…" in title
            or "..." in title
        ):
            raise ValueError(
                "Titre widget trop long : " + title
            )


# ==========================================
# CONTRÔLE DES DOUBLONS
# ==========================================

seen = set()

for item in critical + radar + intel + readings:

    url = item["url"]

    if url in seen:
        raise ValueError(
            "Lien dupliqué : " + url
        )

    seen.add(url)


# ==========================================
# COMPATIBILITÉ AVEC SCRIPTABLE
# ==========================================

# Les trois premiers développements
# alimentent le widget iPhone.

data["news"] = [
    {
        "title": x["title"],
        "category": x["category"],
        "url": x["url"]
    }
    for x in critical[:3]
]

# Les deux premières lectures
# alimentent la Reading Room du widget.

data["readings"] = [
    {
        "title": x["title"],
        "source": x["source"],
        "url": x["url"]
    }
    for x in readings[:2]
]


# ==========================================
# DATE ET IDENTITÉ ÉDITORIALE
# ==========================================

data["date"] = TODAY
data["edition"] = "THE SIGNAL"


# ==========================================
# PUBLICATION
# ==========================================

# Aucun fichier n'est remplacé si une
# validation précédente a échoué.

OUT.parent.mkdir(
    parents=True,
    exist_ok=True
)

OUT.write_text(
    json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    ) + "\n",
    encoding="utf-8"
)

print("THE SIGNAL publiée :", TODAY)

print(
    "5 développements / "
    "8 Radar / "
    "2 signaux / "
    "4 chiffres / "
    "5 lectures"
)

print("Titres du widget :")

for item in data["news"]:
    print("-", item["title"])

print("Reading Room :")

for item in data["readings"]:
    print("-", item["title"])
