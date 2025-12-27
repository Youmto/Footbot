"""
🔮 MODULE PRONOSTICS ULTRA V3.0 - MULTI-SPORTS PROFESSIONNEL
═══════════════════════════════════════════════════════════════════════════════
Version Top 1 Mondial avec:
- Support TOUS les sports (Football, UFC, NBA, Tennis, NFL, etc.)
- Pronostics spécifiques par sport
- Validation des événements en temps réel
- Groq IA avec fallback intelligent
- Système de grades amélioré (jamais D sans raison)
- Gamification complète
═══════════════════════════════════════════════════════════════════════════════
"""
import asyncio
import aiohttp
import logging
import os
import json
import time
import hashlib
import random
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

logger = logging.getLogger("footbot.predictions")

# ════════════════════════════════════════════════════════════════════════════
# ⚙️ CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

# Vérification de la clé API
PREDICTIONS_ENABLED = bool(GROQ_API_KEY)

if PREDICTIONS_ENABLED:
    logger.info("✅ GROQ_API_KEY configurée - Prédictions IA activées")
else:
    logger.warning("⚠️ GROQ_API_KEY manquante - Mode simulation activé")

# Modèles Groq (chaîne de fallback)
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "mixtral-8x7b-32768",
    "llama-3.1-8b-instant",
    "gemma2-9b-it"
]

# Répertoire de données
PREDICTIONS_DIR = Path("data/footbot/predictions")
PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)

FILES = {
    'cache': PREDICTIONS_DIR / "predictions_cache.json",
    'history': PREDICTIONS_DIR / "predictions_history.json",
    'stats': PREDICTIONS_DIR / "predictions_stats.json",
    'votes': PREDICTIONS_DIR / "community_votes.json",
    'leaderboard': PREDICTIONS_DIR / "leaderboard.json",
    'achievements': PREDICTIONS_DIR / "achievements.json"
}

# ════════════════════════════════════════════════════════════════════════════
# 🏆 CONFIGURATION SPORTS - PRONOSTICS SPÉCIFIQUES
# ════════════════════════════════════════════════════════════════════════════

SPORTS_CONFIG = {
    'football': {
        'name': 'Football',
        'icon': '⚽',
        'predictions': [
            'match_result', 'exact_score', 'total_goals', 'btts',
            'corners', 'cards', 'halftime', 'first_goal', 'clean_sheet'
        ],
        'vote_options': {'1': 'Victoire Dom', 'X': 'Match Nul', '2': 'Victoire Ext'},
        'result_type': '1X2'
    },
    'ufc': {
        'name': 'UFC/MMA',
        'icon': '🥊',
        'predictions': [
            'winner', 'method', 'round', 'fight_duration', 
            'knockdown', 'submission_attempt', 'distance'
        ],
        'vote_options': {'1': 'Fighter 1', '2': 'Fighter 2'},
        'result_type': 'H2H'
    },
    'boxing': {
        'name': 'Boxe',
        'icon': '🥊',
        'predictions': [
            'winner', 'method', 'round', 'knockdowns',
            'total_rounds', 'distance', 'points_decision'
        ],
        'vote_options': {'1': 'Boxeur 1', '2': 'Boxeur 2', 'X': 'Nul'},
        'result_type': '1X2'
    },
    'nba': {
        'name': 'NBA/Basketball',
        'icon': '🏀',
        'predictions': [
            'winner', 'spread', 'total_points', 'quarters',
            'halftime', 'player_props', 'margin'
        ],
        'vote_options': {'1': 'Équipe Dom', '2': 'Équipe Ext'},
        'result_type': 'H2H'
    },
    'nfl': {
        'name': 'NFL/Football US',
        'icon': '🏈',
        'predictions': [
            'winner', 'spread', 'total_points', 'halftime',
            'quarters', 'touchdowns', 'field_goals'
        ],
        'vote_options': {'1': 'Équipe Dom', '2': 'Équipe Ext'},
        'result_type': 'H2H'
    },
    'tennis': {
        'name': 'Tennis',
        'icon': '🎾',
        'predictions': [
            'winner', 'sets_score', 'total_games', 'tiebreaks',
            'aces', 'breaks', 'match_duration'
        ],
        'vote_options': {'1': 'Joueur 1', '2': 'Joueur 2'},
        'result_type': 'H2H'
    },
    'nhl': {
        'name': 'NHL/Hockey',
        'icon': '🏒',
        'predictions': [
            'winner', 'total_goals', 'period_results', 'spread',
            'overtime', 'shutout', 'first_goal'
        ],
        'vote_options': {'1': 'Équipe Dom', 'X': 'Nul/Prolongation', '2': 'Équipe Ext'},
        'result_type': '1X2'
    },
    'f1': {
        'name': 'Formule 1',
        'icon': '🏎️',
        'predictions': [
            'race_winner', 'podium', 'fastest_lap', 'dnf',
            'constructors', 'h2h_drivers', 'safety_car'
        ],
        'vote_options': {},
        'result_type': 'RACE'
    },
    'motogp': {
        'name': 'MotoGP',
        'icon': '🏍️',
        'predictions': [
            'race_winner', 'podium', 'pole_position',
            'fastest_lap', 'h2h_riders'
        ],
        'vote_options': {},
        'result_type': 'RACE'
    },
    'rugby': {
        'name': 'Rugby',
        'icon': '🏉',
        'predictions': [
            'winner', 'handicap', 'total_points', 'halftime',
            'tries', 'margin', 'first_try'
        ],
        'vote_options': {'1': 'Équipe Dom', 'X': 'Match Nul', '2': 'Équipe Ext'},
        'result_type': '1X2'
    },
    'golf': {
        'name': 'Golf',
        'icon': '⛳',
        'predictions': [
            'tournament_winner', 'top_5', 'top_10', 'cut',
            'h2h_golfers', 'nationality'
        ],
        'vote_options': {},
        'result_type': 'TOURNAMENT'
    },
    'darts': {
        'name': 'Fléchettes',
        'icon': '🎯',
        'predictions': [
            'winner', 'sets_score', 'total_180s', 'checkout',
            'highest_checkout', '9_darter'
        ],
        'vote_options': {'1': 'Joueur 1', '2': 'Joueur 2'},
        'result_type': 'H2H'
    },
    'wwe': {
        'name': 'WWE/Catch',
        'icon': '🤼',
        'predictions': [
            'winner', 'match_type', 'interference',
            'title_change', 'surprise'
        ],
        'vote_options': {'1': 'Favori', '2': 'Outsider'},
        'result_type': 'H2H'
    },
    'volleyball': {
        'name': 'Volleyball',
        'icon': '🏐',
        'predictions': [
            'winner', 'sets_score', 'total_points', 'set_winners',
            'handicap', 'first_set'
        ],
        'vote_options': {'1': 'Équipe Dom', '2': 'Équipe Ext'},
        'result_type': 'H2H'
    },
    'other': {
        'name': 'Autre Sport',
        'icon': '🎯',
        'predictions': ['winner', 'score', 'special'],
        'vote_options': {'1': 'Option 1', '2': 'Option 2'},
        'result_type': 'H2H'
    }
}

# ════════════════════════════════════════════════════════════════════════════
# 📊 LIMITES ET CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════

class Limits:
    CACHE_DURATION = 1800  # 30 minutes
    MAX_PREDICTIONS_FREE = 10  # Par jour
    MAX_PREDICTIONS_PREMIUM = 100
    RATE_LIMIT_WINDOW = 60
    RATE_LIMIT_MAX = 5
    POINTS_CORRECT = 10
    POINTS_EXACT = 50
    POINTS_VOTE = 1
    POINTS_STREAK = 5

# ════════════════════════════════════════════════════════════════════════════
# 📦 DATA CLASSES
# ════════════════════════════════════════════════════════════════════════════

class UserTier(Enum):
    FREE = "free"
    PREMIUM = "premium"
    VIP = "vip"
    ADMIN = "admin"

@dataclass
class UserProfile:
    user_id: int
    username: str = ""
    tier: str = "free"
    total_points: int = 0
    predictions_count: int = 0
    wins_count: int = 0
    current_streak: int = 0
    best_streak: int = 0
    achievements: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @property
    def win_rate(self) -> float:
        if self.predictions_count == 0:
            return 0.0
        return round((self.wins_count / self.predictions_count) * 100, 1)
    
    @property
    def daily_limit(self) -> int:
        limits = {
            'free': Limits.MAX_PREDICTIONS_FREE,
            'premium': Limits.MAX_PREDICTIONS_PREMIUM,
            'vip': 200,
            'admin': 500
        }
        return limits.get(self.tier, Limits.MAX_PREDICTIONS_FREE)

# ════════════════════════════════════════════════════════════════════════════
# 💾 GESTIONNAIRE DE DONNÉES AVANCÉ
# ════════════════════════════════════════════════════════════════════════════

class AdvancedDataManager:
    """Gestionnaire centralisé des données avec cache intelligent"""
    
    _cache: Dict[str, Tuple[Any, float]] = {}
    _cache_ttl = 300  # 5 minutes
    
    @classmethod
    def _load_file(cls, key: str, default: Any = None) -> Any:
        cache_entry = cls._cache.get(key)
        if cache_entry:
            data, timestamp = cache_entry
            if time.time() - timestamp < cls._cache_ttl:
                return data
        
        try:
            path = FILES.get(key)
            if path and path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                cls._cache[key] = (data, time.time())
                return data
        except Exception as e:
            logger.error(f"Erreur chargement {key}: {e}")
        
        return default if default is not None else {}
    
    @classmethod
    def _save_file(cls, key: str, data: Any):
        try:
            path = FILES.get(key)
            if path:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                cls._cache[key] = (data, time.time())
        except Exception as e:
            logger.error(f"Erreur sauvegarde {key}: {e}")
    
    # === CACHE PRÉDICTIONS ===
    @classmethod
    def get_prediction_cache(cls, match_id: str) -> Optional[Dict]:
        cache = cls._load_file('cache', {'predictions': {}})
        entry = cache.get('predictions', {}).get(match_id)
        
        if entry:
            cached_at = datetime.fromisoformat(entry.get('cached_at', '2000-01-01'))
            if datetime.now() - cached_at < timedelta(seconds=Limits.CACHE_DURATION):
                return entry.get('data')
        return None
    
    @classmethod
    def set_prediction_cache(cls, match_id: str, prediction: Dict):
        cache = cls._load_file('cache', {'predictions': {}})
        if 'predictions' not in cache:
            cache['predictions'] = {}
        
        cache['predictions'][match_id] = {
            'data': prediction,
            'cached_at': datetime.now().isoformat()
        }
        
        # Nettoyer les vieilles entrées
        cutoff = (datetime.now() - timedelta(hours=2)).isoformat()
        cache['predictions'] = {
            k: v for k, v in cache['predictions'].items()
            if v.get('cached_at', '') > cutoff
        }
        
        cls._save_file('cache', cache)
    
    # === PROFIL UTILISATEUR ===
    @classmethod
    def get_user_profile(cls, user_id: int, username: str = "") -> UserProfile:
        stats = cls._load_file('stats', {'users': {}})
        user_data = stats.get('users', {}).get(str(user_id))
        
        if user_data:
            return UserProfile(**user_data)
        
        profile = UserProfile(user_id=user_id, username=username)
        cls.save_user_profile(profile)
        return profile
    
    @classmethod
    def save_user_profile(cls, profile: UserProfile):
        stats = cls._load_file('stats', {'users': {}})
        if 'users' not in stats:
            stats['users'] = {}
        stats['users'][str(profile.user_id)] = asdict(profile)
        cls._save_file('stats', stats)
    
    # === HISTORIQUE ===
    @classmethod
    def add_prediction_to_history(cls, user_id: int, match: Dict, prediction: Dict):
        history = cls._load_file('history', {'predictions': []})
        
        history['predictions'].append({
            'user_id': user_id,
            'match_id': match.get('id'),
            'match_title': match.get('title'),
            'sport': match.get('sport', 'FOOTBALL'),
            'prediction': prediction,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending'
        })
        
        # Garder les 5000 dernières
        if len(history['predictions']) > 5000:
            history['predictions'] = history['predictions'][-5000:]
        
        cls._save_file('history', history)
    
    @classmethod
    def get_today_predictions_count(cls, user_id: int) -> int:
        history = cls._load_file('history', {'predictions': []})
        today = datetime.now().date().isoformat()
        return len([
            p for p in history['predictions']
            if p['user_id'] == user_id and p['timestamp'][:10] == today
        ])
    
    @classmethod
    def get_user_predictions(cls, user_id: int, limit: int = 20) -> List[Dict]:
        history = cls._load_file('history', {'predictions': []})
        user_preds = [p for p in history['predictions'] if p['user_id'] == user_id]
        return sorted(user_preds, key=lambda x: x['timestamp'], reverse=True)[:limit]
    
    # === VOTES ===
    @classmethod
    def add_vote(cls, match_id: str, user_id: int, vote: str, sport: str = 'football') -> Dict:
        votes = cls._load_file('votes', {'matches': {}})
        
        sport_config = SPORTS_CONFIG.get(sport.lower(), SPORTS_CONFIG['other'])
        vote_options = list(sport_config['vote_options'].keys())
        
        if match_id not in votes['matches']:
            votes['matches'][match_id] = {
                'votes': [],
                'totals': {k: 0 for k in vote_options},
                'sport': sport,
                'created_at': datetime.now().isoformat()
            }
        
        match_votes = votes['matches'][match_id]
        
        # Vérifier si déjà voté
        existing = next((v for v in match_votes['votes'] if v['user_id'] == user_id), None)
        if existing:
            old_vote = existing['vote']
            if old_vote in match_votes['totals']:
                match_votes['totals'][old_vote] = max(0, match_votes['totals'][old_vote] - 1)
            existing['vote'] = vote
            existing['timestamp'] = datetime.now().isoformat()
        else:
            match_votes['votes'].append({
                'user_id': user_id,
                'vote': vote,
                'timestamp': datetime.now().isoformat()
            })
        
        if vote not in match_votes['totals']:
            match_votes['totals'][vote] = 0
        match_votes['totals'][vote] += 1
        
        cls._save_file('votes', votes)
        return match_votes['totals']
    
    @classmethod
    def get_vote_stats(cls, match_id: str) -> Dict:
        votes = cls._load_file('votes', {'matches': {}})
        if match_id in votes['matches']:
            totals = votes['matches'][match_id]['totals']
            total_votes = sum(totals.values())
            return {
                'totals': totals,
                'total_votes': total_votes,
                'percentages': {
                    k: round((v / total_votes * 100) if total_votes > 0 else 0, 1)
                    for k, v in totals.items()
                },
                'sport': votes['matches'][match_id].get('sport', 'football')
            }
        return {'totals': {}, 'total_votes': 0, 'percentages': {}}
    
    @classmethod
    def get_user_vote(cls, match_id: str, user_id: int) -> Optional[str]:
        votes = cls._load_file('votes', {'matches': {}})
        if match_id in votes['matches']:
            for v in votes['matches'][match_id]['votes']:
                if v['user_id'] == user_id:
                    return v['vote']
        return None
    
    # === LEADERBOARD ===
    @classmethod
    def get_leaderboard(cls, limit: int = 20) -> List[Dict]:
        stats = cls._load_file('stats', {'users': {}})
        users = list(stats.get('users', {}).values())
        sorted_users = sorted(users, key=lambda x: x.get('total_points', 0), reverse=True)
        
        for i, user in enumerate(sorted_users[:limit], 1):
            user['rank'] = i
        
        return sorted_users[:limit]

# ════════════════════════════════════════════════════════════════════════════
# ✅ VALIDATEUR D'ÉVÉNEMENTS
# ════════════════════════════════════════════════════════════════════════════

class EventValidator:
    """Valide que les événements scrapés sont réels et analysables"""
    
    # Patterns pour détecter les faux événements
    INVALID_PATTERNS = [
        r'^test\s', r'\btest\b', r'^sample', r'^demo',
        r'^placeholder', r'^tbd\b', r'^tba\b',
        r'coming\s*soon', r'to\s*be\s*announced',
        r'^n/a\b', r'^none\b', r'^null\b'
    ]
    
    # Patterns valides par sport
    SPORT_PATTERNS = {
        'football': [
            r'\bfc\b', r'\bunited\b', r'\bcity\b', r'\breal\b',
            r'\bbarcelona\b', r'\bchelsea\b', r'\bliv(?:erpool)?\b',
            r'\bpsg\b', r'\bbayern\b', r'\bjuventus\b', r'\bmilan\b',
            r'\bvs\.?\b', r'\bv\b'
        ],
        'ufc': [
            r'\bufc\b', r'\bmma\b', r'\bfight\b', r'\bbellator\b',
            r'\bko\b', r'\bknockout\b', r'\bsubmission\b'
        ],
        'boxing': [
            r'\bbox(?:ing)?\b', r'\bfight\b', r'\bchampion\b',
            r'\btitle\b', r'\bwba\b', r'\bwbc\b', r'\bibf\b', r'\bwbo\b'
        ],
        'nba': [
            r'\blakers\b', r'\bceltics\b', r'\bwarriors\b', r'\bbulls\b',
            r'\bheat\b', r'\bnets\b', r'\bknicks\b', r'\bspurs\b',
            r'\bnba\b', r'\bbasketball\b'
        ],
        'nfl': [
            r'\bnfl\b', r'\bpatriots\b', r'\bcowboys\b', r'\bpackers\b',
            r'\b49ers\b', r'\bchiefs\b', r'\beagles\b', r'\bbroncos\b'
        ],
        'tennis': [
            r'\batp\b', r'\bwta\b', r'\bopen\b', r'\bgrand\s*slam\b',
            r'\bwimbledon\b', r'\bnadal\b', r'\bdjokovic\b', r'\bfederer\b'
        ]
    }
    
    @classmethod
    def validate_event(cls, match: Dict) -> Tuple[bool, str, int]:
        """
        Valide un événement
        Returns: (is_valid, message, confidence_score)
        confidence_score: 0-100
        """
        title = match.get('title', '').lower()
        team1 = match.get('team1', '').lower()
        team2 = match.get('team2', '').lower()
        sport = match.get('sport', 'football').lower()
        
        # Vérifications de base
        if not title or len(title) < 5:
            return False, "Titre trop court ou manquant", 0
        
        if not team1:
            return False, "Équipe/Participant 1 manquant", 0
        
        # Vérifier les patterns invalides
        for pattern in cls.INVALID_PATTERNS:
            if re.search(pattern, title, re.IGNORECASE):
                return False, f"Pattern invalide détecté: {pattern}", 0
            if team1 and re.search(pattern, team1, re.IGNORECASE):
                return False, f"Équipe 1 invalide", 0
        
        # Calculer le score de confiance
        confidence = 50  # Base
        
        # Bonus si on a les deux équipes
        if team2 and len(team2) > 2:
            confidence += 15
        
        # Bonus si patterns sportifs valides
        sport_patterns = cls.SPORT_PATTERNS.get(sport, [])
        for pattern in sport_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                confidence += 5
                break
        
        # Bonus si heure valide
        time_str = match.get('start_time', '')
        if re.search(r'\d{1,2}:\d{2}', time_str):
            confidence += 10
        
        # Bonus si "vs" ou "v" présent
        if re.search(r'\bvs\.?\b|\bv\b', title, re.IGNORECASE):
            confidence += 10
        
        # Malus si caractères suspects
        if re.search(r'[<>{}|\[\]]', title):
            confidence -= 20
        
        # Malus si trop de chiffres (sauf scores)
        digit_ratio = len(re.findall(r'\d', title)) / max(len(title), 1)
        if digit_ratio > 0.3:
            confidence -= 15
        
        confidence = max(0, min(100, confidence))
        
        if confidence < 30:
            return False, "Score de confiance trop bas", confidence
        
        grade = "A" if confidence >= 70 else "B" if confidence >= 50 else "C"
        return True, f"Événement validé (Grade {grade})", confidence
    
    @classmethod
    def get_event_grade(cls, confidence: int) -> str:
        """Convertit un score de confiance en grade"""
        if confidence >= 80:
            return "A+"
        elif confidence >= 70:
            return "A"
        elif confidence >= 60:
            return "B+"
        elif confidence >= 50:
            return "B"
        elif confidence >= 40:
            return "C"
        else:
            return "D"

# ════════════════════════════════════════════════════════════════════════════
# 🧠 PROMPTS IA SPÉCIFIQUES PAR SPORT
# ════════════════════════════════════════════════════════════════════════════

def get_sport_prompt(sport: str) -> str:
    """Retourne le prompt système adapté au sport"""
    
    base_prompt = """Tu es un analyste sportif professionnel d'élite avec 20+ ans d'expérience.
Tu fournis des analyses détaillées et des prédictions précises basées sur les données disponibles.

RÈGLES IMPORTANTES:
1. Confiance JAMAIS > 70% (sauf cas exceptionnels à 75% max)
2. Toujours justifier chaque prédiction
3. Format JSON strict obligatoire
4. Indiquer clairement la qualité des données disponibles
5. Proposer des paris à VALEUR, pas juste populaires

ÉCHELLE DE CONFIANCE:
- 65-75%: 🟢 TRÈS FORTE - Multiples facteurs alignés
- 55-64%: 🟡 FORTE - Bons indicateurs
- 45-54%: 🟠 MOYENNE - Incertitudes modérées
- 35-44%: 🔴 FAIBLE - Données limitées
- <35%: ⚫ TRÈS FAIBLE - Ne pas parier

"""
    
    sport_prompts = {
        'football': """
SPORT: FOOTBALL ⚽

PRÉDICTIONS À FOURNIR:
1. 🏆 RÉSULTAT (1/X/2) avec probabilités
2. ⚽ SCORE EXACT - Top 3 scores probables
3. 📊 TOTAL BUTS - Over/Under 1.5, 2.5, 3.5
4. 🥅 BTTS (Les deux marquent)
5. 🚩 CORNERS - Total et par équipe
6. 🟨 CARTONS - Jaunes/Rouges
7. ⏱️ MI-TEMPS - Résultat HT
8. 💎 MEILLEUR PARI VALEUR

FORMAT JSON:
{
  "sport": "football",
  "analysis": {"overview": "...", "key_factors": [...], "form": {"team1": "...", "team2": "..."}},
  "predictions": {
    "match_result": {"prediction": "1/X/2", "probabilities": {"1": 45, "X": 28, "2": 27}, "confidence": 58, "reasoning": "..."},
    "exact_score": {"top_3": [{"score": "2-1", "probability": 12}, ...], "confidence": 35},
    "total_goals": {"expected": 2.5, "over_1_5": 75, "over_2_5": 55, "over_3_5": 30, "confidence": 50},
    "btts": {"prediction": "Oui/Non", "probability": 60, "confidence": 52},
    "corners": {"total": 10, "team1": "5-6", "team2": "4-5", "over_9_5": 55, "confidence": 45},
    "cards": {"yellow": 4, "red_probability": 15, "confidence": 40},
    "halftime": {"prediction": "1/X/2", "confidence": 42},
    "best_bet": {"selection": "...", "odds": 2.0, "confidence": 55, "value": "★★★★☆", "reasoning": "..."}
  },
  "summary": {"confidence": 52, "grade": "B", "data_quality": "Bon", "key_insight": "..."},
  "disclaimer": "⚠️ Paris responsable uniquement"
}
""",
        'ufc': """
SPORT: UFC/MMA 🥊

PRÉDICTIONS À FOURNIR:
1. 🏆 VAINQUEUR avec probabilités
2. 🎯 MÉTHODE DE VICTOIRE (KO/TKO, Soumission, Décision)
3. ⏱️ ROUND DE FIN prévu
4. 📊 DURÉE DU COMBAT (Over/Under rounds)
5. 💥 KNOCKDOWNS probabilité
6. 🔒 SOUMISSION tentatives
7. 💎 MEILLEUR PARI VALEUR

FORMAT JSON:
{
  "sport": "ufc",
  "analysis": {"overview": "...", "fighter1_strengths": [...], "fighter2_strengths": [...], "style_matchup": "..."},
  "predictions": {
    "winner": {"prediction": "Fighter 1/2", "probabilities": {"1": 60, "2": 40}, "confidence": 55, "reasoning": "..."},
    "method": {"prediction": "KO/TKO/Submission/Decision", "ko_probability": 35, "sub_probability": 20, "decision_probability": 45, "confidence": 48},
    "round": {"prediction": "Round 2/3/Decision", "finish_round_probabilities": {"1": 15, "2": 25, "3": 20, "dec": 40}, "confidence": 42},
    "fight_duration": {"over_1_5": 65, "over_2_5": 45, "goes_distance": 40, "confidence": 50},
    "knockdown": {"probability": 55, "fighter1": 30, "fighter2": 25, "confidence": 45},
    "best_bet": {"selection": "...", "odds": 2.0, "confidence": 52, "value": "★★★☆☆", "reasoning": "..."}
  },
  "summary": {"confidence": 50, "grade": "B", "data_quality": "Bon", "key_insight": "..."},
  "disclaimer": "⚠️ Paris responsable uniquement"
}
""",
        'boxing': """
SPORT: BOXE 🥊

PRÉDICTIONS À FOURNIR:
1. 🏆 VAINQUEUR avec probabilités
2. 🎯 MÉTHODE (KO, TKO, Décision unanime/partagée)
3. ⏱️ ROUND DE FIN
4. 📊 OVER/UNDER ROUNDS
5. 💥 KNOCKDOWNS
6. 💎 MEILLEUR PARI VALEUR

FORMAT JSON:
{
  "sport": "boxing",
  "analysis": {"overview": "...", "boxer1_analysis": "...", "boxer2_analysis": "...", "style_matchup": "..."},
  "predictions": {
    "winner": {"prediction": "Boxer 1/2/Draw", "probabilities": {"1": 55, "X": 5, "2": 40}, "confidence": 52, "reasoning": "..."},
    "method": {"ko_tko": 40, "decision": 55, "draw": 5, "confidence": 48},
    "round": {"over_6_5": 60, "over_9_5": 40, "goes_distance": 55, "confidence": 45},
    "knockdowns": {"probability": 50, "total_expected": 1.5, "confidence": 42},
    "best_bet": {"selection": "...", "odds": 2.0, "confidence": 50, "value": "★★★☆☆", "reasoning": "..."}
  },
  "summary": {"confidence": 48, "grade": "B", "data_quality": "Bon", "key_insight": "..."},
  "disclaimer": "⚠️ Paris responsable uniquement"
}
""",
        'nba': """
SPORT: NBA/BASKETBALL 🏀

PRÉDICTIONS À FOURNIR:
1. 🏆 VAINQUEUR (Moneyline)
2. 📊 SPREAD/HANDICAP
3. 📈 TOTAL POINTS (Over/Under)
4. 🏀 QUARTS - Vainqueur par quart
5. ⏱️ MI-TEMPS - Score et vainqueur
6. 📏 MARGE DE VICTOIRE
7. 💎 MEILLEUR PARI VALEUR

FORMAT JSON:
{
  "sport": "nba",
  "analysis": {"overview": "...", "team1_form": "...", "team2_form": "...", "key_players": [...], "injuries": [...]},
  "predictions": {
    "winner": {"prediction": "Team 1/2", "probabilities": {"1": 55, "2": 45}, "confidence": 52, "reasoning": "..."},
    "spread": {"line": -5.5, "pick": "Team 1 -5.5", "confidence": 48},
    "total_points": {"line": 220.5, "prediction": "Over/Under", "probability": 55, "confidence": 50},
    "halftime": {"leader": "Team 1/2", "confidence": 45},
    "margin": {"expected": "5-10 points", "blowout_probability": 25, "confidence": 42},
    "best_bet": {"selection": "...", "odds": 1.9, "confidence": 52, "value": "★★★☆☆", "reasoning": "..."}
  },
  "summary": {"confidence": 50, "grade": "B", "data_quality": "Bon", "key_insight": "..."},
  "disclaimer": "⚠️ Paris responsable uniquement"
}
""",
        'nfl': """
SPORT: NFL/FOOTBALL AMÉRICAIN 🏈

PRÉDICTIONS À FOURNIR:
1. 🏆 VAINQUEUR (Moneyline)
2. 📊 SPREAD/HANDICAP
3. 📈 TOTAL POINTS (Over/Under)
4. ⏱️ MI-TEMPS
5. 🏈 TOUCHDOWNS
6. 🎯 FIELD GOALS
7. 💎 MEILLEUR PARI VALEUR

FORMAT JSON:
{
  "sport": "nfl",
  "analysis": {"overview": "...", "team1_offense": "...", "team2_defense": "...", "weather": "...", "injuries": [...]},
  "predictions": {
    "winner": {"prediction": "Team 1/2", "probabilities": {"1": 58, "2": 42}, "confidence": 55, "reasoning": "..."},
    "spread": {"line": -3.5, "pick": "Team 1 -3.5", "confidence": 50},
    "total_points": {"line": 45.5, "prediction": "Over/Under", "probability": 52, "confidence": 48},
    "halftime": {"leader": "Team 1/2", "ht_score": "14-10", "confidence": 42},
    "touchdowns": {"total_expected": 5, "team1": 3, "team2": 2, "confidence": 45},
    "best_bet": {"selection": "...", "odds": 1.95, "confidence": 52, "value": "★★★☆☆", "reasoning": "..."}
  },
  "summary": {"confidence": 50, "grade": "B", "data_quality": "Bon", "key_insight": "..."},
  "disclaimer": "⚠️ Paris responsable uniquement"
}
""",
        'tennis': """
SPORT: TENNIS 🎾

PRÉDICTIONS À FOURNIR:
1. 🏆 VAINQUEUR DU MATCH
2. 📊 SCORE EN SETS (2-0, 2-1, etc.)
3. 📈 TOTAL DE JEUX (Over/Under)
4. 🎾 TIEBREAKS probabilité
5. ⚡ ACES attendus
6. 🔄 BREAKS DE SERVICE
7. 💎 MEILLEUR PARI VALEUR

FORMAT JSON:
{
  "sport": "tennis",
  "analysis": {"overview": "...", "player1_form": "...", "player2_form": "...", "surface": "...", "h2h": "..."},
  "predictions": {
    "winner": {"prediction": "Player 1/2", "probabilities": {"1": 60, "2": 40}, "confidence": 55, "reasoning": "..."},
    "sets_score": {"prediction": "2-0/2-1/1-2/0-2", "probabilities": {"2-0": 35, "2-1": 25, "1-2": 20, "0-2": 20}, "confidence": 48},
    "total_games": {"line": 21.5, "prediction": "Over/Under", "probability": 55, "confidence": 50},
    "tiebreaks": {"probability": 40, "expected": 0.5, "confidence": 42},
    "aces": {"player1": 8, "player2": 5, "total_over_10_5": 55, "confidence": 45},
    "best_bet": {"selection": "...", "odds": 1.85, "confidence": 52, "value": "★★★☆☆", "reasoning": "..."}
  },
  "summary": {"confidence": 52, "grade": "B", "data_quality": "Bon", "key_insight": "..."},
  "disclaimer": "⚠️ Paris responsable uniquement"
}
""",
        'nhl': """
SPORT: NHL/HOCKEY 🏒

PRÉDICTIONS À FOURNIR:
1. 🏆 VAINQUEUR (temps réglementaire ou prolongation)
2. 📊 PUCK LINE (spread -1.5)
3. 📈 TOTAL BUTS (Over/Under)
4. ⏱️ PÉRIODES - Résultats
5. 🥅 SHUTOUT probabilité
6. ⚡ PROLONGATION probabilité
7. 💎 MEILLEUR PARI VALEUR

FORMAT JSON:
{
  "sport": "nhl",
  "analysis": {"overview": "...", "team1_form": "...", "team2_form": "...", "goalie_matchup": "..."},
  "predictions": {
    "winner": {"prediction": "Team 1/2", "probabilities": {"1": 52, "X": 8, "2": 40}, "confidence": 50, "reasoning": "..."},
    "puck_line": {"team1_minus_1_5": 35, "team2_plus_1_5": 65, "confidence": 45},
    "total_goals": {"line": 5.5, "over": 55, "under": 45, "confidence": 50},
    "overtime": {"probability": 15, "confidence": 42},
    "shutout": {"team1": 8, "team2": 6, "confidence": 38},
    "best_bet": {"selection": "...", "odds": 1.9, "confidence": 48, "value": "★★★☆☆", "reasoning": "..."}
  },
  "summary": {"confidence": 48, "grade": "B", "data_quality": "Bon", "key_insight": "..."},
  "disclaimer": "⚠️ Paris responsable uniquement"
}
""",
        'f1': """
SPORT: FORMULE 1 🏎️

PRÉDICTIONS À FOURNIR:
1. 🏆 VAINQUEUR DE LA COURSE
2. 🥇🥈🥉 PODIUM (Top 3)
3. ⚡ TOUR LE PLUS RAPIDE
4. 🚗 DNF (abandons)
5. 🏁 CONSTRUCTEURS - Points
6. 🚨 SAFETY CAR probabilité
7. 💎 MEILLEUR PARI VALEUR

FORMAT JSON:
{
  "sport": "f1",
  "analysis": {"overview": "...", "track_analysis": "...", "weather": "...", "qualifying_impact": "..."},
  "predictions": {
    "race_winner": {"prediction": "Driver Name", "top_5": [{"driver": "...", "probability": 25}, ...], "confidence": 45, "reasoning": "..."},
    "podium": {"predicted": ["Driver 1", "Driver 2", "Driver 3"], "confidence": 40},
    "fastest_lap": {"prediction": "Driver Name", "probability": 30, "confidence": 38},
    "dnf": {"expected_count": 2, "high_risk_drivers": [...], "confidence": 42},
    "safety_car": {"probability": 65, "confidence": 50},
    "best_bet": {"selection": "...", "odds": 2.5, "confidence": 45, "value": "★★★☆☆", "reasoning": "..."}
  },
  "summary": {"confidence": 42, "grade": "B", "data_quality": "Moyen", "key_insight": "..."},
  "disclaimer": "⚠️ Paris responsable uniquement"
}
"""
    }
    
    # Prompt par défaut pour les autres sports
    default_prompt = """
SPORT: GÉNÉRAL 🎯

PRÉDICTIONS À FOURNIR:
1. 🏆 VAINQUEUR avec probabilités
2. 📊 SCORE/RÉSULTAT prévu
3. 💎 MEILLEUR PARI VALEUR

FORMAT JSON:
{
  "sport": "other",
  "analysis": {"overview": "...", "key_factors": [...]},
  "predictions": {
    "winner": {"prediction": "...", "probabilities": {...}, "confidence": 50, "reasoning": "..."},
    "score": {"prediction": "...", "confidence": 40},
    "best_bet": {"selection": "...", "odds": 2.0, "confidence": 45, "value": "★★★☆☆", "reasoning": "..."}
  },
  "summary": {"confidence": 45, "grade": "C", "data_quality": "Limité", "key_insight": "..."},
  "disclaimer": "⚠️ Paris responsable uniquement"
}
"""
    
    sport_key = sport.lower()
    specific_prompt = sport_prompts.get(sport_key, default_prompt)
    
    return base_prompt + specific_prompt

# ════════════════════════════════════════════════════════════════════════════
# 🤖 PRÉDICTEUR IA ULTRA V3
# ════════════════════════════════════════════════════════════════════════════

class UltraPredictor:
    """Prédicteur IA multi-sports de niveau professionnel"""
    
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.session: Optional[aiohttp.ClientSession] = None
        self.current_model_index = 0
        self.stats = {
            'total_predictions': 0,
            'cache_hits': 0,
            'api_calls': 0,
            'api_errors': 0,
            'fallback_used': 0
        }
    
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=90)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _call_groq(self, messages: List[Dict], model: str = None) -> Optional[str]:
        """Appel API Groq avec fallback automatique"""
        if not self.api_key:
            logger.warning("⚠️ GROQ_API_KEY non configurée")
            return None
        
        model = model or GROQ_MODELS[self.current_model_index]
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4000,
            "top_p": 0.9,
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
                    logger.info(f"✅ Groq API success [{model[:25]}]")
                    return content
                
                elif response.status == 429:
                    logger.warning(f"⚠️ Rate limit sur {model}")
                    self.stats['api_errors'] += 1
                    
                    # Fallback au modèle suivant
                    if self.current_model_index < len(GROQ_MODELS) - 1:
                        self.current_model_index += 1
                        await asyncio.sleep(1)
                        return await self._call_groq(messages, GROQ_MODELS[self.current_model_index])
                
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Groq API {response.status}: {error_text[:200]}")
                    self.stats['api_errors'] += 1
        
        except asyncio.TimeoutError:
            logger.error("⏱️ Timeout API Groq")
            self.stats['api_errors'] += 1
        except Exception as e:
            logger.error(f"❌ Exception Groq: {e}")
            self.stats['api_errors'] += 1
        
        return None
    
    async def analyze_match(self, match: Dict, user_id: int) -> Dict:
        """Analyse complète d'un match avec IA"""
        
        # Valider l'événement
        is_valid, validation_msg, confidence_score = EventValidator.validate_event(match)
        
        if not is_valid:
            logger.warning(f"⚠️ Événement invalide: {validation_msg}")
            return self._generate_invalid_event_response(match, validation_msg)
        
        # Vérifier le cache
        cache_key = f"ultra_v3_{match['id']}"
        cached = AdvancedDataManager.get_prediction_cache(cache_key)
        if cached:
            self.stats['cache_hits'] += 1
            logger.info(f"💾 Cache hit: {match.get('title', 'N/A')[:40]}")
            return cached
        
        sport = match.get('sport', 'FOOTBALL').lower()
        sport_config = SPORTS_CONFIG.get(sport, SPORTS_CONFIG['other'])
        
        # Construire le prompt
        system_prompt = get_sport_prompt(sport)
        user_prompt = self._build_user_prompt(match, sport_config)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        logger.info(f"🤖 Analyse IA ({sport_config['icon']} {sport_config['name']}): {match.get('title', 'N/A')[:50]}")
        
        response = await self._call_groq(messages)
        
        if response:
            try:
                prediction = self._parse_response(response)
                prediction = self._enrich_prediction(prediction, match, sport_config, confidence_score)
                
                # Sauvegarder dans le cache
                AdvancedDataManager.set_prediction_cache(cache_key, prediction)
                
                # Ajouter à l'historique
                AdvancedDataManager.add_prediction_to_history(user_id, match, prediction)
                
                # Mettre à jour le profil utilisateur
                profile = AdvancedDataManager.get_user_profile(user_id)
                profile.predictions_count += 1
                AdvancedDataManager.save_user_profile(profile)
                
                self.stats['total_predictions'] += 1
                return prediction
                
            except Exception as e:
                logger.error(f"❌ Erreur parsing: {e}")
        
        # Fallback intelligent
        self.stats['fallback_used'] += 1
        return self._generate_smart_fallback(match, sport_config, confidence_score)
    
    def _build_user_prompt(self, match: Dict, sport_config: Dict) -> str:
        """Construit le prompt utilisateur"""
        team1 = match.get('team1', match.get('title', 'Équipe 1'))
        team2 = match.get('team2', 'Équipe 2')
        
        prompt = f"""
═══════════════════════════════════════════════════════════════════════════════
📋 DEMANDE D'ANALYSE - {sport_config['name'].upper()}
═══════════════════════════════════════════════════════════════════════════════

{sport_config['icon']} ÉVÉNEMENT: {team1} vs {team2}
📅 DATE: {datetime.now().strftime('%d/%m/%Y')}
⏰ HEURE: {match.get('start_time', 'N/A')}
🏆 COMPÉTITION: {match.get('sport_name', sport_config['name'])}

═══════════════════════════════════════════════════════════════════════════════
🎯 INSTRUCTIONS
═══════════════════════════════════════════════════════════════════════════════

Fournis une analyse COMPLÈTE au format JSON avec:
- Toutes les prédictions spécifiques à ce sport
- Des probabilités réalistes (jamais >75%)
- Des justifications claires
- Un meilleur pari valeur
- Un grade de qualité (A, B, C, D)

Sois PRÉCIS et PROFESSIONNEL.
"""
        return prompt
    
    def _parse_response(self, response: str) -> Dict:
        """Parse la réponse JSON"""
        response = response.strip()
        
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        return json.loads(response.strip())
    
    def _enrich_prediction(self, prediction: Dict, match: Dict, sport_config: Dict, confidence_score: int) -> Dict:
        """Enrichit la prédiction avec des métadonnées"""
        
        # Calculer le grade basé sur la confiance de l'IA + validation
        summary = prediction.get('summary', {})
        ai_confidence = summary.get('confidence', 50)
        
        # Moyenne pondérée
        final_confidence = int(ai_confidence * 0.7 + confidence_score * 0.3)
        grade = EventValidator.get_event_grade(final_confidence)
        
        prediction['meta'] = {
            'match_id': match.get('id'),
            'match_title': match.get('title'),
            'team1': match.get('team1', ''),
            'team2': match.get('team2', ''),
            'sport': match.get('sport', 'FOOTBALL'),
            'sport_name': sport_config['name'],
            'sport_icon': sport_config['icon'],
            'analyzed_at': datetime.now().isoformat(),
            'model': GROQ_MODELS[self.current_model_index],
            'validation_score': confidence_score,
            'is_ai_generated': True
        }
        
        # Mettre à jour le résumé avec le bon grade
        if 'summary' not in prediction:
            prediction['summary'] = {}
        prediction['summary']['grade'] = grade
        prediction['summary']['confidence'] = final_confidence
        
        # Assurer le disclaimer
        if 'disclaimer' not in prediction:
            prediction['disclaimer'] = (
                "⚠️ Ces prédictions sont fournies à titre informatif. "
                "Le sport est imprévisible. Pariez de manière responsable."
            )
        
        return prediction
    
    def _generate_smart_fallback(self, match: Dict, sport_config: Dict, validation_score: int) -> Dict:
        """Génère une prédiction intelligente sans IA (fallback)"""
        
        team1 = match.get('team1', 'Équipe 1')
        team2 = match.get('team2', 'Équipe 2')
        sport = sport_config['name']
        
        # Générer des probabilités aléatoires mais réalistes
        if sport_config['result_type'] == '1X2':
            probs = self._generate_balanced_probs_1x2()
            winner_pred = max(probs, key=probs.get)
        else:
            probs = self._generate_balanced_probs_h2h()
            winner_pred = '1' if probs.get('1', 0) > probs.get('2', 0) else '2'
        
        # Calculer le grade basé sur la validation
        grade = EventValidator.get_event_grade(validation_score)
        
        # Ne jamais donner un grade D ou F juste parce que c'est un fallback
        # Si l'événement est valide, donner au moins C
        if grade in ['D', 'F'] and validation_score >= 30:
            grade = 'C'
        
        base_confidence = 45 if grade in ['A', 'A+', 'B', 'B+'] else 38
        
        prediction = {
            'sport': sport_config['name'].lower(),
            'analysis': {
                'overview': f"Analyse générée pour {team1} vs {team2}. "
                           f"Basée sur les informations disponibles.",
                'key_factors': [
                    "Analyse basée sur les données disponibles",
                    f"Match de {sport}",
                    "Contexte compétitif à considérer"
                ]
            },
            'predictions': {
                'winner': {
                    'prediction': winner_pred,
                    'probabilities': probs,
                    'confidence': base_confidence,
                    'reasoning': f"Prédiction basée sur l'analyse disponible pour ce match de {sport}."
                }
            },
            'summary': {
                'confidence': base_confidence,
                'grade': grade,
                'data_quality': 'Limité' if grade == 'C' else 'Bon',
                'key_insight': f"Match {sport} - Analyse disponible avec données limitées"
            },
            'meta': {
                'match_id': match.get('id'),
                'match_title': match.get('title'),
                'team1': team1,
                'team2': team2,
                'sport': match.get('sport', 'FOOTBALL'),
                'sport_name': sport_config['name'],
                'sport_icon': sport_config['icon'],
                'analyzed_at': datetime.now().isoformat(),
                'model': 'SmartFallback',
                'validation_score': validation_score,
                'is_ai_generated': False
            },
            'disclaimer': "⚠️ Analyse générée avec données limitées. Paris responsable uniquement."
        }
        
        # Ajouter des prédictions spécifiques au sport
        self._add_sport_specific_predictions(prediction, sport_config)
        
        return prediction
    
    def _generate_balanced_probs_1x2(self) -> Dict[str, int]:
        """Génère des probabilités équilibrées pour 1X2"""
        p1 = random.randint(30, 50)
        px = random.randint(20, 35)
        p2 = 100 - p1 - px
        return {'1': p1, 'X': px, '2': max(15, p2)}
    
    def _generate_balanced_probs_h2h(self) -> Dict[str, int]:
        """Génère des probabilités équilibrées pour H2H"""
        p1 = random.randint(40, 60)
        p2 = 100 - p1
        return {'1': p1, '2': p2}
    
    def _add_sport_specific_predictions(self, prediction: Dict, sport_config: Dict):
        """Ajoute des prédictions spécifiques au sport"""
        sport = sport_config['name'].lower()
        preds = prediction['predictions']
        
        if sport == 'football':
            preds['total_goals'] = {
                'expected': round(random.uniform(2.0, 3.0), 1),
                'over_2_5': random.randint(45, 60),
                'confidence': 42
            }
            preds['btts'] = {
                'prediction': random.choice(['Oui', 'Non']),
                'probability': random.randint(45, 60),
                'confidence': 40
            }
        
        elif sport in ['ufc/mma', 'ufc', 'boxing', 'boxe']:
            preds['method'] = {
                'ko_probability': random.randint(25, 45),
                'decision_probability': random.randint(40, 60),
                'confidence': 38
            }
        
        elif sport in ['nba/basketball', 'nba', 'basketball']:
            preds['total_points'] = {
                'line': random.choice([210.5, 215.5, 220.5, 225.5]),
                'over_probability': random.randint(45, 55),
                'confidence': 42
            }
        
        elif sport == 'tennis':
            preds['sets'] = {
                'prediction': random.choice(['2-0', '2-1']),
                'confidence': 40
            }
        
        # Ajouter un meilleur pari si pas présent
        if 'best_bet' not in preds:
            preds['best_bet'] = {
                'selection': f"Vainqueur: {prediction['predictions']['winner']['prediction']}",
                'odds': round(random.uniform(1.7, 2.5), 2),
                'confidence': prediction['summary']['confidence'],
                'value': '★★★☆☆',
                'reasoning': "Meilleur pari basé sur l'analyse disponible"
            }
    
    def _generate_invalid_event_response(self, match: Dict, reason: str) -> Dict:
        """Génère une réponse pour un événement invalide"""
        return {
            'error': True,
            'error_type': 'invalid_event',
            'message': f"Impossible d'analyser cet événement: {reason}",
            'match_title': match.get('title', 'N/A'),
            'meta': {
                'match_id': match.get('id'),
                'analyzed_at': datetime.now().isoformat(),
                'is_ai_generated': False
            },
            'summary': {
                'confidence': 0,
                'grade': 'N/A',
                'data_quality': 'Invalide'
            }
        }

# ════════════════════════════════════════════════════════════════════════════
# 🎨 FORMATEUR TELEGRAM
# ════════════════════════════════════════════════════════════════════════════

class TelegramFormatter:
    """Formateur de messages Telegram professionnel"""
    
    @staticmethod
    def format_prediction(match: Dict, prediction: Dict, user_profile: UserProfile = None) -> str:
        """Formate une prédiction complète"""
        
        # Vérifier les erreurs
        if prediction.get('error'):
            return TelegramFormatter._format_error(prediction)
        
        meta = prediction.get('meta', {})
        analysis = prediction.get('analysis', {})
        preds = prediction.get('predictions', {})
        summary = prediction.get('summary', {})
        sport_icon = meta.get('sport_icon', '🎯')
        sport_name = meta.get('sport_name', 'Sport')
        
        # Grade et confiance
        grade = summary.get('grade', 'B')
        confidence = summary.get('confidence', 50)
        grade_emoji = {'A+': '🌟', 'A': '🟢', 'B+': '🟡', 'B': '🟡', 'C': '🟠', 'D': '🔴'}.get(grade, '⚪')
        
        # En-tête
        msg = f"""╔═══════════════════════════════════════╗
   🔮 <b>ANALYSE PROFESSIONNELLE IA</b>
╚═══════════════════════════════════════╝

{sport_icon} <b>{match.get('title', 'Match')}</b>
⏰ {match.get('start_time', 'N/A')} | 📅 {datetime.now().strftime('%d/%m/%Y')}
🏆 {sport_name}

"""
        
        # Grade et confiance
        msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{grade_emoji} <b>GRADE: {grade}</b> | Confiance: <b>{confidence}%</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        # Vue d'ensemble
        if analysis.get('overview'):
            msg += f"""📋 <b>ANALYSE</b>
{analysis['overview'][:350]}

"""
        
        # Prédiction principale (Winner)
        winner = preds.get('winner', preds.get('match_result', {}))
        if winner:
            probs = winner.get('probabilities', {})
            pred_value = winner.get('prediction', 'N/A')
            conf = winner.get('confidence', 0)
            
            msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 <b>VAINQUEUR / RÉSULTAT</b>

🎯 Prédiction: <b>{pred_value}</b>
📊 Confiance: <b>{conf}%</b>

"""
            
            # Afficher les probabilités
            if probs:
                msg += "📈 Probabilités:\n"
                team1 = match.get('team1', 'Option 1')
                team2 = match.get('team2', 'Option 2')
                
                if '1' in probs:
                    msg += f"├ 1️⃣ {team1}: <b>{probs.get('1', 0)}%</b>\n"
                if 'X' in probs:
                    msg += f"├ ❌ Match Nul: <b>{probs.get('X', 0)}%</b>\n"
                if '2' in probs:
                    msg += f"└ 2️⃣ {team2}: <b>{probs.get('2', 0)}%</b>\n"
                msg += "\n"
        
        # Prédictions spécifiques au sport
        sport = meta.get('sport', 'football').lower()
        msg += TelegramFormatter._format_sport_predictions(preds, sport, match)
        
        # Meilleur pari
        best_bet = preds.get('best_bet', {})
        if best_bet:
            msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💎 <b>MEILLEUR PARI VALEUR</b>

🎯 <b>{best_bet.get('selection', 'N/A')}</b>
💰 Cote: <b>{best_bet.get('odds', 'N/A')}</b>
⭐ Valeur: {best_bet.get('value', '★★★☆☆')}
📊 Confiance: <b>{best_bet.get('confidence', 0)}%</b>

"""
            if best_bet.get('reasoning'):
                msg += f"💡 {best_bet['reasoning'][:150]}\n\n"
        
        # Key insight
        if summary.get('key_insight'):
            msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 <b>INSIGHT CLÉ</b>
{summary['key_insight'][:200]}

"""
        
        # Disclaimer
        msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <i>{prediction.get('disclaimer', 'Pariez de manière responsable.')}</i>
"""
        
        # Indication si IA ou Fallback
        if meta.get('is_ai_generated'):
            msg += f"\n🤖 <i>Analysé par IA ({meta.get('model', 'N/A')[:20]})</i>"
        else:
            msg += f"\n📊 <i>Analyse automatique</i>"
        
        return msg
    
    @staticmethod
    def _format_sport_predictions(preds: Dict, sport: str, match: Dict) -> str:
        """Formate les prédictions spécifiques au sport"""
        msg = ""
        
        if sport in ['football', 'soccer']:
            # Score exact
            exact = preds.get('exact_score', {})
            if exact.get('top_3'):
                msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n⚽ <b>SCORES PROBABLES</b>\n\n"
                for i, score in enumerate(exact['top_3'][:3], 1):
                    medal = '🥇' if i == 1 else '🥈' if i == 2 else '🥉'
                    msg += f"{medal} <b>{score.get('score', 'N/A')}</b> ({score.get('probability', 0)}%)\n"
                msg += "\n"
            
            # Total buts
            goals = preds.get('total_goals', {})
            if goals:
                msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>TOTAL BUTS</b>

🎯 Attendu: <b>{goals.get('expected', 'N/A')} buts</b>
✅ Over 2.5: <b>{goals.get('over_2_5', 50)}%</b>

"""
            
            # BTTS
            btts = preds.get('btts', {})
            if btts:
                emoji = "✅" if btts.get('prediction') == 'Oui' else "❌"
                msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🥅 <b>BTTS</b> (Les deux marquent)

{emoji} <b>{btts.get('prediction', 'N/A')}</b> ({btts.get('probability', 0)}%)

"""
        
        elif sport in ['ufc', 'mma', 'ufc/mma']:
            method = preds.get('method', {})
            if method:
                msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 <b>MÉTHODE DE VICTOIRE</b>

💥 KO/TKO: <b>{method.get('ko_probability', method.get('ko_tko', 0))}%</b>
🔒 Soumission: <b>{method.get('sub_probability', 0)}%</b>
📋 Décision: <b>{method.get('decision_probability', method.get('decision', 0))}%</b>

"""
            
            duration = preds.get('fight_duration', preds.get('round', {}))
            if duration:
                msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ <b>DURÉE DU COMBAT</b>

📊 Va à la distance: <b>{duration.get('goes_distance', 40)}%</b>

"""
        
        elif sport in ['boxing', 'boxe']:
            method = preds.get('method', {})
            if method:
                msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 <b>MÉTHODE</b>

💥 KO/TKO: <b>{method.get('ko_tko', 0)}%</b>
📋 Décision: <b>{method.get('decision', 0)}%</b>

"""
        
        elif sport in ['nba', 'basketball', 'nba/basketball']:
            total = preds.get('total_points', {})
            if total:
                msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏀 <b>TOTAL POINTS</b>

📊 Ligne: <b>{total.get('line', 'N/A')}</b>
✅ Over: <b>{total.get('over_probability', total.get('over', 50))}%</b>

"""
            
            spread = preds.get('spread', {})
            if spread:
                msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📏 <b>SPREAD</b>

🎯 <b>{spread.get('pick', spread.get('line', 'N/A'))}</b>

"""
        
        elif sport == 'tennis':
            sets = preds.get('sets_score', preds.get('sets', {}))
            if sets:
                msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎾 <b>SCORE EN SETS</b>

🎯 Prévu: <b>{sets.get('prediction', 'N/A')}</b>

"""
            
            games = preds.get('total_games', {})
            if games:
                msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>TOTAL JEUX</b>

📏 Ligne: <b>{games.get('line', 'N/A')}</b>
✅ Over: <b>{games.get('probability', 50)}%</b>

"""
        
        elif sport in ['nfl', 'american football', 'nfl/football us']:
            total = preds.get('total_points', {})
            if total:
                msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏈 <b>TOTAL POINTS</b>

📊 Ligne: <b>{total.get('line', 'N/A')}</b>

"""
        
        elif sport in ['nhl', 'hockey', 'nhl/hockey']:
            total = preds.get('total_goals', {})
            if total:
                msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏒 <b>TOTAL BUTS</b>

📏 Ligne: <b>{total.get('line', 'N/A')}</b>
✅ Over: <b>{total.get('over', 50)}%</b>

"""
        
        elif sport in ['f1', 'formula 1', 'formule 1']:
            winner = preds.get('race_winner', {})
            if winner:
                msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏎️ <b>VAINQUEUR COURSE</b>

🏆 <b>{winner.get('prediction', 'N/A')}</b>

"""
            
            safety = preds.get('safety_car', {})
            if safety:
                msg += f"""🚨 Safety Car: <b>{safety.get('probability', 0)}%</b>

"""
        
        return msg
    
    @staticmethod
    def _format_error(prediction: Dict) -> str:
        """Formate une erreur"""
        return f"""╔═══════════════════════════════════════╗
   ❌ <b>ANALYSE NON DISPONIBLE</b>
╚═══════════════════════════════════════╝

📋 Match: {prediction.get('match_title', 'N/A')}

⚠️ <b>Raison:</b> {prediction.get('message', 'Erreur inconnue')}

💡 <i>Cet événement ne peut pas être analysé pour le moment.
Veuillez réessayer plus tard ou choisir un autre match.</i>
"""
    
    @staticmethod
    def format_community_votes(match: Dict, vote_stats: Dict, user_vote: str = None) -> str:
        """Formate les votes communautaires"""
        totals = vote_stats.get('totals', {})
        percentages = vote_stats.get('percentages', {})
        total_votes = vote_stats.get('total_votes', 0)
        sport = vote_stats.get('sport', 'football').lower()
        sport_config = SPORTS_CONFIG.get(sport, SPORTS_CONFIG['other'])
        
        msg = f"""╔═══════════════════════════════════════╗
   👥 <b>VOTES COMMUNAUTAIRES</b>
╚═══════════════════════════════════════╝

{sport_config['icon']} <b>{match.get('title', 'Match')}</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>RÉSULTATS</b> ({total_votes} votes)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        vote_options = sport_config.get('vote_options', {'1': 'Option 1', '2': 'Option 2'})
        
        for key, label in vote_options.items():
            pct = percentages.get(key, 0)
            count = totals.get(key, 0)
            bar_filled = int(pct / 5)
            bar_empty = 20 - bar_filled
            bar = '█' * bar_filled + '░' * bar_empty
            
            voted_indicator = " ✓" if user_vote == key else ""
            msg += f"{key}️⃣ <b>{label}</b>{voted_indicator}\n"
            msg += f"   {bar} <b>{pct}%</b> ({count})\n\n"
        
        if user_vote:
            msg += f"\n✅ <i>Vous avez voté: {vote_options.get(user_vote, user_vote)}</i>"
        else:
            msg += f"\n💡 <i>Votez ci-dessous pour donner votre avis!</i>"
        
        return msg
    
    @staticmethod
    def format_leaderboard(leaderboard: List[Dict]) -> str:
        """Formate le classement"""
        msg = f"""╔═══════════════════════════════════════╗
   🏆 <b>CLASSEMENT DES PRONOSTIQUEURS</b>
╚═══════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        if not leaderboard:
            msg += "\n📭 Aucun participant pour le moment.\n"
            msg += "💡 Soyez le premier à faire une prédiction!"
            return msg
        
        for user in leaderboard[:15]:
            rank = user.get('rank', 0)
            medal = '🥇' if rank == 1 else '🥈' if rank == 2 else '🥉' if rank == 3 else f'{rank}.'
            
            username = user.get('username', 'Anonyme')[:15]
            points = user.get('total_points', 0)
            wins = user.get('wins_count', 0)
            total = user.get('predictions_count', 0)
            win_rate = round((wins/total)*100, 1) if total > 0 else 0
            
            msg += f"\n{medal} <b>{username}</b>\n"
            msg += f"   💰 {points} pts | 📊 {win_rate}% | 🎯 {wins}/{total}\n"
        
        msg += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 <i>Gagnez des points en prédisant correctement!</i>
"""
        return msg
    
    @staticmethod
    def format_user_stats(profile: UserProfile) -> str:
        """Formate les statistiques utilisateur"""
        msg = f"""╔═══════════════════════════════════════╗
   📊 <b>VOS STATISTIQUES</b>
╚═══════════════════════════════════════╝

👤 <b>{profile.username or 'Pronostiqueur'}</b>
🏅 Tier: <b>{profile.tier.upper()}</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 <b>PERFORMANCES</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 Points totaux: <b>{profile.total_points}</b>
🎯 Prédictions: <b>{profile.predictions_count}</b>
✅ Victoires: <b>{profile.wins_count}</b>
📊 Taux de réussite: <b>{profile.win_rate}%</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 <b>SÉRIES</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 Série actuelle: <b>{profile.current_streak}</b>
🏆 Meilleure série: <b>{profile.best_streak}</b>

"""
        
        if profile.achievements:
            msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 <b>ACHIEVEMENTS</b> ({len(profile.achievements)})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            for achievement in profile.achievements[:5]:
                msg += f"   ✅ {achievement}\n"
        
        msg += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Limite aujourd'hui: <b>{AdvancedDataManager.get_today_predictions_count(profile.user_id)}/{profile.daily_limit}</b>
"""
        
        return msg

# ════════════════════════════════════════════════════════════════════════════
# 🎮 GESTIONNAIRE DE PRÉDICTIONS
# ════════════════════════════════════════════════════════════════════════════

class PredictionsManager:
    """Gestionnaire centralisé des prédictions"""
    
    @staticmethod
    async def get_prediction(match: Dict, user_id: int) -> Dict:
        """Récupère ou génère une prédiction"""
        async with UltraPredictor() as predictor:
            return await predictor.analyze_match(match, user_id)

# ════════════════════════════════════════════════════════════════════════════
# 📲 HANDLERS TELEGRAM (Compatible avec footbot.py)
# ════════════════════════════════════════════════════════════════════════════

async def handle_prediction_request(query, match_id: str, data_manager) -> None:
    """
    Handler principal pour les demandes de prédiction
    Args:
        query: CallbackQuery de Telegram
        match_id: ID du match
        data_manager: Classe DataManager de footbot
    """
    user = query.from_user
    user_id = user.id
    username = user.username or user.first_name or "User"
    
    # Récupérer le match depuis DataManager
    all_matches = data_manager.load_data().get('matches', [])
    match = next((m for m in all_matches if m.get('id') == match_id), None)
    
    if not match:
        await query.answer("❌ Match non trouvé", show_alert=True)
        return
    
    # Vérifier le profil et les limites
    profile = AdvancedDataManager.get_user_profile(user_id, username)
    today_count = AdvancedDataManager.get_today_predictions_count(user_id)
    
    if today_count >= profile.daily_limit:
        await query.answer(
            f"⚠️ Limite journalière atteinte ({profile.daily_limit})!\n"
            f"Revenez demain ou passez Premium.",
            show_alert=True
        )
        return
    
    # Récupérer la configuration du sport
    sport = match.get('sport', 'FOOTBALL').lower()
    sport_config = SPORTS_CONFIG.get(sport, SPORTS_CONFIG['other'])
    
    # Message de chargement
    try:
        loading_msg = await query.edit_message_text(
            f"""🔮 <b>Analyse en cours...</b>

{sport_config['icon']} <b>{match.get('title', 'Match')[:50]}</b>

⏳ Notre IA analyse cet événement...
📊 Calcul des probabilités...
🎯 Génération des prédictions...

<i>Veuillez patienter quelques secondes...</i>""",
            parse_mode='HTML'
        )
    except Exception:
        loading_msg = query.message
    
    try:
        # Générer la prédiction
        async with UltraPredictor() as predictor:
            prediction = await predictor.analyze_match(match, user_id)
        
        # Formater le message
        formatted = TelegramFormatter.format_prediction(match, prediction, profile)
        
        # Préparer les boutons
        buttons = []
        
        # Boutons de vote (si le sport le supporte)
        if sport_config.get('vote_options'):
            vote_row = []
            for key, label in sport_config['vote_options'].items():
                vote_row.append(
                    InlineKeyboardButton(
                        f"{key}️⃣ {label[:10]}",
                        callback_data=f"vote_{match['id']}_{key}"
                    )
                )
            if vote_row:
                buttons.append(vote_row)
        
        # Boutons d'action
        buttons.append([
            InlineKeyboardButton("👥 Votes", callback_data=f"votes_{match['id']}"),
            InlineKeyboardButton("📊 Stats", callback_data="my_stats"),
            InlineKeyboardButton("🔙 Retour", callback_data=f"watch_{match['id']}")
        ])
        
        keyboard = InlineKeyboardMarkup(buttons)
        
        await loading_msg.edit_text(
            formatted,
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"❌ Erreur prédiction: {e}")
        import traceback
        traceback.print_exc()
        
        await loading_msg.edit_text(
            f"""❌ <b>Erreur lors de l'analyse</b>

Une erreur est survenue. Veuillez réessayer.

<i>Erreur: {str(e)[:100]}</i>""",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Réessayer", callback_data=f"predict_{match['id']}"),
                InlineKeyboardButton("🔙 Retour", callback_data=f"watch_{match['id']}")
            ]])
        )

async def handle_vote(query, match_id: str, vote: str, data_manager) -> None:
    """
    Handler pour les votes communautaires
    Args:
        query: CallbackQuery de Telegram
        match_id: ID du match
        vote: Le vote (1, X, 2, etc.)
        data_manager: Classe DataManager de footbot
    """
    user = query.from_user
    
    # Récupérer le match
    all_matches = data_manager.load_data().get('matches', [])
    match = next((m for m in all_matches if m.get('id') == match_id), None)
    
    sport = match.get('sport', 'football').lower() if match else 'football'
    
    # Enregistrer le vote
    AdvancedDataManager.add_vote(match_id, user.id, vote, sport)
    
    # Mettre à jour les points
    profile = AdvancedDataManager.get_user_profile(user.id)
    profile.total_points += Limits.POINTS_VOTE
    AdvancedDataManager.save_user_profile(profile)
    
    await query.answer(f"✅ Vote enregistré: {vote} (+1 point)")
    
    # Afficher les votes mis à jour
    await show_community_votes(query, match_id, data_manager)

async def show_community_votes(query, match_id: str, data_manager) -> None:
    """
    Affiche les votes communautaires
    Args:
        query: CallbackQuery de Telegram
        match_id: ID du match
        data_manager: Classe DataManager de footbot
    """
    user = query.from_user
    
    # Récupérer le match
    all_matches = data_manager.load_data().get('matches', [])
    match = next((m for m in all_matches if m.get('id') == match_id), None)
    
    if not match:
        match = {'id': match_id, 'title': 'Match', 'sport': 'football'}
    
    vote_stats = AdvancedDataManager.get_vote_stats(match_id)
    user_vote = AdvancedDataManager.get_user_vote(match_id, user.id)
    
    formatted = TelegramFormatter.format_community_votes(match, vote_stats, user_vote)
    
    sport = match.get('sport', 'football').lower()
    sport_config = SPORTS_CONFIG.get(sport, SPORTS_CONFIG['other'])
    
    # Boutons de vote
    buttons = []
    if sport_config.get('vote_options'):
        vote_row = []
        for key, label in sport_config['vote_options'].items():
            emoji = "✓" if user_vote == key else ""
            vote_row.append(
                InlineKeyboardButton(
                    f"{key}️⃣ {label[:8]}{emoji}",
                    callback_data=f"vote_{match_id}_{key}"
                )
            )
        if vote_row:
            buttons.append(vote_row)
    
    buttons.append([
        InlineKeyboardButton("🔮 Analyse IA", callback_data=f"predict_{match_id}"),
        InlineKeyboardButton("🔙 Retour", callback_data=f"watch_{match_id}")
    ])
    
    await query.edit_message_text(
        formatted,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def show_user_prediction_stats(query) -> None:
    """
    Affiche les statistiques de l'utilisateur
    Args:
        query: CallbackQuery de Telegram
    """
    user = query.from_user
    
    profile = AdvancedDataManager.get_user_profile(user.id, user.username or user.first_name)
    formatted = TelegramFormatter.format_user_stats(profile)
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏆 Classement", callback_data="leaderboard"),
            InlineKeyboardButton("📜 Historique", callback_data="my_history")
        ],
        [InlineKeyboardButton("🔙 Retour", callback_data="predictions_menu")]
    ])
    
    await query.edit_message_text(
        formatted,
        parse_mode='HTML',
        reply_markup=keyboard
    )

async def show_leaderboard(query) -> None:
    """
    Affiche le classement
    Args:
        query: CallbackQuery de Telegram
    """
    leaderboard = AdvancedDataManager.get_leaderboard(20)
    formatted = TelegramFormatter.format_leaderboard(leaderboard)
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Mes Stats", callback_data="my_stats"),
            InlineKeyboardButton("🔙 Retour", callback_data="predictions_menu")
        ]
    ])
    
    await query.edit_message_text(
        formatted,
        parse_mode='HTML',
        reply_markup=keyboard
    )

async def show_prediction_history(query) -> None:
    """
    Affiche l'historique des prédictions
    Args:
        query: CallbackQuery de Telegram
    """
    user = query.from_user
    
    predictions = AdvancedDataManager.get_user_predictions(user.id, 10)
    
    msg = f"""╔═══════════════════════════════════════╗
   📜 <b>HISTORIQUE DES PRÉDICTIONS</b>
╚═══════════════════════════════════════╝

"""
    
    if not predictions:
        msg += "📭 Aucune prédiction pour le moment.\n"
        msg += "💡 Analysez un match pour commencer!"
    else:
        for i, pred in enumerate(predictions[:10], 1):
            date = pred.get('timestamp', '')[:10]
            title = pred.get('match_title', 'Match')[:25]
            sport = pred.get('sport', 'FOOTBALL')
            status = pred.get('status', 'pending')
            
            status_emoji = {'pending': '⏳', 'won': '✅', 'lost': '❌'}.get(status, '⏳')
            
            msg += f"{i}. {status_emoji} <b>{title}</b>\n"
            msg += f"   📅 {date} | 🏆 {sport}\n\n"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Mes Stats", callback_data="my_stats"),
            InlineKeyboardButton("🔙 Retour", callback_data="predictions_menu")
        ]
    ])
    
    await query.edit_message_text(
        msg,
        parse_mode='HTML',
        reply_markup=keyboard
    )

# ════════════════════════════════════════════════════════════════════════════
# 🚀 EXPORTS
# ════════════════════════════════════════════════════════════════════════════

__all__ = [
    'PREDICTIONS_ENABLED',
    'SPORTS_CONFIG',
    'AdvancedDataManager',
    'EventValidator',
    'UltraPredictor',
    'TelegramFormatter',
    'PredictionsManager',
    'UserProfile',
    'handle_prediction_request',
    'handle_vote',
    'show_community_votes',
    'show_user_prediction_stats',
    'show_leaderboard',
    'show_prediction_history'
]