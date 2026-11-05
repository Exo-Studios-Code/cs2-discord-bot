"""
AI Analyzer - Google Gemini integrace (nové SDK: google-genai)
Analyzuje CS2 statistiky a zápasy pomocí AI.
"""

import logging
import os
from typing import Optional, Dict, Any

log = logging.getLogger("CS2Bot.AI")

class AIAnalyzer:
    def __init__(self):
        api_key = os.getenv("GOOGLE_AI_KEY")
        self.available = False
        self.client = None

        if not api_key:
            log.warning("[AI] GOOGLE_AI_KEY neni nastaven - AI analyza nedostupna")
            return

        try:
            from google import genai
            self.client = genai.Client(api_key=api_key)
            # Otestuj dostupnost modelu
            self.model = "gemini-2.0-flash"
            self.available = True
            log.info("[AI] Google Gemini pripraven (model: %s)", self.model)
        except ImportError:
            log.error("[AI] Knihovna 'google-genai' neni nainstalova. Spust: pip install google-genai")
        except Exception as e:
            log.error("[AI] Chyba inicializace: %s", e)

    def _generate(self, prompt: str) -> Optional[str]:
        """Synchronni volani Gemini API."""
        if not self.available or not self.client:
            return None
        try:
            from google.genai import types
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=2048,
                    temperature=0.7,
                )
            )
            return response.text
        except Exception as e:
            log.error("[AI] Chyba generovani: %s", e)
            return None

    async def analyze_overall_stats(self, stats: Dict[str, Any], player_name: str) -> str:
        if not self.available:
            return self._fallback_stats_analysis(stats)

        prompt = f"""Jsi expert na Counter-Strike 2 (CS2). Analyzuj statistiky hrace "{player_name}" a poskytni detailni, prakticke hodnoceni v cestine.

STATISTIKY:
- K/D Ratio: {stats.get('kd_ratio', 0)}
- Win Rate: {stats.get('win_rate', 0)}%
- Headshot Rate: {stats.get('hs_rate', 0)}%
- Presnost: {stats.get('accuracy', 0)}%
- ADR: {stats.get('adr', 0)}
- Celkem zabiti: {stats.get('total_kills', 0):,}
- Celkem smrti: {stats.get('total_deaths', 0):,}
- Celkem zapasu: {stats.get('total_matches', 0):,}
- Vyhry: {stats.get('total_wins', 0):,}
- MVPs: {stats.get('total_mvps', 0):,}
- Hodiny: {stats.get('hours_played', 0)}h
- Nejlepsi mapa: {stats.get('best_map', 'N/A')}
- Oblibena zbran: {stats.get('favorite_weapon', 'N/A')}

Poskytni:
1. Celkove hodnoceni (2-3 vety)
2. Silne stranky (3 konkretni veci)
3. Slabe stranky (3 konkretni veci)
4. Doporuceni pro zlepseni (5 rad)
5. Styl hry (odhadnuty na zaklade dat)
6. Odhadovany rank

Bud konkretni a motivujici. Odpovez v cestine."""

        result = self._generate(prompt)
        return result if result else self._fallback_stats_analysis(stats)

    async def analyze_match(self, match_data: Dict[str, Any],
                             player_name: str, teammates=None, enemies=None) -> str:
        if not self.available:
            return self._fallback_match_analysis(match_data)

        team_info = ""
        if teammates:
            team_info = "\nSPOLUHRACI:\n" + "\n".join(
                [f"- {p.get('name')}: {p.get('kills')}/{p.get('deaths')}/{p.get('assists')}"
                 for p in teammates]
            )

        enemy_info = ""
        if enemies:
            enemy_info = "\nNEPRATELE:\n" + "\n".join(
                [f"- {p.get('name')}: {p.get('kills')}/{p.get('deaths')}/{p.get('assists')}"
                 for p in enemies]
            )

        prompt = f"""Jsi CS2 analytik. Analyzuj zapas hrace "{player_name}" v cestine.

ZAPAS:
- Mapa: {match_data.get('map_name', 'N/A')}
- Skore: {match_data.get('score_ct', 0)}-{match_data.get('score_t', 0)}
- Vysledek: {match_data.get('result', 'N/A')}
- K/D/A: {match_data.get('kills', 0)}/{match_data.get('deaths', 0)}/{match_data.get('assists', 0)}
- Headshoty: {match_data.get('hs_kills', 0)}
- MVPs: {match_data.get('mvps', 0)}
- ADR: {match_data.get('adr', 0)}
{team_info}{enemy_info}

Poskytni:
1. Shrnutí vykonu (2-3 vety)
2. Co se povedlo
3. Co se nepovedlo
4. 3 tipy do pristiho zapasu
5. Rating vykonu 1-10

Odpovez v cestine, bud uprimny ale konstruktivni."""

        result = self._generate(prompt)
        return result if result else self._fallback_match_analysis(match_data)

    async def analyze_progress(self, snapshots: list, current_stats: Dict) -> str:
        if not self.available or len(snapshots) < 2:
            return "Pro AI analyzu pokroku potrebuji alespon 2 snimky statistik."

        oldest = snapshots[-1]
        newest = snapshots[0]
        kd_change = round(float(newest["kd_ratio"]) - float(oldest["kd_ratio"]), 2)
        wr_change = round(float(newest["win_rate"]) - float(oldest["win_rate"]), 1)

        prompt = f"""Analyzuj pokrok CS2 hrace v case v cestine.

DRIVE ({str(oldest['snapshot_date'])[:10]}):
K/D: {oldest['kd_ratio']}, Win Rate: {oldest['win_rate']}%, HS: {oldest['hs_rate']}%
Zapasy: {oldest['total_matches']}

NYNI:
K/D: {newest['kd_ratio']}, Win Rate: {newest['win_rate']}%, HS: {newest['hs_rate']}%
Zapasy: {newest['total_matches']}

ZMENY: K/D {'+' if kd_change>=0 else ''}{kd_change}, WR {'+' if wr_change>=0 else ''}{wr_change}%

Poskytni:
1. Celkovy trend (zlepseni/stagnace/pokles)
2. Nejvetsi pokrok
3. Co jeste zlepsit
4. Motivacni zprava
5. 3 cilene cile na pristy tyden

Bud uprimny a motivujici. V cestine."""

        result = self._generate(prompt)
        return result or "Nepodarilo se vygenerovat analyzu pokroku."

    async def quick_tip(self, stats: Dict) -> str:
        if not self.available:
            return "Tip: Zaměř se na konzistentní crosshair placement a pre-aimy!"

        weak = []
        if stats.get("hs_rate", 0) < 30: weak.append("nízká headshot rate")
        if stats.get("kd_ratio", 1) < 1.0: weak.append("K/D pod 1.0")
        if stats.get("accuracy", 0) < 20: weak.append("nízká přesnost")
        if stats.get("win_rate", 50) < 45: weak.append("win rate pod 45%")
        weaknesses = ", ".join(weak) if weak else "celkové zlepšení"

        prompt = f"Dej mi 1 konkretni prakticKy CS2 tip pro hrace s {weaknesses}. Max 2 vety, v cestine, actionable."
        result = self._generate(prompt)
        return f"Tip: {result.strip()}" if result else "Tip: Trénuj deathmatch každý den!"

    async def analyze_external_data(self, player_name: str, external: Dict) -> str:
        """Analyzuje data z externích webů (Leetify, FACEIT, CSGOStats)."""
        if not self.available:
            return "AI analyza externich dat neni dostupna."

        sections = []
        if external.get("leetify"):
            l = external["leetify"]
            sections.append(f"LEETIFY: Aim rating {l.get('aim_rating','N/A')}, Utility {l.get('utility_rating','N/A')}, Positioning {l.get('positioning_rating','N/A')}, Clutch {l.get('clutch_rating','N/A')}")
        if external.get("faceit"):
            f = external["faceit"]
            sections.append(f"FACEIT: Level {f.get('level','N/A')}, ELO {f.get('elo','N/A')}, Win Rate {f.get('win_rate','N/A')}%, K/D {f.get('kd','N/A')}")
        if external.get("csgostats"):
            c = external["csgostats"]
            sections.append(f"CSGOSTATS: Rating {c.get('rating','N/A')}, KAST {c.get('kast','N/A')}%, Opening kills {c.get('opening_kills','N/A')}")

        if not sections:
            return "Zadna externa data k analyze."

        prompt = f"""Jsi CS2 coach. Analyzuj tato externa data hrace "{player_name}" v cestine:

{chr(10).join(sections)}

Poskytni:
1. Co rika kazdy zdroj o hracovem stylu
2. Silne stranky (ze vsech zdroju)
3. Slabe stranky (ze vsech zdroju)  
4. Co prioritizovat pro zlepseni
5. Odhadovany skutecny level hrace

Bud specificKy a prakticKy. V cestine."""

        result = self._generate(prompt)
        return result or "Nepodarilo se analyzovat externa data."

    # ─── FALLBACK ────────────────────────────────────────────────

    def _fallback_stats_analysis(self, stats: Dict) -> str:
        kd = stats.get("kd_ratio", 0)
        wr = stats.get("win_rate", 0)
        hs = stats.get("hs_rate", 0)
        lines = ["**Automatická analýza** (AI není k dispozici)\n"]
        lines.append("K/D: " + ("Výborné (>1.5)" if kd>=1.5 else "Průměrné (>1.0)" if kd>=1.0 else "Pod průměrem — zaměř se na přežití"))
        lines.append("HS Rate: " + ("Skvělé (>45%)" if hs>=45 else "Průměrné" if hs>=30 else "Nízké — procvičuj crosshair placement"))
        lines.append("Win Rate: " + ("Dobrá (>55%)" if wr>=55 else "Vyvážená" if wr>=45 else "Pod 45% — zaměř se na týmovou hru"))
        lines.append("\nNastav GOOGLE_AI_KEY v .env pro AI analýzu.")
        return "\n".join(lines)

    def _fallback_match_analysis(self, match_data: Dict) -> str:
        k = match_data.get("kills", 0)
        d = match_data.get("deaths", 0)
        result = match_data.get("result", "?")
        lines = [f"**Shrnutí zápasu** (bez AI)\n", f"Výsledek: **{result}**", f"K/D: **{k}/{d}**"]
        lines.append("Dobrý výkon — více zabití!" if k > d else "Náročný zápas — hraj opatrněji.")
        return "\n".join(lines)
