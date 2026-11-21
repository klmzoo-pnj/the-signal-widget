#!/usr/bin/env python3
"""THE SIGNAL — veille complète + widget Scriptable.

Un appel OpenAI par exécution. Une édition invalide n'est pas publiée.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from openai import OpenAI

TODAY = datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()
OUT = Path("docs/signal.json")

PROMPT = f"""
Tu es la rédaction de THE SIGNAL, Executive Intelligence Brief en français.
Date de l'édition : {TODAY}, fuseau Europe/Paris.

Effectue une recherche web réelle. Sélectionne uniquement des informations
récentes et vérifiables. Sujets : technologie, IA, startups/VC, macro/marchés,
cybersécurité, renseignement, géopolitique, défense, industrie et supply chain.
SOURCES POUR ACTUALITÉS : Reuters, AP, FT, WSJ, sources officielles,
Rest of World et médias spécialisés fiables. Explore aussi OpexNews
(opexnews.fr) pour défense, BITD, équipements, commandes et souveraineté,
et Intelligence Online (intelligenceonline.fr / intelligenceonline.com)
pour renseignement, réseaux d'influence, diplomatie secrète et cyber.
Ce sont des sources à consulter en priorité pour leurs SPÉCIALITÉS,
jamais des rubriques à remplir ni une preuve automatique de véracité.
Vérifie date, titre, contenu et attribution de chaque article.
Ne confonds jamais la publication d'une information et sa confirmation
indépendante : une révélation exclusive se rapporte à son média.

RÈGLES DE VÉRIFICATION :
- Chaque URL HTTPS doit mener à un article/document précis étayant le titre.
- N'invente aucun fait, chiffre, sommet, introduction en Bourse ou URL.
- Pour IPO, résultats financiers, acquisitions, cyberattaques et espionnage,
  fais preuve d'une prudence renforcée ; attribution et chiffres seulement
  s'ils sont directement documentés par la source, sinon écarte le sujet.
- Ne transforme jamais un conditionnel journalistique en fait avéré.
- Distingue fait avéré, projet, négociation, accusation et hypothèse.
- Actualités : idéalement 72 h, jusqu'à 7 jours si nécessaire.
- Lectures : enquêtes et grands formats de moins de 90 jours.
- Pas de doublons entre rubriques ; plusieurs secteurs représentés.
- Chaque sujet doit justifier sa présence : nouveauté, importance,
  caractère peu évident, conséquence stratégique compréhensible.
- AUCUN quota n'est un objectif à atteindre. N'invente ni n'ajoute
  des sujets faibles pour compléter une liste.
- Si tu n'as pas assez de faits fiables, rends moins d'items plutôt que
  d'inventer. Ne laisse pas de champs vides.

RENVOIE UNIQUEMENT UN OBJET JSON VALIDE (sans Markdown) comportant :

"critical" : entre 2 et 5 objets, seulement les nouvelles structurantes, avec
{{"title":"...", "category":"...", "summary":"...", "url":"https://..."}}.
Les 3 PREMIERS titres font 54 caractères maximum, sans points de suspension.
Résumés de 45 à 75 mots : faits et pourquoi ils comptent.

"radar" : 0 à 4 objets (CIBLE 2 OU 3 UNIQUEMENT SI MÉRITÉS) avec
{{"title":"...", "category":"...", "summary":"...", "url":"https://..."}}.
CE N'EST PAS UNE RUBRIQUE DE REMPLISSAGE. Sélectionne exclusivement
les 2, 3 ou 4 meilleures informations discrètes du jour.
Fenêtre PRIORITAIRE : les dernières 24 à 48 h en heure de Paris.
Tolérance de 72 h seulement pour un nouveau développement vérifiable.
Un événement plus ancien ne peut être retenu que si un FAIT NOUVEAU
dans les dernières 48 h modifie sa portée ; précise ce fait nouveau.
Chaque entrée doit passer ces 4 tests :
1. FRAÎCHEUR : fait nouveau documenté, pas un sujet générique ;
2. PORTÉE : implication claire pour entreprises, pouvoir ou capital ;
3. ORIGINALITÉ : signal encore peu visible, pas simple reprise de titre ;
4. UTILITÉ : le lecteur comprend ce qui change SANS cliquer.
Donne priorité aux startups/VC, chaînes industrielles, fournisseurs
stratégiques, capital, intelligence, cyber et régulation concrète.
Écarte les déclarations politiques sans suite, chiffres économiques sans
écart ni contexte, résumés de discussions et auditions anecdotiques.
Résumés de 50 à 75 mots, présentant dans cet ordre :
- Le fait vérifié et daté (qui, quoi, nouveauté concrète) ;
- Le contexte ou la référence qui rend la nouvelle remarquable ;
- LE SIGNAL : implication stratégique ou question précise à surveiller.
N'écris jamais une hypothèse comme un fait.
Si aucune information ne passe les tests, renvoie "radar": [].
Les sujets sont distincts de "critical".

"intelligence" : 0 à 3 objets, seulement si pertinents, avec
{{"title":"...", "category":"...", "summary":"...", "url":"https://..."}}.
Renseignement, défense, cyber ou capacités industrielles.

"data_points" : 1 à 4 objets réellement contextualisés, CHACUN avec SIX clés
EXACTES et obligatoires, toutes de type chaîne :
{{"label":"...", "value":"290 M€", "context":"...",
  "comparison":"...", "stakes":"...", "url":"https://..."}}.
- label : intitulé qui dit précisément QUOI, QUI et QUAND.
- value : UNE métrique courte, de 1 à 20 caractères au maximum,
  exemple « +12 % », « 4,5 Md€ », « 81 jours » ; jamais une phrase.
  Ne mets dans value ni le nom de l'entreprise ni les explications : elles
  vont exclusivement dans label et context. Période et périmètre dans
  label/context. Choisis le meilleur indicateur si une source en donne 3.
- context : mesure, période, population ou périmètre, en 15-30 mots.
- comparison : comparaison CHIFFRÉE et VÉRIFIABLE avec T-1, N-1,
  consensus, concurrent, objectif ou référence historique ; fournir valeur,
  base et période, en 20-45 mots. Une simple phrase vague est interdite.
- stakes : pourquoi l'écart compte, ce qu'il révèle de stratégique,
  en 20-35 mots maximum. Évite les banalités et les spéculations.
- Les 2 à 4 data points doivent couvrir des domaines différents si possible.
  Ne répète pas un même sujet, entreprise ou opération dans 2 cartes.
- url : source HTTPS permettant de vérifier la valeur ET la comparaison.
N'invente jamais de comparaison ou de consensus. Si aucune comparaison
solide n'est trouvée, choisis une AUTRE donnée. Évite les chiffres isolés,
les unités ambiguës et les comparaisons de périmètres incompatibles.
Le nombre de 4 est une cible, la qualité prime sur la quantité.

"reading_room" : 1 à 4 lectures d'exception avec
{{"title":"...", "source":"...", "why_read":"...", "url":"https://..."}}.
Les 2 PREMIERS titres font 48 caractères maximum, sans points de suspension.
Avant de chercher ailleurs, explore ACTIVEMENT et séparément les articles
récents de ces rédactions, sans quota ni obligation de les retenir :
1. The New Yorker : grands reportages, portraits et enquêtes au long cours.
2. The Wall Street Journal : enquêtes originales, affaires, industrie.
3. 404 Media (404media.co) : surveillance, hacking, plateformes, données.
4. Financial Times : enquêtes, Big Reads, finance et chaînes industrielles.
5. Intelligence Online : enquêtes sur renseignement et réseaux de pouvoir.
6. OpexNews : entretiens ou reportages originaux défense/industrie.
Recherche chaque source explicitement ; compare ensuite les articles candidats.
Élargis seulement si des publications tierces offrent de meilleurs formats
(Rest of World, ProPublica, Bloomberg, MIT Tech Review, Wired, etc.).
AUCUN quota par média : ne retiens que les meilleures lectures, 1 à 4.
Préférence 30 derniers jours, jusqu'à 90 jours pour un article remarquable.
PRIORITÉ ABSOLUE aux enquêtes, grands reportages et portraits approfondis.
Exclus les simples brèves, reprises d'agences, pages d'accueil, billets
promotionnels, billets d'annonce, synthèses superficielles et rapports
techniques (ceux-ci vont plutôt dans Intelligence & Industrial Signals).
Diversifie les thèmes : pas 3 articles sur la même opération ou la même IA.
Pourquoi lire : 35-50 mots, avec ce que l'enquête révèle concrètement,
ce qui la rend originale et l'intérêt pour nos lecteurs.
Respecte titre, média, date et URL de l'article précis ; n'invente rien.
N'ajoute jamais un média prioritaire si son article n'est pas remarquable.

"editorial" : un objet
{{"title":"...", "text":"..."}}.
Réflexion stratégique originale (60 à 90 mots), identifiée comme analyse.

Relis les clés JSON et vérifie chaque objet avant de répondre.
"""


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
    return isinstance(value, str) and bool(value.strip())


def compact_title(text, max_length):
    """Raccourcit au dernier mot complet, sans ajouter de points de suspension."""
    text = " ".join(text.split()).replace("…", "").replace("...", "")
    if len(text) <= max_length:
        return text
    short = text[: max_length + 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return short if short else text[:max_length]


def normalize_entries(data, name, fields, minimum, maximum):
    raw = data.get(name, [])
    if not isinstance(raw, list):
        raise ValueError(f"{name}: liste JSON attendue")

    cleaned = []
    seen = set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            print(f"AVERTISSEMENT : {name}[{i}] ignoré (pas un objet)")
            continue
        item = dict(item)

        # Corrige uniquement les noms de champs évidents ; n'invente pas de valeur.
        if name == "data_points" and not nonempty_text(item.get("value")):
            for alias in ("figure", "amount", "number", "stat"):
                candidate = item.get(alias)
                if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
                    item["value"] = str(candidate)
                    break
                if nonempty_text(candidate):
                    item["value"] = candidate.strip()
                    break

        if not all(nonempty_text(item.get(field)) for field in fields):
            print(f"AVERTISSEMENT : {name}[{i}] ignoré (champ manquant)")
            continue
        if not valid_url(item["url"]):
            print(f"AVERTISSEMENT : {name}[{i}] ignoré (URL invalide)")
            continue
        if name == "data_points":
            # Un « chiffre » ne doit plus être une phrase immense.
            metric = " ".join(str(item["value"]).split())
            if len(metric) > 22 or not re.search(r"\d", metric):
                print(f"AVERTISSEMENT : {name}[{i}] ignoré (valeur trop longue ou non chiffrée)")
                continue
            item["value"] = metric
            if not re.search(r"\d", item["comparison"]):
                print(f"AVERTISSEMENT : {name}[{i}] ignoré (comparaison non chiffrée)")
                continue

        item = {field: item[field].strip() for field in fields}
        url = item["url"]
        if url in seen:
            print(f"AVERTISSEMENT : {name}[{i}] ignoré (URL répétée)")
            continue
        seen.add(url)
        cleaned.append(item)

    if len(cleaned) < minimum:
        raise ValueError(
            f"{name}: seulement {len(cleaned)} éléments valides "
            f"(minimum {minimum}). Ancienne édition conservée."
        )
    if len(cleaned) > maximum:
        print(f"INFO : {name} réduit de {len(cleaned)} à {maximum} éléments")
        cleaned = cleaned[:maximum]
    return cleaned


def build_edition(data):
    if not isinstance(data, dict):
        raise ValueError("Réponse JSON : objet attendu")

    critical = normalize_entries(
        data, "critical", ("title", "category", "summary", "url"), 2, 5
    )
    radar = normalize_entries(
        data, "radar", ("title", "category", "summary", "url"), 0, 4
    )
    intelligence = normalize_entries(
        data, "intelligence", ("title", "category", "summary", "url"), 0, 3
    )
    data_points = normalize_entries(
        data, "data_points", ("label", "value", "context", "comparison", "stakes", "url"), 1, 4
    )
    reading_room = normalize_entries(
        data, "reading_room", ("title", "source", "why_read", "url"), 1, 4
    )

    editorial = data.get("editorial")
    if not isinstance(editorial, dict) or not all(
        nonempty_text(editorial.get(field)) for field in ("title", "text")
    ):
        raise ValueError("editorial: titre ou texte manquant")

    # Le widget a sa propre limite de largeur, sans modifier les titres du site.
    news = [
        {
            "title": compact_title(item["title"], 54),
            "category": item["category"],
            "url": item["url"],
        }
        for item in critical[:3]
    ]
    readings = [
        {
            "title": compact_title(item["title"], 48),
            "source": item["source"],
            "url": item["url"],
        }
        for item in reading_room[:2]
    ]

    # Noms inchangés pour le site et Scriptable existants.
    return {
        "critical": critical,
        "radar": radar,
        "intelligence": intelligence,
        "data_points": data_points,
        "reading_room": reading_room,
        "editorial": {
            "title": editorial["title"].strip(),
            "text": editorial["text"].strip(),
        },
        "news": news,
        "readings": readings,
        "date": TODAY,
        "edition": "THE SIGNAL",
    }


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY absent des secrets GitHub")

    client = OpenAI(timeout=300.0, max_retries=0)
    response = client.responses.create(
        model="gpt-5-mini",
        tools=[{"type": "web_search"}],
        tool_choice="required",
        input=PROMPT,
    )
    raw = response.output_text.strip()
    if raw.startswith("```"):
        raw = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE
        ).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("OpenAI n'a pas renvoyé un JSON complet et valide") from exc

    edition = build_edition(data)

    # Écriture atomique après validation : aucune édition partielle publiée.
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(edition, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(OUT)

    print("THE SIGNAL : édition générée le", TODAY)
    for key in ("critical", "radar", "intelligence", "data_points", "reading_room"):
        print(f"{key}: {len(edition[key])} éléments")
    print("Widget :")
    for item in edition["news"]:
        print("-", item["title"])


if __name__ == "__main__":
    main()
