"""
🔮 MODULE PRONOSTICS ULTRA-PROFESSIONNEL - FootBot
Version Premium avec Groq IA + Statistiques Avancées
Prédictions: Victoire, Corners, Cartons, Buts, etc.
"""
import asyncio
import aiohttp
import logging
import os
import json
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("footbot.predictions")

# ============================================================================
# ⚙️ CONFIGURATION GROQ
# ============================================================================

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
GROQ_MODEL = "llama-3.3-70b-versatile"

# Configuration du module
PREDICTIONS_DIR = Path("data/footbot/predictions")
PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)

PREDICTIONS_CACHE_FILE = PREDICTIONS_DIR / "predictions_cache.json"
PREDICTIONS_HISTORY_FILE = PREDICTIONS_DIR / "predictions_history.json"
PREDICTIONS_STATS_FILE = PREDICTIONS_DIR / "predictions_stats.json"

# Limites et configuration
CACHE_DURATION = 1800  # 30 minutes
MAX_PREDICTIONS_PER_USER = 10  # Par jour
RATE_LIMIT_WINDOW = 60  # 1 minute
RATE_LIMIT_MAX = 5  # 5 prédictions par minute

# ============================================================================
# 🎯 PROMPT SYSTÈME ULTRA-PROFESSIONNEL
# ============================================================================

PROFESSIONAL_SYSTEM_PROMPT = """Tu es un analyste sportif professionnel de niveau expert avec 15+ ans d'expérience dans l'analyse de matchs et les statistiques sportives avancées.

MISSION: Fournir une analyse détaillée et des prédictions précises sur plusieurs aspects du match.

ASPECTS À ANALYSER:
1. **Résultat du match** (Victoire Équipe 1, Match Nul, Victoire Équipe 2)
2. **Score exact probable** (ex: 2-1, 1-1, 3-0)
3. **Total de buts** (Plus/Moins de 2.5, Plus/Moins de 3.5)
4. **Les deux équipes marquent** (Oui/Non - BTTS)
5. **Nombre de corners** (Total et par équipe)
6. **Cartons jaunes** (Total match)
7. **Cartons rouges** (Probabilité et nombre)
8. **Mi-temps/Fin** (Résultat à la pause vs résultat final)
9. **Buteur probable** (Si données disponibles)
10. **Score à la mi-temps**

MÉTHODOLOGIE D'ANALYSE:
- Analyse la forme récente (si disponible)
- Évalue les confrontations directes historiques
- Considère le contexte (domicile/extérieur, enjeux)
- Calcule les probabilités statistiques
- Identifie les patterns et tendances

RÈGLES DE CONFIANCE:
- 65-70%: Prédiction très solide avec multiples facteurs concordants
- 55-64%: Prédiction solide avec bons indicateurs
- 45-54%: Prédiction modérée avec incertitudes
- 35-44%: Prédiction faible, données limitées
- <35%: Trop incertain pour prédire

FORMAT JSON STRICT (ESSENTIEL):
{
  "match_analysis": {
    "overview": "Vue d'ensemble du match et contexte",
    "key_factors": ["facteur1", "facteur2", "facteur3"],
    "tactical_analysis": "Analyse tactique attendue"
  },
  
  "predictions": {
    "match_result": {
      "prediction": "1 (Victoire Équipe 1) ou X (Nul) ou 2 (Victoire Équipe 2)",
      "confidence": 0-70,
      "odds_estimate": "Cote estimée (ex: 1.85)",
      "reasoning": "Justification détaillée"
    },
    
    "exact_score": {
      "most_likely": "2-1",
      "alternatives": ["1-1", "2-0"],
      "confidence": 0-70,
      "reasoning": "Justification"
    },
    
    "total_goals": {
      "over_2_5": {
        "prediction": "Oui ou Non",
        "confidence": 0-70,
        "reasoning": "Justification"
      },
      "over_3_5": {
        "prediction": "Oui ou Non",
        "confidence": 0-70
      },
      "expected_total": "2-3 buts"
    },
    
    "both_teams_score": {
      "prediction": "Oui ou Non",
      "confidence": 0-70,
      "reasoning": "Justification"
    },
    
    "corners": {
      "total_corners": {
        "prediction": "9-11 corners",
        "over_9_5": "Oui ou Non",
        "over_10_5": "Oui ou Non",
        "confidence": 0-70
      },
      "team1_corners": "4-6",
      "team2_corners": "5-7",
      "reasoning": "Justification"
    },
    
    "cards": {
      "yellow_cards": {
        "total": "3-5 cartons jaunes",
        "over_3_5": "Oui ou Non",
        "over_4_5": "Oui ou Non",
        "confidence": 0-70
      },
      "red_cards": {
        "probability": "Faible/Moyenne/Élevée",
        "expected": "0-1 carton rouge",
        "confidence": 0-70
      },
      "reasoning": "Justification basée sur historique arbitrage"
    },
    
    "halftime": {
      "halftime_result": "1/X/2",
      "halftime_score": "1-0",
      "confidence": 0-70
    },
    
    "special_bets": {
      "first_goal": {
        "team": "Équipe 1 ou Équipe 2",
        "timeframe": "0-15 min / 15-30 min / etc.",
        "confidence": 0-70
      },
      "clean_sheet": {
        "team1": "Oui ou Non",
        "team2": "Oui ou Non",
        "confidence": 0-70
      }
    }
  },
  
  "risk_analysis": {
    "risk_level": "Faible/Moyen/Élevé",
    "uncertainty_factors": ["facteur1", "facteur2"],
    "recommendation": "Conseil général"
  },
  
  "statistical_summary": {
    "overall_confidence": 0-70,
    "data_quality": "Excellent/Bon/Moyen/Faible",
    "prediction_reliability": "Description"
  },
  
  "disclaimer": "Avertissement obligatoire sur imprévisibilité"
}

IMPORTANT:
- Sois précis dans les fourchettes (ex: "8-10 corners", pas "beaucoup")
- Justifie CHAQUE prédiction
- Si données manquantes, indique-le clairement
- Ne dépasse JAMAIS 70% de confiance
- Utilise un langage professionnel mais accessible"""

# ============================================================================
# 💾 GESTIONNAIRE DE CACHE & HISTORIQUE
# ============================================================================

class PredictionsManager:
    """Gestionnaire professionnel des prédictions avec cache et historique"""
    
    @staticmethod
    def load_cache() -> Dict:
        """Charge le cache des prédictions"""
        try:
            if PREDICTIONS_CACHE_FILE.exists():
                with open(PREDICTIONS_CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                
                # Nettoyer les entrées expirées
                now = time.time()
                return {
                    k: v for k, v in cache.items()
                    if now - v.get('timestamp', 0) < CACHE_DURATION
                }
        except (json.JSONDecodeError, IOError):
            pass
        return {}
    
    @staticmethod
    def save_cache(cache: Dict):
        """Sauvegarde le cache"""
        try:
            with open(PREDICTIONS_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Erreur sauvegarde cache: {e}")
    
    @staticmethod
    def load_history() -> Dict:
        """Charge l'historique des prédictions"""
        try:
            if PREDICTIONS_HISTORY_FILE.exists():
                with open(PREDICTIONS_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return {"predictions": [], "total": 0}
    
    @staticmethod
    def save_history(history: Dict):
        """Sauvegarde l'historique"""
        try:
            with open(PREDICTIONS_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Erreur sauvegarde historique: {e}")
    
    @staticmethod
    def add_to_history(user_id: int, match: Dict, prediction: Dict):
        """Ajoute une prédiction à l'historique"""
        history = PredictionsManager.load_history()
        
        entry = {
            'prediction_id': f"pred_{int(time.time())}_{user_id}",
            'user_id': user_id,
            'match_id': match['id'],
            'match_title': match['title'],
            'sport': match['sport'],
            'prediction_data': prediction,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending'  # pending, won, lost, void
        }
        
        history['predictions'].append(entry)
        history['total'] = len(history['predictions'])
        
        # Garder seulement les 1000 dernières
        if len(history['predictions']) > 1000:
            history['predictions'] = history['predictions'][-1000:]
        
        PredictionsManager.save_history(history)
    
    @staticmethod
    def get_user_stats(user_id: int) -> Dict:
        """Statistiques d'un utilisateur"""
        history = PredictionsManager.load_history()
        user_preds = [p for p in history['predictions'] if p['user_id'] == user_id]
        
        today = datetime.now().date().isoformat()
        today_preds = [
            p for p in user_preds 
            if p['timestamp'][:10] == today
        ]
        
        return {
            'total_predictions': len(user_preds),
            'today_predictions': len(today_preds),
            'can_predict': len(today_preds) < MAX_PREDICTIONS_PER_USER
        }

# ============================================================================
# 🤖 PRÉDICTEUR PROFESSIONNEL GROQ
# ============================================================================

class ProfessionalGroqPredictor:
    """Prédicteur ultra-professionnel utilisant Groq IA"""
    
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache = PredictionsManager.load_cache()
        self.rate_limiter = {}  # {user_id: [timestamps]}
        
        self.stats = {
            'total_predictions': 0,
            'cache_hits': 0,
            'api_calls': 0,
            'errors': 0,
            'avg_confidence': 0.0
        }
    
    async def __aenter__(self):
        """Initialise la session HTTP"""
        if not self.api_key:
            raise ValueError("❌ GROQ_API_KEY manquante! Obtenez-la sur https://console.groq.com")
        
        timeout = aiohttp.ClientTimeout(total=60)
        self.session = aiohttp.ClientSession(timeout=timeout)
        logger.info("✅ Prédicteur Groq initialisé")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ferme la session"""
        if self.session:
            await self.session.close()
    
    def check_rate_limit(self, user_id: int) -> Tuple[bool, int]:
        """Vérifie le rate limit utilisateur"""
        now = time.time()
        
        if user_id not in self.rate_limiter:
            self.rate_limiter[user_id] = []
        
        # Nettoyer les timestamps expirés
        self.rate_limiter[user_id] = [
            ts for ts in self.rate_limiter[user_id]
            if now - ts < RATE_LIMIT_WINDOW
        ]
        
        count = len(self.rate_limiter[user_id])
        
        if count >= RATE_LIMIT_MAX:
            wait_time = int(RATE_LIMIT_WINDOW - (now - self.rate_limiter[user_id][0]))
            return False, wait_time
        
        self.rate_limiter[user_id].append(now)
        return True, 0
    
    async def fetch_advanced_stats(self, team1: str, team2: str, sport: str) -> Dict:
        """
        Collecte des statistiques avancées
        TODO: Implémenter avec vraies sources (API-Football, etc.)
        """
        
        # Simulation de données avancées
        # Dans une version production, remplacer par de vraies APIs
        
        advanced_stats = {
            "data_source": "Simulation (remplacer par vraie API)",
            "team1": {
                "name": team1,
                "recent_form": "W-W-D-L-W",  # 5 derniers matchs
                "goals_scored_avg": 1.8,
                "goals_conceded_avg": 1.2,
                "corners_avg": 5.3,
                "cards_yellow_avg": 2.1,
                "cards_red_avg": 0.1,
                "home_advantage": True if "home" in sport.lower() else None
            },
            "team2": {
                "name": team2,
                "recent_form": "L-W-W-D-L",
                "goals_scored_avg": 1.5,
                "goals_conceded_avg": 1.4,
                "corners_avg": 4.8,
                "cards_yellow_avg": 2.3,
                "cards_red_avg": 0.08
            },
            "head_to_head": {
                "last_5_matches": [
                    {"date": "2024-10-15", "score": "2-1", "winner": team1},
                    {"date": "2024-05-20", "score": "1-1", "winner": "draw"},
                    {"date": "2023-12-10", "score": "0-2", "winner": team2}
                ],
                "total_meetings": 15,
                "team1_wins": 7,
                "draws": 4,
                "team2_wins": 4
            },
            "league_context": {
                "team1_position": "5ème",
                "team2_position": "8ème",
                "competition": sport,
                "importance": "Standard"
            },
            "weather": {
                "condition": "Clair",
                "temperature": "15°C",
                "wind": "Faible"
            },
            "referee": {
                "name": "À déterminer",
                "avg_yellow_cards": 3.8,
                "avg_red_cards": 0.15,
                "strict_level": "Moyen"
            },
            "injuries_suspensions": {
                "team1": ["Joueur A (suspendu)", "Joueur B (blessé)"],
                "team2": ["Joueur C (blessé)"]
            },
            "betting_odds": {
                "1": 2.10,
                "X": 3.40,
                "2": 3.60,
                "over_2_5": 1.85,
                "btts_yes": 1.70
            },
            "data_quality": "simulated",
            "last_updated": datetime.now().isoformat()
        }
        
        logger.info(f"📊 Stats collectées pour {team1} vs {team2}")
        return advanced_stats
    
    async def call_groq_api(self, messages: List[Dict]) -> Optional[str]:
        """Appel à l'API Groq avec gestion d'erreurs professionnelle"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.2,  # Basse température pour cohérence
            "max_tokens": 3000,
            "top_p": 0.95,
            "response_format": {"type": "json_object"}
        }
        
        try:
            self.stats['api_calls'] += 1
            
            async with self.session.post(
                GROQ_API_URL, 
                headers=headers, 
                json=payload
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    content = data['choices'][0]['message']['content']
                    
                    # Logs de debug
                    usage = data.get('usage', {})
                    logger.info(
                        f"✅ Groq API success | "
                        f"Tokens: {usage.get('total_tokens', 0)} | "
                        f"Time: {data.get('x_groq', {}).get('usage', {}).get('total_time', 0):.2f}s"
                    )
                    
                    return content
                
                elif response.status == 429:
                    logger.warning("⚠️ Rate limit Groq atteint")
                    self.stats['errors'] += 1
                    return None
                
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Groq API error {response.status}: {error_text[:200]}")
                    self.stats['errors'] += 1
                    return None
        
        except asyncio.TimeoutError:
            logger.error("⏱️ Timeout Groq API")
            self.stats['errors'] += 1
            return None
        
        except Exception as e:
            logger.error(f"❌ Exception Groq API: {e}")
            self.stats['errors'] += 1
            return None
    
    async def analyze_match_professional(
        self, 
        match: Dict, 
        user_id: int
    ) -> Dict:
        """
        Analyse ultra-professionnelle d'un match
        Retourne prédictions complètes sur victoire, corners, cartons, etc.
        """
        
        # Vérifier rate limit
        can_proceed, wait_time = self.check_rate_limit(user_id)
        if not can_proceed:
            return {
                "error": "rate_limit",
                "message": f"⏳ Trop de requêtes. Attendez {wait_time}s",
                "wait_time": wait_time
            }
        
        # Vérifier quota journalier
        user_stats = PredictionsManager.get_user_stats(user_id)
        if not user_stats['can_predict']:
            return {
                "error": "daily_limit",
                "message": f"🚫 Limite quotidienne atteinte ({MAX_PREDICTIONS_PER_USER}/jour)",
                "used": user_stats['today_predictions'],
                "limit": MAX_PREDICTIONS_PER_USER
            }
        
        team1 = match.get('team1', '')
        team2 = match.get('team2', '')
        sport = match.get('sport_name', 'Sport')
        
        if not team1 or not team2:
            return self._create_error_response("Données de match incomplètes")
        
        # Vérifier le cache
        cache_key = f"pred_{match['id']}_{user_id}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached.get('timestamp', 0) < CACHE_DURATION:
                self.stats['cache_hits'] += 1
                logger.info(f"💾 Cache hit pour {team1} vs {team2}")
                return cached['data']
        
        # Collecter statistiques avancées
        try:
            stats = await self.fetch_advanced_stats(team1, team2, sport)
        except Exception as e:
            logger.error(f"Erreur collecte stats: {e}")
            stats = {"error": "Stats unavailable"}
        
        # Construire le prompt ultra-détaillé
        user_prompt = f"""Analyse professionnelle approfondie du match suivant:

═══════════════════════════════════════════════════════════════
📋 INFORMATIONS DU MATCH
═══════════════════════════════════════════════════════════════

🏟️ **Match:** {team1} vs {team2}
🏆 **Compétition:** {sport}
⏰ **Horaire:** {match.get('start_time', 'En direct')}
📅 **Date:** {datetime.now().strftime('%d/%m/%Y')}
🔴 **Statut:** {match.get('status', 'À venir')}

═══════════════════════════════════════════════════════════════
📊 DONNÉES STATISTIQUES DISPONIBLES
═══════════════════════════════════════════════════════════════

{json.dumps(stats, indent=2, ensure_ascii=False)}

═══════════════════════════════════════════════════════════════
🎯 ANALYSES REQUISES
═══════════════════════════════════════════════════════════════

Tu dois fournir des prédictions DÉTAILLÉES sur:

1. ✅ **Résultat du match** (1/X/2)
2. ⚽ **Score exact** le plus probable
3. 📊 **Total de buts** (Over/Under 2.5 et 3.5)
4. 🥅 **Les deux équipes marquent** (BTTS)
5. 🚩 **Corners totaux et par équipe**
6. 🟨 **Cartons jaunes** (total et over/under)
7. 🟥 **Cartons rouges** (probabilité)
8. ⏱️ **Score à la mi-temps**
9. 🎲 **Paris spéciaux** (premier but, clean sheet)

═══════════════════════════════════════════════════════════════
⚠️ CONSIGNES IMPORTANTES
═══════════════════════════════════════════════════════════════

- Sois PRÉCIS: utilise des fourchettes (ex: "8-10 corners")
- JUSTIFIE chaque prédiction avec des arguments solides
- Indique le niveau de CONFIANCE (max 70%)
- Si données insuffisantes, DIS-LE clairement
- Utilise les stats pour supporter tes analyses
- Format JSON STRICT obligatoire

Fournis maintenant ton analyse complète au format JSON."""

        messages = [
            {"role": "system", "content": PROFESSIONAL_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        # Appeler Groq
        logger.info(f"🤖 Analyse IA pour {team1} vs {team2}...")
        
        response = await self.call_groq_api(messages)
        
        if not response:
            return self._create_error_response("API Groq indisponible")
        
        # Parser la réponse JSON
        try:
            # Nettoyer la réponse
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            prediction = json.loads(response)
            
            # Valider et normaliser
            prediction = self._validate_prediction(prediction)
            
            # Ajouter métadonnées
            prediction['meta'] = {
                'match_id': match['id'],
                'match_title': match['title'],
                'analyzed_at': datetime.now().isoformat(),
                'model': GROQ_MODEL,
                'user_id': user_id,
                'cache_key': cache_key
            }
            
            # Mettre en cache
            self.cache[cache_key] = {
                'data': prediction,
                'timestamp': time.time()
            }
            PredictionsManager.save_cache(self.cache)
            
            # Ajouter à l'historique
            PredictionsManager.add_to_history(user_id, match, prediction)
            
            # Stats
            self.stats['total_predictions'] += 1
            overall_conf = prediction.get('statistical_summary', {}).get('overall_confidence', 0)
            self.stats['avg_confidence'] = (
                (self.stats['avg_confidence'] * (self.stats['total_predictions'] - 1) + overall_conf)
                / self.stats['total_predictions']
            )
            
            logger.info(
                f"✅ Prédiction générée | "
                f"Confiance: {overall_conf}% | "
                f"User: {user_id}"
            )
            
            return prediction
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON invalide: {e}")
            logger.debug(f"Réponse brute: {response[:500]}")
            return self._create_error_response("Format de réponse invalide")
        
        except Exception as e:
            logger.error(f"❌ Erreur parsing: {e}")
            return self._create_error_response(str(e))
    
    def _validate_prediction(self, prediction: Dict) -> Dict:
        """Valide et normalise une prédiction"""
        
        # Forcer les limites de confiance
        if 'predictions' in prediction:
            for category, data in prediction['predictions'].items():
                if isinstance(data, dict) and 'confidence' in data:
                    if data['confidence'] > 70:
                        data['confidence'] = 70
        
        # Assurer la présence du disclaimer
        if not prediction.get('disclaimer'):
            prediction['disclaimer'] = (
                "⚠️ Le sport est imprévisible. "
                "Ces prédictions sont basées sur des analyses statistiques et ne garantissent aucun résultat. "
                "À utiliser pour divertissement uniquement."
            )
        
        # Assurer statistical_summary
        if 'statistical_summary' not in prediction:
            prediction['statistical_summary'] = {
                'overall_confidence': 50,
                'data_quality': 'Moyen',
                'prediction_reliability': 'Modérée'
            }
        
        return prediction
    
    def _create_error_response(self, error_msg: str) -> Dict:
        """Crée une réponse d'erreur formatée"""
        return {
            "error": True,
            "message": error_msg,
            "match_analysis": {
                "overview": f"Erreur: {error_msg}",
                "key_factors": [],
                "tactical_analysis": "Analyse indisponible"
            },
            "predictions": {},
            "statistical_summary": {
                "overall_confidence": 0,
                "data_quality": "Indisponible",
                "prediction_reliability": "Erreur"
            },
            "disclaimer": "⚠️ Service temporairement indisponible"
        }

# ============================================================================
# 🎨 FORMATAGE TELEGRAM ULTRA-PROFESSIONNEL
# ============================================================================

def format_professional_prediction(match: Dict, prediction: Dict) -> str:
    """Formate une prédiction de manière ultra-professionnelle pour Telegram"""
    
    # Vérifier si erreur
    if prediction.get('error'):
        if prediction.get('error') == 'rate_limit':
            return f"""⏳ <b>LIMITE DE REQUÊTES</b>

🚫 Vous avez atteint la limite temporaire.

⏰ Attendez <b>{prediction['wait_time']}s</b> avant de réessayer.

💡 Ceci évite la surcharge du serveur."""

        elif prediction.get('error') == 'daily_limit':
            return f"""🚫 <b>QUOTA JOURNALIER ATTEINT</b>

Vous avez utilisé vos <b>{prediction['used']}/{prediction['limit']}</b> prédictions quotidiennes.

🔄 Revenez demain pour de nouvelles analyses !

💡 Cette limite assure un service équitable pour tous."""

        else:
            return f"""❌ <b>ERREUR</b>

{prediction.get('message', 'Erreur inconnue')}

🔄 Réessayez dans quelques instants."""
    
    # Récupérer les données
    ma = prediction.get('match_analysis', {})
    preds = prediction.get('predictions', {})
    risk = prediction.get('risk_analysis', {})
    stats_summary = prediction.get('statistical_summary', {})
    
    overall_conf = stats_summary.get('overall_confidence', 0)
    
    # Emoji de confiance
    if overall_conf >= 60:
        conf_emoji = "🟢"
        conf_text = "ÉLEVÉE"
    elif overall_conf >= 45:
        conf_emoji = "🟡"
        conf_text = "MOYENNE"
    else:
        conf_emoji = "🔴"
        conf_text = "FAIBLE"
    
    msg = f"""╔═══════════════════════════════════════╗
   🔮 <b>ANALYSE PROFESSIONNELLE IA</b>
╚═══════════════════════════════════════╝

{match['sport_icon']} <b>{match['title']}</b>
⏰ {match.get('start_time', 'N/A')} | 📅 {datetime.now().strftime('%d/%m/%Y')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 <b>VUE D'ENSEMBLE</b>

{ma.get('overview', 'Analyse en cours...')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 <b>PRÉDICTIONS DÉTAILLÉES</b>

"""
    
    # 1. Résultat du match
    match_result = preds.get('match_result', {})
    if match_result:
        result_pred = match_result.get('prediction', 'N/A')
        result_conf = match_result.get('confidence', 0)
        result_emoji = "🟢" if result_conf >= 55 else "🟡" if result_conf >= 40 else "🔴"
        
        msg += f"""┌─ <b>1️⃣ RÉSULTAT DU MATCH</b>
│
│ 🏆 Prédiction: <b>{result_pred}</b>
│ {result_emoji} Confiance: <b>{result_conf}%</b>
│ 💰 Cote estimée: <code>{match_result.get('odds_estimate', 'N/A')}</code>
│
│ 📝 {match_result.get('reasoning', 'N/A')}
└────────────────────────────────────────

"""
    
    # 2. Score exact
    exact_score = preds.get('exact_score', {})
    if exact_score:
        score = exact_score.get('most_likely', 'N/A')
        alts = ', '.join(exact_score.get('alternatives', []))
        score_conf = exact_score.get('confidence', 0)
        
        msg += f"""┌─ <b>2️⃣ SCORE EXACT PROBABLE</b>
│
│ ⚽ Score prédit: <b>{score}</b>
│ 📊 Alternatives: <code>{alts}</code>
│ 🎯 Confiance: <b>{score_conf}%</b>
│
│ 📝 {exact_score.get('reasoning', 'N/A')}
└────────────────────────────────────────

"""
    
    # 3. Total de buts
    total_goals = preds.get('total_goals', {})
    if total_goals:
        over25 = total_goals.get('over_2_5', {})
        over35 = total_goals.get('over_3_5', {})
        expected = total_goals.get('expected_total', 'N/A')
        
        msg += f"""┌─ <b>3️⃣ TOTAL DE BUTS</b>
│
│ 📈 Attendu: <b>{expected}</b>
│
│ 🎲 Over 2.5: <b>{over25.get('prediction', 'N/A')}</b> ({over25.get('confidence', 0)}%)
│ 🎲 Over 3.5: <b>{over35.get('prediction', 'N/A')}</b> ({over35.get('confidence', 0)}%)
│
│ 📝 {over25.get('reasoning', 'N/A')}
└────────────────────────────────────────

"""
    
    # 4. Les deux équipes marquent
    btts = preds.get('both_teams_score', {})
    if btts:
        btts_pred = btts.get('prediction', 'N/A')
        btts_conf = btts.get('confidence', 0)
        
        msg += f"""┌─ <b>4️⃣ LES DEUX ÉQUIPES MARQUENT (BTTS)</b>
│
│ 🥅 Prédiction: <b>{btts_pred}</b>
│ 🎯 Confiance: <b>{btts_conf}%</b>
│
│ 📝 {btts.get('reasoning', 'N/A')}
└────────────────────────────────────────

"""
    
    # 5. Corners
    corners = preds.get('corners', {})
    if corners:
        total_corn = corners.get('total_corners', {})
        team1_corn = corners.get('team1_corners', 'N/A')
        team2_corn = corners.get('team2_corners', 'N/A')
        
        msg += f"""┌─ <b>5️⃣ CORNERS</b>
│
│ 🚩 Total prédit: <b>{total_corn.get('prediction', 'N/A')}</b>
│ 🔵 {match.get('team1', 'Équipe 1')}: <code>{team1_corn}</code>
│ 🔴 {match.get('team2', 'Équipe 2')}: <code>{team2_corn}</code>
│
│ 📊 Over 9.5: <b>{total_corn.get('over_9_5', 'N/A')}</b>
│ 📊 Over 10.5: <b>{total_corn.get('over_10_5', 'N/A')}</b>
│ 🎯 Confiance: <b>{total_corn.get('confidence', 0)}%</b>
│
│ 📝 {corners.get('reasoning', 'N/A')}
└────────────────────────────────────────

"""
    
    # 6. Cartons
    cards = preds.get('cards', {})
    if cards:
        yellow = cards.get('yellow_cards', {})
        red = cards.get('red_cards', {})
        
        msg += f"""┌─ <b>6️⃣ CARTONS</b>
│
│ 🟨 <b>CARTONS JAUNES</b>
│ ├─ Total: <b>{yellow.get('total', 'N/A')}</b>
│ ├─ Over 3.5: <b>{yellow.get('over_3_5', 'N/A')}</b>
│ ├─ Over 4.5: <b>{yellow.get('over_4_5', 'N/A')}</b>
│ └─ Confiance: <b>{yellow.get('confidence', 0)}%</b>
│
│ 🟥 <b>CARTONS ROUGES</b>
│ ├─ Probabilité: <b>{red.get('probability', 'N/A')}</b>
│ ├─ Attendu: <b>{red.get('expected', 'N/A')}</b>
│ └─ Confiance: <b>{red.get('confidence', 0)}%</b>
│
│ 📝 {cards.get('reasoning', 'N/A')}
└────────────────────────────────────────

"""
    
    # 7. Mi-temps
    halftime = preds.get('halftime', {})
    if halftime:
        ht_result = halftime.get('halftime_result', 'N/A')
        ht_score = halftime.get('halftime_score', 'N/A')
        ht_conf = halftime.get('confidence', 0)
        
        msg += f"""┌─ <b>7️⃣ MI-TEMPS</b>
│
│ ⏱️ Résultat HT: <b>{ht_result}</b>
│ ⚽ Score HT: <b>{ht_score}</b>
│ 🎯 Confiance: <b>{ht_conf}%</b>
└────────────────────────────────────────

"""
    
    # 8. Paris spéciaux
    special = preds.get('special_bets', {})
    if special:
        first_goal = special.get('first_goal', {})
        clean_sheet = special.get('clean_sheet', {})
        
        if first_goal or clean_sheet:
            msg += f"""┌─ <b>8️⃣ PARIS SPÉCIAUX</b>
│
"""
            
            if first_goal:
                msg += f"""│ ⚡ <b>PREMIER BUT</b>
│ ├─ Équipe: <b>{first_goal.get('team', 'N/A')}</b>
│ ├─ Période: <code>{first_goal.get('timeframe', 'N/A')}</code>
│ └─ Confiance: <b>{first_goal.get('confidence', 0)}%</b>
│
"""
            
            if clean_sheet:
                msg += f"""│ 🛡️ <b>CLEAN SHEET</b>
│ ├─ {match.get('team1', 'Équipe 1')}: <b>{clean_sheet.get('team1', 'N/A')}</b>
│ ├─ {match.get('team2', 'Équipe 2')}: <b>{clean_sheet.get('team2', 'N/A')}</b>
│ └─ Confiance: <b>{clean_sheet.get('confidence', 0)}%</b>
"""
            
            msg += "└────────────────────────────────────────\n\n"
    
    # Analyse de risque
    if risk:
        risk_level = risk.get('risk_level', 'Moyen')
        risk_emoji = "🔴" if risk_level == "Élevé" else "🟡" if risk_level == "Moyen" else "🟢"
        
        msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>ANALYSE DE RISQUE</b>

{risk_emoji} Niveau de risque: <b>{risk_level}</b>

"""
        
        uncertainties = risk.get('uncertainty_factors', [])
        if uncertainties:
            msg += "🔍 <b>Facteurs d'incertitude:</b>\n"
            for uf in uncertainties[:3]:
                msg += f"  • {uf}\n"
            msg += "\n"
        
        recommendation = risk.get('recommendation', '')
        if recommendation:
            msg += f"💡 <b>Recommandation:</b> {recommendation}\n\n"
    
    # Résumé statistique
    msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>RÉSUMÉ STATISTIQUE</b>

{conf_emoji} Confiance globale: <b>{overall_conf}% ({conf_text})</b>
📈 Qualité des données: <b>{stats_summary.get('data_quality', 'N/A')}</b>
🎯 Fiabilité: <b>{stats_summary.get('prediction_reliability', 'N/A')}</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>AVERTISSEMENT LÉGAL</b>

{prediction.get('disclaimer', '')}

<b>🎮 DIVERTISSEMENT UNIQUEMENT</b>
🚫 Ne jamais parier plus que vous ne pouvez perdre
⚖️ Le gambling peut créer une dépendance
📞 Aide: https://www.joueurs-info-service.fr

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<i>🤖 Généré par Groq IA | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</i>
<i>🔬 Modèle: {GROQ_MODEL}</i>"""
    
    return msg

# ============================================================================
# 🎯 HANDLER PRINCIPAL POUR TELEGRAM
# ============================================================================

async def handle_prediction_request(query, match_id: str, DataManager):
    """
    Handler principal pour les demandes de prédiction
    À intégrer dans callback_handler de footbot.py
    """
    user_id = query.from_user.id
    
    # Message initial
    await query.answer("🔮 Lancement de l'analyse IA...")
    
    await query.edit_message_text(
        "╔═══════════════════════════════════════╗\n"
        "   ⏳ <b>ANALYSE IA EN COURS</b>\n"
        "╚═══════════════════════════════════════╝\n\n"
        "🤖 Initialisation Groq IA...\n"
        "📊 Collecte des statistiques...\n"
        "🧠 Analyse des tendances...\n"
        "🎯 Calcul des probabilités...\n\n"
        "⏱️ <i>Cela prend généralement 10-30 secondes</i>\n\n"
        "💡 <b>Analyses incluses:</b>\n"
        "  • Résultat du match\n"
        "  • Score exact\n"
        "  • Total de buts\n"
        "  • Corners\n"
        "  • Cartons jaunes/rouges\n"
        "  • Et bien plus...",
        parse_mode='HTML'
    )
    
    # Récupérer le match
    data = DataManager.load_data()
    match = next((m for m in data['matches'] if m['id'] == match_id), None)
    
    if not match:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]
        await query.edit_message_text(
            "❌ <b>Match introuvable</b>\n\n"
            "Le match n'est plus disponible.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Analyser avec Groq
    try:
        async with ProfessionalGroqPredictor() as predictor:
            prediction = await predictor.analyze_match_professional(match, user_id)
    except Exception as e:
        logger.error(f"Erreur analyse: {e}")
        prediction = {"error": True, "message": f"Erreur technique: {str(e)[:100]}"}
    
    # Formater le message
    message = format_professional_prediction(match, prediction)
    
    # Créer le clavier
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    keyboard = []
    
    if not prediction.get('error'):
        keyboard.append([
            InlineKeyboardButton("🔄 Nouvelle analyse", callback_data=f"predict_{match_id}")
        ])
    
    keyboard.extend([
        [InlineKeyboardButton("🔙 Retour au match", callback_data=f"watch_{match_id}")],
        [InlineKeyboardButton("📊 Mes stats", callback_data="prediction_stats")],
        [InlineKeyboardButton("🏠 Menu principal", callback_data="main_menu")]
    ])
    
    # Envoyer
    try:
        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Erreur envoi message: {e}")
        # Fallback: message plus court
        await query.edit_message_text(
            message[:4000] + "\n\n<i>[Message tronqué]</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ============================================================================
# 📊 STATISTIQUES UTILISATEUR
# ============================================================================

async def show_user_prediction_stats(query):
    """Affiche les statistiques de prédictions de l'utilisateur"""
    user_id = query.from_user.id
    await query.answer()
    
    stats = PredictionsManager.get_user_stats(user_id)
    history = PredictionsManager.load_history()
    user_preds = [p for p in history['predictions'] if p['user_id'] == user_id]
    
    # Analyser l'historique
    total = stats['total_predictions']
    today = stats['today_predictions']
    remaining = MAX_PREDICTIONS_PER_USER - today
    
    msg = f"""╔═══════════════════════════════════════╗
   📊 <b>VOS STATISTIQUES</b>
╚═══════════════════════════════════════╝

👤 <b>Utilisateur:</b> <code>{user_id}</code>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 <b>UTILISATION</b>

🔮 Total prédictions: <b>{total}</b>
📅 Aujourd'hui: <b>{today}/{MAX_PREDICTIONS_PER_USER}</b>
✅ Restantes: <b>{remaining}</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🕐 <b>DERNIÈRES ANALYSES</b>

"""
    
    # Afficher les 5 dernières
    recent = user_preds[-5:][::-1]  # Inverser pour avoir les plus récentes en premier
    
    if recent:
        for pred in recent:
            match_title = pred.get('match_title', 'Match inconnu')
            timestamp = pred.get('timestamp', '')[:16].replace('T', ' ')
            msg += f"• {match_title}\n  <i>{timestamp}</i>\n\n"
    else:
        msg += "<i>Aucune prédiction encore</i>\n\n"
    
    msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 <b>LIMITES QUOTIDIENNES</b>

• Max {MAX_PREDICTIONS_PER_USER} prédictions/jour
• Réinitialisation à minuit (UTC)
• Cache de 30 minutes par match

🎯 <b>Ces limites assurent un service équitable pour tous</b>"""
    
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]
    
    await query.edit_message_text(
        msg,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

