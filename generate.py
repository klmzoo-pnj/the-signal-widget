
#!/usr/bin/env python3
"""THE SIGNAL — veille complète + widget Scriptable."""

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

OUT = Path("docs/signal.json")


# ==========================================
# CONSIGNES DE GÉNÉRATION
# ==========================================

PROMPT = f"""
Tu es la rédaction de THE SIGNAL,
Executive Intelligence Brief en français.

Date : {TODAY}, fuseau Europe/Paris.

Effectue une recherche web réelle.

Sujets : technologie, IA, startups/VC,
macroéconomie, marchés, cybersécurité,
renseignement, géopolitique, défense,
industrie et chaînes d'approvisionnement.

Privilégie Reuters, AP, FT, WSJ,
sources officielles, The New Yorker,
Rest of World et médias spécialisés fiables.

VÉRIFICATION :
- Chaque URL HTTPS doit étayer le titre précis.
- N'invente aucun événement, chiffre ou article.
- Distingue faits, projets, négociations et accusations.
- Actualités : 72 heures, jusqu'à 7 jours si nécessaire.
- Lectures : articles de fond des 90 derniers jours.
- Évite les doublons et varie les domaines.
- Si les sources sont insuffisantes, produis moins
  d'éléments plutôt que d'inventer.
- Tous les champs doivent être remplis.

Renvoie UNIQUEMENT un objet JSON valide,
sans commentaire ni balise Markdown.

STRUCTURE :

"critical" :
Idéalement 5 objets, minimum 3.
Champs obligatoires :
{{"title":"...", "category":"...",
  "summary":"...", "url":"https://..."}}
Les 3 premiers titres : 54 caractères maximum.
Résumé : 45 à 75 mots, avec pourquoi cela compte.

"radar" :
Idéalement 8 objets, entre 6 et 10 acceptés.
Champs :
{{"title":"...", "category":"...",
  "summary":"...", "url":"https://..."}}
Résumé : 20 à 35 mots.

"intelligence" :
Idéalement 2 objets, entre 1 et 3 acceptés.
Champs :
{{"title":"...", "category":"...",
  "summary":"...", "url":"https://..."}}
Renseignement, défense, cyber ou industrie.

"data_points" :
Idéalement 4 objets, entre 3 et 6 acceptés.

Chaque objet doit avoir ces quatre clés EXACTES :
{{"label":"...", "value":"290 M€",
  "context":"...", "url":"https://..."}}

La valeur "value" doit être une CHAÎNE
contenant un chiffre vérifiable.
N'utilise pas figure, amount, metric ou number
à la place de la clé "value".
Le contexte précise la période et le périmètre.

"reading_room" :
Idéalement 5 objets, minimum 2.
Champs :
{{"title":"...", "source":"...",
  "why_read":"...", "url":"https://..."}}
Les 2 premiers titres : 48 caractères maximum.
Sélectionne enquêtes, reportages et analyses de fond.

"editorial" :
Un objet :
{{"title":"...", "text":"..."}}
Réflexion stratégique originale de 60 à 90 mots.

Évite les points de suspension dans les titres
destinés au widget.

Vérifie les noms des champs avant de répondre.
"""


# ==========================================
# OUTILS DE VALIDATION
# ==========================================

def valid_url(value):
    if not isinstance(value, str):
        return False

    u = urlparse(value.strip())

    return (
        u.scheme == "https"
        and bool(u.netloc)
        and u.path not in ("", "/")
        and "example." not in u.netloc.lower()
    )


def nonempty_text(value):
    return (
        isinstance(value, str)
        and bool(value.strip())
    )


def compact_title(text, max_length):
    """Produit un titre court sans points de suspension."""

    text = " ".join(text.split())
    text = text.replace("…", "").replace("...", "")

    if len(text) <= max_length:
        return text

    short = text[:max_length + 1].rsplit(" ", 1)[0]
    short = short.rstrip(" ,;:-")

    return short if short else text[:max_length]


def normalize_entries(
    data,
    name,
    fields,
    minimum,
    maximum
):
    raw = data.get(name, [])

    if not isinstance(raw, list):
        raise ValueError(
            f"{name}: liste JSON attendue"
        )

    cleaned = []
    seen = set()

    for i, item in enumerate(raw):

        if not isinstance(item, dict):
            print(
                f"AVERTISSEMENT : {name}[{i}] ignoré "
                "(pas un objet)"
            )
            continue

        item = dict(item)

        # Corrige certains noms de champs évidents,
        # mais n'invente jamais de valeur.

        if (
            name == "data_points"
            and not nonempty_text(item.get("value"))
        ):
            for alias in (
                "figure",
                "amount",
                "number",
                "stat"
            ):
                candidate = item.get(alias)

                if (
                    isinstance(candidate, (int, float))
                    and not isinstance(candidate, bool)
                ):
                    item["value"] = str(candidate)
                    break

                if nonempty_text(candidate):
                    item["value"] = candidate.strip()
                    break

        if not all(
            nonempty_text(item.get(field))
            for field in fields
        ):
            print(
                f"AVERTISSEMENT : {name}[{i}] ignoré "
                "(champ manquant)"
            )
            continue

        if not valid_url(item["url"]):
            print(
                f"AVERTISSEMENT : {name}[{i}] ignoré "
                "(URL invalide)"
            )
            continue

        if (
            name == "data_points"
            and not re.search(r"\d", item["value"])
        ):
            print(
                f"AVERTISSEMENT : {name}[{i}] ignoré "
                "(chiffre absent)"
            )
            continue

        item = {
            field: item[field].strip()
            for field in fields
        }

        url = item["url"]

        if url in seen:
            print(
                f"AVERTISSEMENT : {name}[{i}] ignoré "
                "(URL répétée)"
            )
            continue

        seen.add(url)
        cleaned.append(item)

    if len(cleaned) < minimum:
        raise ValueError(
            f"{name}: seulement {len(cleaned)} "
            f"éléments valides (minimum {minimum}). "
            "Ancienne édition conservée."
        )

    if len(cleaned) > maximum:
        print(
            f"INFO : {name} réduit "
            f"de {len(cleaned)} à {maximum} éléments"
        )
        cleaned = cleaned[:maximum]

    return cleaned


# ==========================================
# CONSTRUCTION DE L'ÉDITION
# ==========================================

def build_edition(data):

    if not isinstance(data, dict):
        raise ValueError(
            "Réponse JSON : objet attendu"
        )

    critical = normalize_entries(
        data,
        "critical",
        ("title", "category", "summary", "url"),
        3,
        5
    )

    radar = normalize_entries(
        data,
        "radar",
        ("title", "category", "summary", "url"),
        6,
        10
    )

    intelligence = normalize_entries(
        data,
        "intelligence",
        ("title", "category", "summary", "url"),
        1,
        3
    )

    data_points = normalize_entries(
        data,
        "data_points",
        ("label", "value", "context", "url"),
        3,
        6
    )

    reading_room = normalize_entries(
        data,
        "reading_room",
        ("title", "source", "why_read", "url"),
        2,
        5
    )

    editorial = data.get("editorial")

    if (
        not isinstance(editorial, dict)
        or not all(
            nonempty_text(editorial.get(field))
            for field in ("title", "text")
        )
    ):
        raise ValueError(
            "editorial: titre ou texte manquant"
        )

    # Sélection courte pour le widget iPhone

    news = [
        {
            "title": compact_title(
                item["title"], 54
            ),
            "category": item["category"],
            "url": item["url"]
        }
        for item in critical[:3]
    ]

    readings = [
        {
            "title": compact_title(
                item["title"], 48
            ),
            "source": item["source"],
            "url": item["url"]
        }
        for item in reading_room[:2]
    ]

    # Structure compatible avec le site et Scriptable

    return {
        "critical": critical,
        "radar": radar,
        "intelligence": intelligence,
        "data_points": data_points,
        "reading_room": reading_room,
        "editorial": {
            "title": editorial["title"].strip(),
            "text": editorial["text"].strip()
        },
        "news": news,
        "readings": readings,
        "date": TODAY,
        "edition": "THE SIGNAL"
    }


# ==========================================
# APPEL OPENAI ET PUBLICATION
# ==========================================

def main():

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY absent des secrets GitHub"
        )

    client = OpenAI(
        timeout=300.0,
        max_retries=0
    )

    response = client.responses.create(
        model="gpt-5-mini",
        tools=[{"type": "web_search"}],
        tool_choice="required",
        input=PROMPT
    )

    raw = response.output_text.strip()

    if raw.startswith("```"):
        raw = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            raw,
            flags=re.IGNORECASE
        ).strip()

    try:
        data = json.loads(raw)

    except json.JSONDecodeError as exc:
        raise ValueError(
            "OpenAI n'a pas renvoyé un JSON "
            "complet et valide"
        ) from exc

    edition = build_edition(data)

    # Publication uniquement après validation

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    tmp = OUT.with_suffix(".json.tmp")

    tmp.write_text(
        json.dumps(
            edition,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    # Remplacement atomique du fichier
    tmp.replace(OUT)

    print(
        "THE SIGNAL : édition générée le",
        TODAY
    )

    for key in (
        "critical",
        "radar",
        "intelligence",
        "data_points",
        "reading_room"
    ):
        print(
            f"{key}: {len(edition[key])} éléments"
        )

    print("Widget :")

    for item in edition["news"]:
        print("-", item["title"])


if __name__ == "__main__":
    main()
