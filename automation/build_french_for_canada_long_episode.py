from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import subprocess
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib import error, request


API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
TEXT_MODEL = "gemini-2.5-flash"
TTS_MODELS = [
    "gemini-3.1-flash-tts-preview",
    "gemini-2.5-flash-preview-tts",
]

HOST_VOICES = {
    "Sophie": "Sadachbia",
    "Leo": "Puck",
}

SCENE_VOICES = {
    "Maya": "Laomedeia",
    "Daniel": "Charon",
}

EDGE_VOICES = {
    "Sophie": "fr-CA-SylvieNeural",
    "Leo": "fr-CA-ThierryNeural",
    "Maya": "fr-FR-VivienneMultilingualNeural",
    "Daniel": "fr-CA-AntoineNeural",
}


@dataclass(frozen=True)
class Section:
    slug: str
    title: str
    speakers: dict[str, str]
    lines: list[tuple[str, str]]


SECTIONS: list[Section] = [
    Section(
        slug="01_warm_open",
        title="Warm open: French for Canada",
        speakers=HOST_VOICES,
        lines=[
            ("Sophie", "[warmly] Salut Leo. Avant de commencer, question importante: café ou thé aujourd'hui?"),
            ("Leo", "[smiling] Café. Très canadien de ma part: j'ai aussi regardé la météo trois fois avant neuf heures."),
            ("Sophie", "[light laugh] Parfait. Aujourd'hui, on fait une leçon très pratique pour les personnes qui arrivent au Canada."),
            ("Leo", "[clearly] Le thème: parler simplement quand tu es nouveau, quand tu cherches un appartement, et quand tu dois prendre rendez-vous."),
            ("Sophie", "[encouragingly] Si ton français est encore fragile, ce n'est pas grave. Le but n'est pas de parler comme un avocat. Le but, c'est de te faire comprendre avec calme."),
            ("Leo", "[thoughtfully] On va écouter deux petites situations, puis on va analyser les phrases utiles. Après, tu répètes avec nous."),
            ("Sophie", "[brightly] Et on garde un français clair, avec une petite couleur Canada, surtout Montréal et Québec, mais sans exagérer l'accent."),
            ("Leo", "[calmly] À la fin, tu auras une mini formule que tu peux utiliser demain matin: dire que tu viens d'arriver, demander de ralentir, et proposer un rendez-vous."),
        ],
    ),
    Section(
        slug="02_key_phrases",
        title="Three phrases for newcomers",
        speakers=HOST_VOICES,
        lines=[
            ("Leo", "[focused] Première phrase: je viens d'arriver au Canada. C'est simple, poli, et très utile."),
            ("Sophie", "[coach tone] Répète lentement: je viens d'arriver au Canada. Naturellement: je viens d'arriver au Canada."),
            ("Leo", "[clearly] Ça veut dire: I just arrived in Canada. Tu peux l'utiliser à la banque, dans une clinique, avec un propriétaire, ou au téléphone."),
            ("Sophie", "[warmly] Deuxième phrase: est-ce que vous pouvez parler un peu plus lentement, s'il vous plaît? C'est une phrase de survie."),
            ("Leo", "[analytical] Remarque la politesse: est-ce que vous pouvez. Puis la demande: parler un peu plus lentement. Et on finit avec s'il vous plaît."),
            ("Sophie", "[encouragingly] Cette phrase te protège. Tu ne dis pas: je ne comprends rien. Tu dis: aide-moi à mieux comprendre."),
            ("Leo", "[focused] Troisième phrase: j'aimerais prendre rendez-vous. C'est plus naturel que: je veux un rendez-vous."),
            ("Sophie", "[softly] J'aimerais, c'est poli. Prendre rendez-vous, c'est book an appointment. Tu peux dire: j'aimerais prendre rendez-vous pour demain matin."),
            ("Leo", "[short pause] Maintenant, on va écouter une situation réelle. Maya vient d'arriver à Montréal et elle parle avec Daniel pour visiter un appartement."),
        ],
    ),
    Section(
        slug="03_live_apartment_scene",
        title="Live situation: apartment visit",
        speakers=SCENE_VOICES,
        lines=[
            ("Maya", "[slightly nervous but friendly] Bonjour, je vous appelle pour l'appartement sur la rue Saint-Denis. Est-ce qu'il est encore disponible?"),
            ("Daniel", "[professional] Bonjour. Oui, il est encore disponible. Vous cherchez pour quelle date?"),
            ("Maya", "[carefully] Je viens d'arriver au Canada, alors je cherche quelque chose pour le mois prochain."),
            ("Daniel", "[warmly] D'accord. Vous travaillez ou vous étudiez à Montréal?"),
            ("Maya", "[honest] Je commence un emploi dans deux semaines. Est-ce que vous pouvez parler un peu plus lentement, s'il vous plaît?"),
            ("Daniel", "[reassuringly] Bien sûr, aucun problème. Je vais parler plus lentement."),
            ("Maya", "[relieved] Merci beaucoup. J'aimerais prendre rendez-vous pour visiter l'appartement."),
            ("Daniel", "[clear] Parfait. J'ai une disponibilité jeudi à dix-sept heures, ou samedi matin à dix heures."),
            ("Maya", "[thinking] Samedi matin, c'est mieux pour moi. Qu'est-ce que je dois apporter?"),
            ("Daniel", "[helpful] Une pièce d'identité, une preuve d'emploi si vous l'avez, et vos questions sur le logement."),
            ("Maya", "[confident] Très bien. Alors, samedi à dix heures. Merci, Daniel."),
            ("Daniel", "[friendly] Avec plaisir, Maya. Je vous envoie l'adresse par courriel."),
        ],
    ),
    Section(
        slug="04_breakdown_apartment",
        title="Breakdown: sound polite and clear",
        speakers=HOST_VOICES,
        lines=[
            ("Sophie", "[energized] Très bonne scène. Maya ne parle pas parfaitement, mais elle contrôle la conversation. C'est ça le vrai objectif."),
            ("Leo", "[analytical] Elle utilise trois tactiques: elle explique sa situation, elle demande de ralentir, puis elle propose une action concrète."),
            ("Sophie", "[clearly] Phrase numéro un: je viens d'arriver au Canada. Cette phrase donne du contexte. Les gens comprennent pourquoi tu poses des questions simples."),
            ("Leo", "[focused] En anglais, on dirait: I just arrived in Canada. En français naturel: je viens d'arriver au Canada."),
            ("Sophie", "[slowly] Prononciation: je viens - d'arriver - au Canada. Maintenant plus naturel: je viens d'arriver au Canada."),
            ("Leo", "[clearly] Phrase numéro deux: est-ce que vous pouvez parler un peu plus lentement? C'est très important pour les appels téléphoniques."),
            ("Sophie", "[encouragingly] Petit conseil: souris quand tu le dis. Même au téléphone, la voix devient plus douce."),
            ("Leo", "[focused] Phrase numéro trois: qu'est-ce que je dois apporter? Tu peux utiliser cette question pour un rendez-vous, une entrevue, une visite, ou un dossier administratif."),
            ("Sophie", "[warmly] Micro-résumé: contexte, rythme, prochaine étape. C'est simple, mais très puissant."),
            ("Leo", "[short pause] Maintenant, deuxième situation: un appel pour un rendez-vous dans une clinique. C'est très utile pour la vie quotidienne au Canada."),
        ],
    ),
    Section(
        slug="05_live_clinic_scene",
        title="Live situation: clinic appointment",
        speakers=SCENE_VOICES,
        lines=[
            ("Daniel", "[professional] Clinique du quartier, bonjour. Comment puis-je vous aider?"),
            ("Maya", "[polite] Bonjour. J'aimerais prendre rendez-vous avec un médecin, s'il vous plaît."),
            ("Daniel", "[clear] D'accord. Est-ce que c'est pour une consultation urgente?"),
            ("Maya", "[carefully] Non, ce n'est pas urgent. Je viens d'arriver au Canada et je veux faire un premier rendez-vous."),
            ("Daniel", "[helpful] Très bien. Avez-vous une carte d'assurance maladie?"),
            ("Maya", "[honest] Pas encore. Est-ce que vous pouvez parler un peu plus lentement, s'il vous plaît?"),
            ("Daniel", "[slower] Bien sûr. Avez-vous une assurance privée, ou un document temporaire?"),
            ("Maya", "[thinking] Oui, j'ai une assurance privée pour les trois premiers mois."),
            ("Daniel", "[clear] Parfait. J'ai une place mardi à quatorze heures quinze."),
            ("Maya", "[confirming] Mardi à quatorze heures quinze. Est-ce que je dois arriver en avance?"),
            ("Daniel", "[helpful] Oui, arrivez quinze minutes avant le rendez-vous avec votre passeport et votre document d'assurance."),
            ("Maya", "[confident] Très bien, merci. Je vais noter tout ça."),
        ],
    ),
    Section(
        slug="06_breakdown_clinic_tef",
        title="Breakdown: questions and TEF style",
        speakers=HOST_VOICES,
        lines=[
            ("Leo", "[focused] Cette scène est excellente pour la vraie vie, mais aussi pour les examens de type TEF ou TCF."),
            ("Sophie", "[curious] Pourquoi? Parce que Maya doit écouter une information, vérifier l'heure, et confirmer les documents."),
            ("Leo", "[analytical] En test oral, on évalue souvent ta capacité à demander, clarifier, reformuler, et conclure."),
            ("Sophie", "[coach tone] La phrase utile ici: est-ce que je dois arriver en avance? Ça veut dire: do I need to arrive early?"),
            ("Leo", "[clearly] Tu peux changer la fin: est-ce que je dois payer maintenant? Est-ce que je dois remplir un formulaire? Est-ce que je dois apporter mon passeport?"),
            ("Sophie", "[slowly] Répète: est-ce que je dois apporter mon passeport?"),
            ("Leo", "[natural speed] Est-ce que je dois apporter mon passeport?"),
            ("Sophie", "[encouragingly] Une autre phrase: je vais noter tout ça. Très naturel. Ça montre que tu as compris et que tu es organisé."),
            ("Leo", "[focused] Pour le Canada, surtout au téléphone, cette phrase est utile: je vais noter tout ça, merci."),
            ("Sophie", "[warmly] Et si tu n'as pas compris, ne panique pas. Dis: pardon, vous pouvez répéter l'heure, s'il vous plaît?"),
            ("Leo", "[short pause] Maintenant, on va transformer tout ça en mini méthode que tu peux utiliser partout."),
        ],
    ),
    Section(
        slug="07_practice",
        title="Practice: repeat and answer",
        speakers=HOST_VOICES,
        lines=[
            ("Sophie", "[teacher mode] Pratique avec nous. Je dis la phrase lentement. Tu répètes après moi."),
            ("Sophie", "[slowly] Je viens d'arriver au Canada."),
            ("Leo", "[short pause] Maintenant, naturel: je viens d'arriver au Canada."),
            ("Sophie", "[slowly] Est-ce que vous pouvez parler un peu plus lentement, s'il vous plaît?"),
            ("Leo", "[short pause] Naturel: est-ce que vous pouvez parler un peu plus lentement, s'il vous plaît?"),
            ("Sophie", "[slowly] J'aimerais prendre rendez-vous pour jeudi matin."),
            ("Leo", "[short pause] Naturel: j'aimerais prendre rendez-vous pour jeudi matin."),
            ("Sophie", "[brightly] Maintenant, remplis le blanc. J'aimerais prendre rendez-vous pour blank."),
            ("Leo", "[thinking pause] Tu peux répondre: demain matin, vendredi après-midi, ou la semaine prochaine."),
            ("Sophie", "[encouragingly] Deuxième blanc: est-ce que je dois apporter blank?"),
            ("Leo", "[clear] Tu peux dire: mon passeport, une preuve d'adresse, une preuve d'emploi, ou mon document d'assurance."),
            ("Sophie", "[warmly] Très bien. Ce genre de répétition construit une vraie mémoire orale."),
        ],
    ),
    Section(
        slug="08_recap_and_next",
        title="Recap and next lesson",
        speakers=HOST_VOICES,
        lines=[
            ("Leo", "[calmly] Résumé en trois points. Un: donne le contexte. Je viens d'arriver au Canada."),
            ("Sophie", "[clearly] Deux: demande un rythme plus lent. Est-ce que vous pouvez parler un peu plus lentement, s'il vous plaît?"),
            ("Leo", "[focused] Trois: finis avec une action. J'aimerais prendre rendez-vous. Qu'est-ce que je dois apporter?"),
            ("Sophie", "[warmly] Si tu apprends le français pour le Canada, ne cherche pas seulement des mots. Cherche des situations: logement, travail, santé, banque, école, transport."),
            ("Leo", "[analytical] Une situation réelle te donne du vocabulaire, de la grammaire, et une raison de parler."),
            ("Sophie", "[encouragingly] Dans la prochaine leçon, on peut faire un épisode complet sur l'entretien d'embauche au Canada: se présenter, parler de son expérience, et répondre calmement."),
            ("Leo", "[clear] Garde ces trois phrases dans ton téléphone et pratique-les aujourd'hui."),
            ("Sophie", "[friendly] Merci d'avoir écouté French for Canada. À très bientôt, et bon courage pour ton français."),
        ],
    ),
]


def extract_text(response_json: dict) -> str:
    try:
        parts = response_json["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Gemini text response: {response_json}") from exc
    return "".join(part.get("text", "") for part in parts)


def parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON object found in Gemini response: {text[:500]}")
    return json.loads(cleaned[start : end + 1])


def generate_sections_from_topic(api_key: str, title: str) -> tuple[list[Section], str]:
    prompt = f"""Create an 8-10 minute French-learning podcast script as JSON only.

Channel niche: French for Canada.
Episode title: {title}

Rules:
- Use clear French with a light Quebec/Montreal influence, but keep it easy for international learners.
- Main hosts are Sophie and Leo.
- Live situations use Maya and Daniel.
- Each section must use only two speakers:
  - host sections: Sophie and Leo
  - live situation sections: Maya and Daniel
- Make the episode specific to the title. Do not reuse apartment/clinic examples unless the title is about those topics.
- Include warm human banter, two realistic live situations, phrase breakdowns, repeat-after-me practice, and a short recap.
- The two live situation sections must contain the actual dialogue, not only an introduction to the dialogue.
- Do not write "listen to the scene" unless the next section is a real Maya/Daniel scene.
- Use subtle English audio tags in square brackets, like [warmly], [thinking], [encouragingly], [short pause].
- Target about 1,050 to 1,250 spoken French words total.
- Return valid JSON only, no markdown.

Required sections exactly:
1. 01_warm_open, speaker_group hosts, 6-8 lines with Sophie and Leo.
2. 02_key_vocabulary, speaker_group hosts, 8-10 lines with Sophie and Leo.
3. 03_live_situation_one, speaker_group scene, 10-14 lines with Maya and Daniel only. This must be real dialogue.
4. 04_breakdown_one, speaker_group hosts, 8-10 lines with Sophie and Leo.
5. 05_live_situation_two, speaker_group scene, 10-14 lines with Maya and Daniel only. This must be real dialogue.
6. 06_breakdown_two, speaker_group hosts, 8-10 lines with Sophie and Leo.
7. 07_repeat_practice, speaker_group hosts, 10-12 lines with Sophie and Leo.
8. 08_recap_close, speaker_group hosts, 6-8 lines with Sophie and Leo.

JSON shape:
{{
  "description": "one short YouTube description sentence specific to this episode",
  "tags": ["tag one", "tag two"],
  "sections": [
    {{
      "slug": "01_warm_open",
      "title": "Warm open",
      "speaker_group": "hosts",
      "lines": [
        {{"speaker": "Sophie", "text": "[warmly] ..."}},
        {{"speaker": "Leo", "text": "[calmly] ..."}}
      ]
    }}
  ]
}}
"""
    response_json = call_gemini(
        TEXT_MODEL,
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.85,
                "responseMimeType": "application/json",
            },
        },
        api_key,
    )
    data = parse_json_object(extract_text(response_json))
    sections: list[Section] = []
    for raw_section in data.get("sections", []):
        group = str(raw_section.get("speaker_group", "hosts")).strip().lower()
        speakers = SCENE_VOICES if group == "scene" else HOST_VOICES
        lines = []
        for raw_line in raw_section.get("lines", []):
            speaker = str(raw_line.get("speaker", "")).strip()
            text = str(raw_line.get("text", "")).strip()
            if speaker in speakers and text:
                lines.append((speaker, text))
        if lines:
            sections.append(
                Section(
                    slug=slugify(str(raw_section.get("slug") or raw_section.get("title") or f"section-{len(sections)+1}")),
                    title=str(raw_section.get("title") or f"Section {len(sections)+1}"),
                    speakers=speakers,
                    lines=lines,
                )
            )
    scene_sections = [section for section in sections if section.speakers == SCENE_VOICES]
    if len(sections) < 8:
        raise RuntimeError("Gemini generated too few valid sections for the episode")
    if len(scene_sections) < 2:
        raise RuntimeError("Gemini did not generate two valid Maya/Daniel live situation sections")
    for section in scene_sections:
        if len(section.lines) < 8:
            raise RuntimeError(f"Live situation section is too short: {section.title}")
    return sections, str(data.get("description", "")).strip()


def local_fallback_sections(title: str) -> tuple[list[Section], str]:
    topic = title.replace("French for Canada:", "").strip() or "daily life in Canada"
    description = f"Practice practical French for Canada with clear phrases for {topic}."
    sections = [
        Section(
            slug="01_warm_open",
            title=f"Warm open: {topic}",
            speakers=HOST_VOICES,
            lines=[
                ("Sophie", f"[warmly] Salut Leo. Aujourd'hui, on travaille un sujet tres utile pour le Canada: {topic}."),
                ("Leo", "[calmly] Exact. On va rester simple, naturel, et pratique. Pas de francais complique juste pour impressionner."),
                ("Sophie", "[light laugh] Oui. Ici, le but n'est pas de gagner un concours de grammaire. Le but, c'est de parler avec calme dans une vraie situation."),
                ("Leo", "[focused] On va ecouter deux mini-scenes avec Maya et Daniel, puis on va analyser les phrases importantes."),
                ("Sophie", "[encouragingly] Si tu debutes, respire. Tu peux parler lentement, demander de repeter, et quand meme etre poli."),
                ("Leo", "[clearly] A la fin, tu auras une petite methode: contexte, question claire, confirmation."),
            ],
        ),
        Section(
            slug="02_key_vocabulary",
            title="Key vocabulary",
            speakers=HOST_VOICES,
            lines=[
                ("Leo", f"[focused] Pour {topic}, retiens d'abord cette phrase: je voudrais avoir plus d'informations."),
                ("Sophie", "[coach tone] Lentement: je voudrais avoir plus d'informations. Naturellement: je voudrais avoir plus d'informations."),
                ("Leo", "[analytical] C'est poli. Plus doux que: je veux des informations."),
                ("Sophie", "[warmly] Deuxieme phrase: est-ce que vous pouvez m'expliquer les prochaines etapes?"),
                ("Leo", "[clearly] Les prochaines etapes, ca veut dire: what happens next."),
                ("Sophie", "[encouragingly] Troisieme phrase: je veux etre sur de bien comprendre. C'est parfait quand tu es au telephone."),
                ("Leo", "[focused] Et pour confirmer: donc, si je comprends bien, le rendez-vous est mardi a dix heures."),
                ("Sophie", "[short pause] Maintenant, ecoutons Maya et Daniel dans une situation concrete."),
            ],
        ),
        Section(
            slug="03_live_situation_one",
            title="Live situation one",
            speakers=SCENE_VOICES,
            lines=[
                ("Maya", f"[polite] Bonjour, je vous appelle parce que j'ai une question sur {topic}."),
                ("Daniel", "[professional] Bonjour. Bien sur, je vous ecoute."),
                ("Maya", "[carefully] Je viens d'arriver au Canada, alors je prefere verifier les informations."),
                ("Daniel", "[reassuringly] Aucun probleme. Qu'est-ce que vous voulez savoir exactement?"),
                ("Maya", "[thinking] Je voudrais avoir plus d'informations sur les documents necessaires."),
                ("Daniel", "[clear] D'accord. Vous avez besoin d'une piece d'identite et d'une preuve d'adresse."),
                ("Maya", "[carefully] Est-ce que vous pouvez parler un peu plus lentement, s'il vous plait?"),
                ("Daniel", "[slower] Bien sur. Une piece d'identite. Et une preuve d'adresse."),
                ("Maya", "[relieved] Merci. Et quelles sont les prochaines etapes?"),
                ("Daniel", "[helpful] Vous envoyez les documents, puis on confirme le rendez-vous par courriel."),
                ("Maya", "[confirming] Donc, si je comprends bien, j'envoie les documents et j'attends le courriel."),
                ("Daniel", "[friendly] Exactement. C'est parfait."),
            ],
        ),
        Section(
            slug="04_breakdown_one",
            title="Breakdown one",
            speakers=HOST_VOICES,
            lines=[
                ("Sophie", "[energized] Bonne scene. Maya ne parle pas vite, mais elle controle la conversation."),
                ("Leo", "[analytical] Elle fait trois choses: elle donne le contexte, elle demande une explication, et elle confirme."),
                ("Sophie", "[clearly] Phrase cle: je viens d'arriver au Canada. Cette phrase aide l'autre personne a comprendre ta situation."),
                ("Leo", "[focused] Deuxieme phrase: quelles sont les prochaines etapes? C'est court, clair, et tres professionnel."),
                ("Sophie", "[coach tone] Repete: quelles sont les prochaines etapes?"),
                ("Leo", "[natural speed] Quelles sont les prochaines etapes?"),
                ("Sophie", "[encouragingly] Troisieme phrase: si je comprends bien. C'est une phrase magique pour verifier sans paraitre perdu."),
                ("Leo", "[short pause] Maintenant, deuxieme scene: Maya doit fixer un rendez-vous."),
            ],
        ),
        Section(
            slug="05_live_situation_two",
            title="Live situation two",
            speakers=SCENE_VOICES,
            lines=[
                ("Daniel", "[professional] Bonjour Maya. J'ai recu vos documents."),
                ("Maya", "[friendly] Bonjour Daniel. Merci de me rappeler."),
                ("Daniel", "[clear] On peut vous proposer un rendez-vous jeudi a quinze heures trente."),
                ("Maya", "[thinking] Jeudi a quinze heures trente. Est-ce qu'il y a une autre option le matin?"),
                ("Daniel", "[helpful] Oui, vendredi a neuf heures quinze."),
                ("Maya", "[confirming] Vendredi a neuf heures quinze, c'est mieux pour moi."),
                ("Daniel", "[clear] Tres bien. Vous devez arriver dix minutes avant."),
                ("Maya", "[carefully] Je veux etre sure de bien comprendre: j'arrive dix minutes avant avec mes documents."),
                ("Daniel", "[reassuringly] Oui, exactement."),
                ("Maya", "[polite] Parfait. Est-ce que je vais recevoir une confirmation par courriel?"),
                ("Daniel", "[friendly] Oui. Je vous envoie la confirmation maintenant."),
                ("Maya", "[confident] Merci beaucoup. Bonne journee."),
            ],
        ),
        Section(
            slug="06_breakdown_two",
            title="Breakdown two",
            speakers=HOST_VOICES,
            lines=[
                ("Leo", "[focused] Ici, Maya utilise une bonne technique: elle repete l'heure pour verifier."),
                ("Sophie", "[warmly] Oui. Quand quelqu'un dit une heure, repete-la. Ca evite les erreurs."),
                ("Leo", "[clearly] Phrase utile: est-ce qu'il y a une autre option le matin?"),
                ("Sophie", "[coach tone] Tu peux changer la fin: le soir, cette semaine, la semaine prochaine."),
                ("Leo", "[analytical] Autre phrase tres naturelle: je veux etre sur de bien comprendre."),
                ("Sophie", "[slowly] Repete: je veux etre sure de bien comprendre."),
                ("Leo", "[natural speed] Je veux etre sur de bien comprendre."),
                ("Sophie", "[encouragingly] Cette phrase montre que tu es serieux et organise."),
            ],
        ),
        Section(
            slug="07_repeat_practice",
            title="Repeat practice",
            speakers=HOST_VOICES,
            lines=[
                ("Sophie", "[teacher mode] Pratique avec nous. Repete apres moi."),
                ("Sophie", "[slowly] Je voudrais avoir plus d'informations."),
                ("Leo", "[short pause] Naturel: je voudrais avoir plus d'informations."),
                ("Sophie", "[slowly] Quelles sont les prochaines etapes?"),
                ("Leo", "[short pause] Naturel: quelles sont les prochaines etapes?"),
                ("Sophie", "[slowly] Je veux etre sure de bien comprendre."),
                ("Leo", "[short pause] Naturel: je veux etre sur de bien comprendre."),
                ("Sophie", "[brightly] Maintenant, remplis le blanc: je voudrais avoir plus d'informations sur blank."),
                ("Leo", "[thinking pause] Tu peux dire: le rendez-vous, les documents, le prix, ou les horaires."),
                ("Sophie", "[encouragingly] Deuxieme blanc: est-ce qu'il y a une autre option blank?"),
                ("Leo", "[clear] Tu peux dire: le matin, vendredi, ou la semaine prochaine."),
            ],
        ),
        Section(
            slug="08_recap_close",
            title="Recap and next step",
            speakers=HOST_VOICES,
            lines=[
                ("Leo", "[calmly] Resume en trois points. Un: donne le contexte."),
                ("Sophie", "[clearly] Deux: demande une explication simple."),
                ("Leo", "[focused] Trois: confirme avec tes propres mots."),
                ("Sophie", f"[warmly] Pour {topic}, ces trois etapes t'aident a rester calme et clair."),
                ("Leo", "[analytical] Garde les phrases dans ton telephone et pratique-les a voix haute."),
                ("Sophie", "[friendly] Merci d'avoir ecoute French for Canada. A tres bientot."),
            ],
        ),
    ]
    return sections, description


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def clean_for_caption(text: str) -> str:
    text = re.sub(r"\[[^\]]+\]\s*", "", text)
    return text.strip()


def call_gemini(model: str, payload: dict, api_key: str) -> dict:
    url = f"{API_BASE}/{model}:generateContent"
    req = request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=300) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API error for {model} ({exc.code}): {details}") from exc


def extract_audio_bytes(response_json: dict) -> bytes:
    try:
        data = response_json["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Gemini audio response: {response_json}") from exc
    return base64.b64decode(data)


def save_wav(output_path: Path, pcm_data: bytes, sample_rate: int = 24000) -> None:
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)


def run_command(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(command)
            + "\nSTDOUT:\n"
            + completed.stdout
            + "\nSTDERR:\n"
            + completed.stderr
        )


def ffprobe_duration(path: Path) -> float:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}:\n{completed.stderr}")
    return float(completed.stdout.strip())


def build_section_prompt(section: Section) -> str:
    transcript = "\n".join(f"{speaker}: {line}" for speaker, line in section.lines)
    return f"""# AUDIO PROFILE

This is a French-learning podcast for adults preparing for life in Canada.

Delivery:
- Natural podcast energy.
- Clear French with a light Canadian French influence, close to Montreal/Quebec, but accessible to international learners.
- No exaggerated slang.
- Moderate pace, with real pauses after important phrases.
- Keep emotional tags subtle and human.

Section title: {section.title}

Transcript:
{transcript}
"""


def render_section(section: Section, api_key: str, output_dir: Path) -> tuple[Path, str]:
    if not api_key:
        return render_section_with_edge_tts(section, output_dir), "edge-tts"

    prompt = build_section_prompt(section)
    speaker_voice_configs = [
        {
            "speaker": speaker,
            "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}},
        }
        for speaker, voice in section.speakers.items()
    ]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "multiSpeakerVoiceConfig": {
                    "speakerVoiceConfigs": speaker_voice_configs,
                }
            },
        },
    }
    last_error: Exception | None = None
    for model in TTS_MODELS:
        try:
            response_json = call_gemini(model, payload, api_key)
            pcm_audio = extract_audio_bytes(response_json)
            wav_path = output_dir / f"{section.slug}.wav"
            save_wav(wav_path, pcm_audio)
            return wav_path, model
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    assert last_error is not None
    print(f"WARNING: Gemini TTS failed for {section.slug}; using edge-tts fallback. {last_error}")
    return render_section_with_edge_tts(section, output_dir), "edge-tts-after-gemini-failure"


async def synthesize_edge_mp3(text: str, voice: str, mp3_path: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+5%", pitch="+0Hz")
    await communicate.save(str(mp3_path))


def render_section_with_edge_tts(section: Section, output_dir: Path) -> Path:
    line_dir = output_dir / f"{section.slug}_edge"
    line_dir.mkdir(parents=True, exist_ok=True)
    wav_parts: list[Path] = []
    silence_path = line_dir / "silence.wav"
    run_command(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=24000:cl=mono",
            "-t",
            "0.35",
            "-acodec",
            "pcm_s16le",
            str(silence_path),
        ]
    )
    for index, (speaker, line) in enumerate(section.lines, start=1):
        text = clean_for_caption(line)
        if not text:
            continue
        voice = EDGE_VOICES.get(speaker, "fr-CA-SylvieNeural")
        mp3_path = line_dir / f"{index:03d}_{slugify(speaker)}.mp3"
        wav_path = line_dir / f"{index:03d}_{slugify(speaker)}.wav"
        asyncio.run(synthesize_edge_mp3(text, voice, mp3_path))
        run_command(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(mp3_path),
                "-ar",
                "24000",
                "-ac",
                "1",
                "-acodec",
                "pcm_s16le",
                str(wav_path),
            ]
        )
        wav_parts.append(wav_path)
        wav_parts.append(silence_path)
    if not wav_parts:
        raise RuntimeError(f"No Edge TTS audio parts were generated for {section.slug}")
    concat_path = line_dir / "section.concat.txt"
    section_wav = output_dir / f"{section.slug}.wav"
    concat_path.write_text(
        "\n".join(f"file '{part.resolve().as_posix()}'" for part in wav_parts) + "\n",
        encoding="utf-8",
    )
    run_command(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c",
            "copy",
            str(section_wav),
        ]
    )
    return section_wav


def word_count(text: str) -> int:
    return len(re.findall(r"[\w']+", clean_for_caption(text), flags=re.UNICODE))


def seconds_to_srt(value: float) -> str:
    total_ms = int(round(value * 1000))
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    seconds = (total_ms % 60000) // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def seconds_to_ass(value: float) -> str:
    total_cs = int(round(value * 100))
    hours = total_cs // 360000
    minutes = (total_cs % 360000) // 6000
    seconds = (total_cs % 6000) // 100
    centis = total_cs % 100
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}"


def make_caption_segments(sections: list[Section], section_durations: dict[str, float]) -> list[tuple[float, float, str]]:
    cursor = 0.0
    segments: list[tuple[float, float, str]] = []
    for section in sections:
        duration = section_durations[section.slug]
        total_words = max(sum(word_count(line) for _, line in section.lines), 1)
        local = cursor
        for index, (_, line) in enumerate(section.lines):
            caption = clean_for_caption(line)
            words = max(word_count(line), 1)
            segment_duration = max(2.4, duration * (words / total_words))
            end = min(cursor + duration, local + segment_duration)
            if index == len(section.lines) - 1:
                end = cursor + duration
            segments.append((local, end, caption))
            local = end
        cursor += duration
    return segments


def write_transcript(path: Path, sections: list[Section]) -> None:
    lines: list[str] = []
    for section in sections:
        lines.append(f"# {section.title}")
        for speaker, line in section.lines:
            lines.append(f"{speaker}: {clean_for_caption(line)}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_srt(path: Path, segments: list[tuple[float, float, str]]) -> None:
    blocks = [
        f"{index}\n{seconds_to_srt(start)} --> {seconds_to_srt(end)}\n{text}\n"
        for index, (start, end, text) in enumerate(segments, start=1)
    ]
    path.write_text("\n".join(blocks), encoding="utf-8")


def ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", r"\{").replace("}", r"\}")


def write_ass(path: Path, segments: list[tuple[float, float, str]]) -> None:
    header = """[Script Info]
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,44,&H00FFFFFF,&H000000FF,&H00111111,&H99000000,-1,0,0,0,100,100,0,0,1,3,1,2,210,210,82,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = [
        f"Dialogue: 0,{seconds_to_ass(start)},{seconds_to_ass(end)},Default,,0,0,0,,{ass_escape(text)}"
        for start, end, text in segments
    ]
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def concat_audio(wav_paths: list[Path], concat_path: Path, wav_output: Path, mp3_output: Path) -> None:
    concat_lines = [f"file '{path.resolve().as_posix()}'" for path in wav_paths]
    concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    run_command(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c",
            "copy",
            str(wav_output),
        ]
    )
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(wav_output),
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "192k",
            str(mp3_output),
        ]
    )


def build_video(
    background: Path,
    mp3_path: Path,
    ass_path: Path,
    mp4_path: Path,
    frame_path: Path,
    preset: str = "veryfast",
) -> None:
    subtitle_path = ass_path.resolve().as_posix().replace(":", r"\:")
    run_command(
        [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(background),
            "-i",
            str(mp3_path),
            "-vf",
            f"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,ass='{subtitle_path}'",
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            "21",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(mp4_path),
        ]
    )
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(mp4_path),
            "-vf",
            r"select=eq(n\,180)",
            "-vframes",
            "1",
            "-update",
            "1",
            str(frame_path),
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a long French for Canada podcast test.")
    parser.add_argument("--output-root", default="runs")
    parser.add_argument("--background", default="video/download.mp4")
    parser.add_argument("--title", default="French for Canada: First Appointments and Daily Life")
    parser.add_argument("--static-template", action="store_true")
    parser.add_argument("--video-preset", default="veryfast")
    parser.add_argument(
        "--text-fallback",
        choices=("local", "static", "fail"),
        default="local",
        help="Behavior when Gemini text generation fails before TTS rendering.",
    )
    parser.add_argument("--script-only", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("WARNING: GEMINI_API_KEY is not set; using local script and edge-tts fallback.")

    base_dir = Path.cwd()
    background = (base_dir / args.background).resolve()
    if not background.exists():
        raise RuntimeError(f"Background video not found: {background}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base_dir / args.output_root / f"{timestamp}_{slugify(args.title)}"
    sections_dir = run_dir / "sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    if args.static_template:
        sections = SECTIONS
        generated_description = ""
        script_source = "static-template"
    elif not api_key:
        sections, generated_description = local_fallback_sections(args.title)
        script_source = "local-template-no-gemini-key"
    else:
        try:
            sections, generated_description = generate_sections_from_topic(api_key, args.title)
            script_source = "gemini-text"
        except Exception as exc:  # noqa: BLE001
            if args.text_fallback == "fail":
                raise
            print(f"WARNING: Gemini text generation failed; using {args.text_fallback} fallback. {exc}")
            if args.text_fallback == "static":
                sections = SECTIONS
                generated_description = ""
                script_source = "static-template-after-gemini-failure"
            else:
                sections, generated_description = local_fallback_sections(args.title)
                script_source = "local-template-after-gemini-failure"

    if args.script_only:
        transcript_path = run_dir / "french_for_canada_long_transcript.txt"
        summary_path = run_dir / "build_summary.json"
        title_path = run_dir / "youtube_title.txt"
        description_path = run_dir / "youtube_description.txt"
        write_transcript(transcript_path, sections)
        title_path.write_text(args.title + "\n", encoding="utf-8")
        description_path.write_text(
            "\n".join(
                [
                    "Learn real French for life in Canada with Sophie and Leo.",
                    "",
                    generated_description or f"In this episode: practical Canadian French for {args.title}.",
                    "",
                    "Synthetic media disclosure: this educational video uses AI-generated voices and AI-assisted visuals.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        summary = {
            "title": args.title,
            "script_only": True,
            "run_dir": str(run_dir),
            "transcript": str(transcript_path),
            "youtube_title": str(title_path),
            "youtube_description": str(description_path),
            "script_source": script_source,
            "sections": [section.title for section in sections],
        }
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    wav_paths: list[Path] = []
    section_durations: dict[str, float] = {}
    models_used: dict[str, str] = {}

    for section in sections:
        wav_path, model = render_section(section, api_key, sections_dir)
        wav_paths.append(wav_path)
        section_durations[section.slug] = ffprobe_duration(wav_path)
        models_used[section.slug] = model

    transcript_path = run_dir / "french_for_canada_long_transcript.txt"
    concat_path = run_dir / "audio.concat.txt"
    wav_output = run_dir / "french_for_canada_long.wav"
    mp3_output = run_dir / "french_for_canada_long.mp3"
    srt_path = run_dir / "french_for_canada_long.srt"
    ass_path = run_dir / "french_for_canada_long.ass"
    mp4_path = run_dir / "french_for_canada_long.mp4"
    frame_path = run_dir / "french_for_canada_long_frame.png"
    summary_path = run_dir / "build_summary.json"
    title_path = run_dir / "youtube_title.txt"
    description_path = run_dir / "youtube_description.txt"

    concat_audio(wav_paths, concat_path, wav_output, mp3_output)
    duration = ffprobe_duration(mp3_output)
    segments = make_caption_segments(sections, section_durations)
    write_transcript(transcript_path, sections)
    write_srt(srt_path, segments)
    write_ass(ass_path, segments)
    build_video(background, mp3_output, ass_path, mp4_path, frame_path, preset=args.video_preset)

    title_path.write_text(args.title + "\n", encoding="utf-8")
    description_path.write_text(
        "\n".join(
            [
                "Learn real French for life in Canada with Sophie and Leo.",
                "",
                generated_description or f"In this episode: practical Canadian French for {args.title}.",
                "",
                "Synthetic media disclosure: this educational video uses AI-generated voices and AI-assisted visuals.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = {
        "title": args.title,
        "duration_seconds": duration,
        "models_used": models_used,
        "background": str(background),
        "run_dir": str(run_dir),
        "transcript": str(transcript_path),
        "mp3": str(mp3_output),
        "srt": str(srt_path),
        "ass": str(ass_path),
        "mp4": str(mp4_path),
        "frame": str(frame_path),
        "youtube_title": str(title_path),
        "youtube_description": str(description_path),
        "script_source": script_source,
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
