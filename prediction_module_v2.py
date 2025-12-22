"""
🔮 MODULE PRONOSTICS ULTRA-PROFESSIONNEL V2.0 - FootBot
═══════════════════════════════════════════════════════════════════════════════
Version Premium avec:
- Groq IA Multi-Modèle
- Statistiques en temps réel (API-Football)
- Système de votes communautaires
- Gamification & Classements
- Notifications push
- Suivi des résultats
- Analytics avancées
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
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

logger = logging.getLogger("footbot.predictions")

# ════════════════════════════════════════════════════════════════════════════
# ⚙️ CONFIGURATION AVANCÉE
# ════════════════════════════════════════════════════════════════════════════

# APIs Configuration
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

# API-Football (pour stats réelles) - https://www.api-football.com/
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "").strip()
API_FOOTBALL_URL = "https://v3.football.api-sports.io"

# Modèles Groq disponibles (fallback chain)
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile", 
    "mixtral-8x7b-32768",
    "llama-3.1-8b-instant"
]

# Répertoires de données
PREDICTIONS_DIR = Path("data/footbot/predictions")
PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)

# Fichiers de données
FILES = {
    'cache': PREDICTIONS_DIR / "predictions_cache.json",
    'history': PREDICTIONS_DIR / "predictions_history.json",
    'stats': PREDICTIONS_DIR / "predictions_stats.json",
    'votes': PREDICTIONS_DIR / "community_votes.json",
    'leaderboard': PREDICTIONS_DIR / "leaderboard.json",
    'notifications': PREDICTIONS_DIR / "notifications.json",
    'results': PREDICTIONS_DIR / "results_tracking.json",
    'achievements': PREDICTIONS_DIR / "achievements.json"
}

# Configuration des limites
class Limits:
    CACHE_DURATION = 1800  # 30 minutes
    MAX_PREDICTIONS_FREE = 5  # Par jour (gratuit)
    MAX_PREDICTIONS_PREMIUM = 50  # Par jour (premium)
    RATE_LIMIT_WINDOW = 60  # 1 minute
    RATE_LIMIT_MAX = 3  # Requêtes par minute
    VOTE_WINDOW = 3600  # 1 heure pour voter
    POINTS_CORRECT_RESULT = 10
    POINTS_CORRECT_SCORE = 50
    POINTS_CORRECT_BTTS = 5
    POINTS_CORRECT_OVER = 5
    POINTS_VOTE = 1
    POINTS_STREAK_BONUS = 5  # Par match correct consécutif

# ════════════════════════════════════════════════════════════════════════════
# 📊 ENUMS & DATA CLASSES
# ════════════════════════════════════════════════════════════════════════════

class PredictionStatus(Enum):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    PARTIAL = "partial"
    VOID = "void"

class UserTier(Enum):
    FREE = "free"
    PREMIUM = "premium"
    VIP = "vip"
    ADMIN = "admin"

class AchievementType(Enum):
    FIRST_PREDICTION = "first_prediction"
    TEN_PREDICTIONS = "ten_predictions"
    FIFTY_PREDICTIONS = "fifty_predictions"
    FIRST_WIN = "first_win"
    TEN_WINS = "ten_wins"
    PERFECT_SCORE = "perfect_score"
    STREAK_5 = "streak_5"
    STREAK_10 = "streak_10"
    TOP_10 = "top_10"
    TOP_3 = "top_3"
    COMMUNITY_LEADER = "community_leader"
    EXPERT = "expert"

ACHIEVEMENTS_CONFIG = {
    AchievementType.FIRST_PREDICTION: {
        "name": "🎯 Premier Pas",
        "description": "Première prédiction effectuée",
        "points": 10,
        "icon": "🎯"
    },
    AchievementType.TEN_PREDICTIONS: {
        "name": "📊 Analyste",
        "description": "10 prédictions effectuées",
        "points": 25,
        "icon": "📊"
    },
    AchievementType.FIFTY_PREDICTIONS: {
        "name": "🏆 Expert",
        "description": "50 prédictions effectuées",
        "points": 100,
        "icon": "🏆"
    },
    AchievementType.FIRST_WIN: {
        "name": "✅ Victoire",
        "description": "Première prédiction gagnante",
        "points": 15,
        "icon": "✅"
    },
    AchievementType.TEN_WINS: {
        "name": "🔥 En Feu",
        "description": "10 prédictions gagnantes",
        "points": 50,
        "icon": "🔥"
    },
    AchievementType.PERFECT_SCORE: {
        "name": "💎 Score Parfait",
        "description": "Score exact prédit correctement",
        "points": 100,
        "icon": "💎"
    },
    AchievementType.STREAK_5: {
        "name": "⚡ Série de 5",
        "description": "5 prédictions correctes consécutives",
        "points": 75,
        "icon": "⚡"
    },
    AchievementType.STREAK_10: {
        "name": "🌟 Légende",
        "description": "10 prédictions correctes consécutives",
        "points": 200,
        "icon": "🌟"
    },
    AchievementType.TOP_10: {
        "name": "🥉 Top 10",
        "description": "Atteindre le Top 10 du classement",
        "points": 50,
        "icon": "🥉"
    },
    AchievementType.TOP_3: {
        "name": "🥇 Podium",
        "description": "Atteindre le Top 3 du classement",
        "points": 150,
        "icon": "🥇"
    }
}

@dataclass
class UserProfile:
    user_id: int
    username: str
    tier: UserTier = UserTier.FREE
    total_points: int = 0
    predictions_count: int = 0
    wins_count: int = 0
    current_streak: int = 0
    best_streak: int = 0
    achievements: List[str] = None
    joined_at: str = None
    last_active: str = None
    notifications_enabled: bool = True
    favorite_sports: List[str] = None
    
    def __post_init__(self):
        if self.achievements is None:
            self.achievements = []
        if self.favorite_sports is None:
            self.favorite_sports = []
        if self.joined_at is None:
            self.joined_at = datetime.now().isoformat()
        self.last_active = datetime.now().isoformat()
    
    @property
    def win_rate(self) -> float:
        if self.predictions_count == 0:
            return 0.0
        return (self.wins_count / self.predictions_count) * 100
    
    @property
    def daily_limit(self) -> int:
        if self.tier in [UserTier.VIP, UserTier.ADMIN]:
            return 100
        elif self.tier == UserTier.PREMIUM:
            return Limits.MAX_PREDICTIONS_PREMIUM
        return Limits.MAX_PREDICTIONS_FREE

@dataclass
class CommunityVote:
    match_id: str
    user_id: int
    vote: str  # "1", "X", "2"
    timestamp: str
    
@dataclass 
class PredictionResult:
    prediction_id: str
    match_id: str
    actual_score: str
    predicted_score: str
    result_correct: bool
    score_correct: bool
    btts_correct: bool
    over_correct: bool
    corners_correct: bool
    cards_correct: bool
    points_earned: int
    verified_at: str

# ════════════════════════════════════════════════════════════════════════════
# 💾 GESTIONNAIRE DE DONNÉES AVANCÉ
# ════════════════════════════════════════════════════════════════════════════

class AdvancedDataManager:
    """Gestionnaire de données avec cache intelligent et persistence"""
    
    _cache: Dict[str, Any] = {}
    _cache_timestamps: Dict[str, float] = {}
    
    @classmethod
    def _load_file(cls, file_key: str, default: Any = None) -> Any:
        """Charge un fichier JSON avec cache"""
        filepath = FILES.get(file_key)
        if not filepath:
            return default if default is not None else {}
        
        # Vérifier le cache
        cache_key = str(filepath)
        if cache_key in cls._cache:
            if time.time() - cls._cache_timestamps.get(cache_key, 0) < 60:
                return cls._cache[cache_key]
        
        try:
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                cls._cache[cache_key] = data
                cls._cache_timestamps[cache_key] = time.time()
                return data
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Erreur chargement {file_key}: {e}")
        
        return default if default is not None else {}
    
    @classmethod
    def _save_file(cls, file_key: str, data: Any):
        """Sauvegarde un fichier JSON"""
        filepath = FILES.get(file_key)
        if not filepath:
            return
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            # Mettre à jour le cache
            cache_key = str(filepath)
            cls._cache[cache_key] = data
            cls._cache_timestamps[cache_key] = time.time()
        except IOError as e:
            logger.error(f"Erreur sauvegarde {file_key}: {e}")
    
    # === CACHE PRÉDICTIONS ===
    @classmethod
    def get_prediction_cache(cls, cache_key: str) -> Optional[Dict]:
        """Récupère une prédiction du cache"""
        cache = cls._load_file('cache', {})
        if cache_key in cache:
            entry = cache[cache_key]
            if time.time() - entry.get('timestamp', 0) < Limits.CACHE_DURATION:
                return entry.get('data')
        return None
    
    @classmethod
    def set_prediction_cache(cls, cache_key: str, data: Dict):
        """Sauvegarde une prédiction dans le cache"""
        cache = cls._load_file('cache', {})
        cache[cache_key] = {
            'data': data,
            'timestamp': time.time()
        }
        # Nettoyer les anciennes entrées
        now = time.time()
        cache = {k: v for k, v in cache.items() 
                 if now - v.get('timestamp', 0) < Limits.CACHE_DURATION * 2}
        cls._save_file('cache', cache)
    
    # === PROFILS UTILISATEURS ===
    @classmethod
    def get_user_profile(cls, user_id: int, username: str = None) -> UserProfile:
        """Récupère ou crée un profil utilisateur"""
        stats = cls._load_file('stats', {'users': {}})
        user_key = str(user_id)
        
        if user_key in stats.get('users', {}):
            user_data = stats['users'][user_key]
            profile = UserProfile(
                user_id=user_id,
                username=user_data.get('username', username or 'User'),
                tier=UserTier(user_data.get('tier', 'free')),
                total_points=user_data.get('total_points', 0),
                predictions_count=user_data.get('predictions_count', 0),
                wins_count=user_data.get('wins_count', 0),
                current_streak=user_data.get('current_streak', 0),
                best_streak=user_data.get('best_streak', 0),
                achievements=user_data.get('achievements', []),
                joined_at=user_data.get('joined_at'),
                notifications_enabled=user_data.get('notifications_enabled', True),
                favorite_sports=user_data.get('favorite_sports', [])
            )
        else:
            profile = UserProfile(user_id=user_id, username=username or 'User')
            cls.save_user_profile(profile)
        
        return profile
    
    @classmethod
    def save_user_profile(cls, profile: UserProfile):
        """Sauvegarde un profil utilisateur"""
        stats = cls._load_file('stats', {'users': {}})
        if 'users' not in stats:
            stats['users'] = {}
        
        stats['users'][str(profile.user_id)] = {
            'user_id': profile.user_id,
            'username': profile.username,
            'tier': profile.tier.value,
            'total_points': profile.total_points,
            'predictions_count': profile.predictions_count,
            'wins_count': profile.wins_count,
            'current_streak': profile.current_streak,
            'best_streak': profile.best_streak,
            'achievements': profile.achievements,
            'joined_at': profile.joined_at,
            'last_active': datetime.now().isoformat(),
            'notifications_enabled': profile.notifications_enabled,
            'favorite_sports': profile.favorite_sports
        }
        cls._save_file('stats', stats)
    
    # === HISTORIQUE ===
    @classmethod
    def add_prediction_to_history(cls, user_id: int, match: Dict, prediction: Dict):
        """Ajoute une prédiction à l'historique"""
        history = cls._load_file('history', {'predictions': []})
        
        entry = {
            'prediction_id': f"pred_{int(time.time())}_{user_id}_{random.randint(1000,9999)}",
            'user_id': user_id,
            'match_id': match['id'],
            'match_title': match['title'],
            'team1': match.get('team1', ''),
            'team2': match.get('team2', ''),
            'sport': match['sport'],
            'prediction_data': prediction,
            'timestamp': datetime.now().isoformat(),
            'status': PredictionStatus.PENDING.value,
            'points_earned': 0
        }
        
        history['predictions'].append(entry)
        
        # Garder les 5000 dernières
        if len(history['predictions']) > 5000:
            history['predictions'] = history['predictions'][-5000:]
        
        cls._save_file('history', history)
        return entry['prediction_id']
    
    @classmethod
    def get_user_predictions(cls, user_id: int, limit: int = 20) -> List[Dict]:
        """Récupère les prédictions d'un utilisateur"""
        history = cls._load_file('history', {'predictions': []})
        user_preds = [p for p in history['predictions'] if p['user_id'] == user_id]
        return sorted(user_preds, key=lambda x: x['timestamp'], reverse=True)[:limit]
    
    @classmethod
    def get_today_predictions_count(cls, user_id: int) -> int:
        """Compte les prédictions du jour"""
        history = cls._load_file('history', {'predictions': []})
        today = datetime.now().date().isoformat()
        return len([
            p for p in history['predictions']
            if p['user_id'] == user_id and p['timestamp'][:10] == today
        ])
    
    # === VOTES COMMUNAUTAIRES ===
    @classmethod
    def add_vote(cls, match_id: str, user_id: int, vote: str) -> Dict:
        """Ajoute un vote communautaire"""
        votes = cls._load_file('votes', {'matches': {}})
        
        if match_id not in votes['matches']:
            votes['matches'][match_id] = {
                'votes': [],
                'totals': {'1': 0, 'X': 0, '2': 0},
                'created_at': datetime.now().isoformat()
            }
        
        match_votes = votes['matches'][match_id]
        
        # Vérifier si déjà voté
        existing = next((v for v in match_votes['votes'] if v['user_id'] == user_id), None)
        if existing:
            # Mettre à jour le vote
            old_vote = existing['vote']
            match_votes['totals'][old_vote] = max(0, match_votes['totals'][old_vote] - 1)
            existing['vote'] = vote
            existing['timestamp'] = datetime.now().isoformat()
        else:
            match_votes['votes'].append({
                'user_id': user_id,
                'vote': vote,
                'timestamp': datetime.now().isoformat()
            })
        
        match_votes['totals'][vote] = match_votes['totals'].get(vote, 0) + 1
        
        cls._save_file('votes', votes)
        return match_votes['totals']
    
    @classmethod
    def get_vote_stats(cls, match_id: str) -> Dict:
        """Récupère les statistiques de votes"""
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
                }
            }
        return {'totals': {'1': 0, 'X': 0, '2': 0}, 'total_votes': 0, 'percentages': {}}
    
    @classmethod
    def get_user_vote(cls, match_id: str, user_id: int) -> Optional[str]:
        """Récupère le vote d'un utilisateur"""
        votes = cls._load_file('votes', {'matches': {}})
        if match_id in votes['matches']:
            for v in votes['matches'][match_id]['votes']:
                if v['user_id'] == user_id:
                    return v['vote']
        return None
    
    # === LEADERBOARD ===
    @classmethod
    def get_leaderboard(cls, period: str = 'all', limit: int = 20) -> List[Dict]:
        """Récupère le classement"""
        stats = cls._load_file('stats', {'users': {}})
        users = list(stats.get('users', {}).values())
        
        # Filtrer par période si nécessaire
        if period == 'weekly':
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            # Pour weekly, il faudrait stocker les points par période
            # Simplifié ici
        elif period == 'monthly':
            month_ago = (datetime.now() - timedelta(days=30)).isoformat()
        
        # Trier par points
        sorted_users = sorted(users, key=lambda x: x.get('total_points', 0), reverse=True)
        
        # Ajouter le rang
        for i, user in enumerate(sorted_users[:limit], 1):
            user['rank'] = i
        
        return sorted_users[:limit]
    
    @classmethod
    def update_leaderboard_position(cls, user_id: int) -> int:
        """Met à jour et retourne la position au classement"""
        leaderboard = cls.get_leaderboard(limit=1000)
        for user in leaderboard:
            if user.get('user_id') == user_id:
                return user.get('rank', 0)
        return 0
    
    # === ACHIEVEMENTS ===
    @classmethod
    def check_and_award_achievements(cls, profile: UserProfile) -> List[str]:
        """Vérifie et attribue les achievements"""
        new_achievements = []
        
        checks = [
            (AchievementType.FIRST_PREDICTION, profile.predictions_count >= 1),
            (AchievementType.TEN_PREDICTIONS, profile.predictions_count >= 10),
            (AchievementType.FIFTY_PREDICTIONS, profile.predictions_count >= 50),
            (AchievementType.FIRST_WIN, profile.wins_count >= 1),
            (AchievementType.TEN_WINS, profile.wins_count >= 10),
            (AchievementType.STREAK_5, profile.best_streak >= 5),
            (AchievementType.STREAK_10, profile.best_streak >= 10),
        ]
        
        # Vérifier le classement
        rank = cls.update_leaderboard_position(profile.user_id)
        if rank > 0:
            checks.append((AchievementType.TOP_10, rank <= 10))
            checks.append((AchievementType.TOP_3, rank <= 3))
        
        for achievement_type, condition in checks:
            if condition and achievement_type.value not in profile.achievements:
                profile.achievements.append(achievement_type.value)
                new_achievements.append(achievement_type.value)
                profile.total_points += ACHIEVEMENTS_CONFIG[achievement_type]['points']
        
        if new_achievements:
            cls.save_user_profile(profile)
        
        return new_achievements
    
    # === NOTIFICATIONS ===
    @classmethod
    def add_notification(cls, user_id: int, notification_type: str, data: Dict):
        """Ajoute une notification"""
        notifications = cls._load_file('notifications', {'pending': []})
        
        notifications['pending'].append({
            'id': f"notif_{int(time.time())}_{user_id}",
            'user_id': user_id,
            'type': notification_type,
            'data': data,
            'created_at': datetime.now().isoformat(),
            'sent': False
        })
        
        # Garder les 1000 dernières
        if len(notifications['pending']) > 1000:
            notifications['pending'] = notifications['pending'][-1000:]
        
        cls._save_file('notifications', notifications)
    
    @classmethod
    def get_pending_notifications(cls, user_id: int = None) -> List[Dict]:
        """Récupère les notifications en attente"""
        notifications = cls._load_file('notifications', {'pending': []})
        pending = [n for n in notifications['pending'] if not n.get('sent')]
        
        if user_id:
            pending = [n for n in pending if n['user_id'] == user_id]
        
        return pending

# ════════════════════════════════════════════════════════════════════════════
# 🌐 API STATISTIQUES RÉELLES
# ════════════════════════════════════════════════════════════════════════════

class RealStatsProvider:
    """Fournisseur de statistiques réelles via API-Football"""
    
    def __init__(self):
        self.api_key = API_FOOTBALL_KEY
        self.base_url = API_FOOTBALL_URL
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache = {}
    
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        } if self.api_key else {}
        
        self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_team(self, team_name: str) -> Optional[Dict]:
        """Recherche une équipe par nom"""
        if not self.api_key:
            return None
        
        cache_key = f"team_{team_name.lower()}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            url = f"{self.base_url}/teams"
            params = {'search': team_name}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('response'):
                        team = data['response'][0]
                        self.cache[cache_key] = team
                        return team
        except Exception as e:
            logger.error(f"Erreur recherche équipe: {e}")
        
        return None
    
    async def get_team_stats(self, team_id: int, league_id: int = None) -> Dict:
        """Récupère les statistiques d'une équipe"""
        if not self.api_key:
            return self._generate_simulated_stats()
        
        try:
            # Statistiques de l'équipe
            url = f"{self.base_url}/teams/statistics"
            params = {
                'team': team_id,
                'season': datetime.now().year,
                'league': league_id or 39  # Premier League par défaut
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('response'):
                        return self._parse_team_stats(data['response'])
        except Exception as e:
            logger.error(f"Erreur stats équipe: {e}")
        
        return self._generate_simulated_stats()
    
    async def get_h2h(self, team1_id: int, team2_id: int) -> Dict:
        """Récupère l'historique des confrontations directes"""
        if not self.api_key:
            return self._generate_simulated_h2h()
        
        try:
            url = f"{self.base_url}/fixtures/headtohead"
            params = {'h2h': f"{team1_id}-{team2_id}", 'last': 10}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('response'):
                        return self._parse_h2h(data['response'])
        except Exception as e:
            logger.error(f"Erreur H2H: {e}")
        
        return self._generate_simulated_h2h()
    
    async def get_live_odds(self, fixture_id: int) -> Dict:
        """Récupère les cotes en direct"""
        if not self.api_key:
            return self._generate_simulated_odds()
        
        try:
            url = f"{self.base_url}/odds"
            params = {'fixture': fixture_id}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('response'):
                        return self._parse_odds(data['response'])
        except Exception as e:
            logger.error(f"Erreur cotes: {e}")
        
        return self._generate_simulated_odds()
    
    def _parse_team_stats(self, data: Dict) -> Dict:
        """Parse les statistiques d'équipe"""
        fixtures = data.get('fixtures', {})
        goals = data.get('goals', {})
        
        return {
            'matches_played': fixtures.get('played', {}).get('total', 0),
            'wins': fixtures.get('wins', {}).get('total', 0),
            'draws': fixtures.get('draws', {}).get('total', 0),
            'losses': fixtures.get('losses', {}).get('total', 0),
            'goals_for': goals.get('for', {}).get('total', {}).get('total', 0),
            'goals_against': goals.get('against', {}).get('total', {}).get('total', 0),
            'goals_for_avg': goals.get('for', {}).get('average', {}).get('total', '0'),
            'goals_against_avg': goals.get('against', {}).get('average', {}).get('total', '0'),
            'clean_sheets': data.get('clean_sheet', {}).get('total', 0),
            'failed_to_score': data.get('failed_to_score', {}).get('total', 0),
            'form': data.get('form', 'WWDLL')[:5],
            'data_source': 'API-Football'
        }
    
    def _parse_h2h(self, matches: List) -> Dict:
        """Parse l'historique H2H"""
        if not matches:
            return self._generate_simulated_h2h()
        
        team1_wins = 0
        team2_wins = 0
        draws = 0
        total_goals = 0
        
        for match in matches:
            home_goals = match['goals']['home'] or 0
            away_goals = match['goals']['away'] or 0
            total_goals += home_goals + away_goals
            
            if home_goals > away_goals:
                team1_wins += 1
            elif away_goals > home_goals:
                team2_wins += 1
            else:
                draws += 1
        
        return {
            'total_matches': len(matches),
            'team1_wins': team1_wins,
            'team2_wins': team2_wins,
            'draws': draws,
            'avg_goals': round(total_goals / len(matches), 2) if matches else 0,
            'last_matches': [
                {
                    'date': m['fixture']['date'][:10],
                    'score': f"{m['goals']['home']}-{m['goals']['away']}",
                    'home': m['teams']['home']['name'],
                    'away': m['teams']['away']['name']
                }
                for m in matches[:5]
            ],
            'data_source': 'API-Football'
        }
    
    def _parse_odds(self, data: List) -> Dict:
        """Parse les cotes"""
        if not data:
            return self._generate_simulated_odds()
        
        odds = {'1': 0, 'X': 0, '2': 0}
        
        for bookmaker in data:
            for bet in bookmaker.get('bets', []):
                if bet.get('name') == 'Match Winner':
                    for value in bet.get('values', []):
                        if value['value'] == 'Home':
                            odds['1'] = float(value['odd'])
                        elif value['value'] == 'Draw':
                            odds['X'] = float(value['odd'])
                        elif value['value'] == 'Away':
                            odds['2'] = float(value['odd'])
                    break
            if odds['1'] > 0:
                break
        
        return {
            'match_winner': odds,
            'over_2_5': 1.85,
            'btts_yes': 1.75,
            'data_source': 'API-Football'
        }
    
    def _generate_simulated_stats(self) -> Dict:
        """Génère des statistiques simulées"""
        return {
            'matches_played': random.randint(15, 38),
            'wins': random.randint(5, 20),
            'draws': random.randint(3, 12),
            'losses': random.randint(2, 15),
            'goals_for': random.randint(20, 70),
            'goals_against': random.randint(15, 50),
            'goals_for_avg': str(round(random.uniform(1.2, 2.5), 2)),
            'goals_against_avg': str(round(random.uniform(0.8, 1.8), 2)),
            'clean_sheets': random.randint(3, 15),
            'failed_to_score': random.randint(2, 10),
            'form': ''.join(random.choices(['W', 'D', 'L'], weights=[45, 25, 30], k=5)),
            'data_source': 'Simulation'
        }
    
    def _generate_simulated_h2h(self) -> Dict:
        """Génère un historique H2H simulé"""
        total = random.randint(5, 15)
        team1_wins = random.randint(1, total - 2)
        team2_wins = random.randint(1, total - team1_wins - 1)
        draws = total - team1_wins - team2_wins
        
        return {
            'total_matches': total,
            'team1_wins': team1_wins,
            'team2_wins': team2_wins,
            'draws': draws,
            'avg_goals': round(random.uniform(2.0, 3.5), 2),
            'last_matches': [],
            'data_source': 'Simulation'
        }
    
    def _generate_simulated_odds(self) -> Dict:
        """Génère des cotes simulées"""
        return {
            'match_winner': {
                '1': round(random.uniform(1.5, 4.0), 2),
                'X': round(random.uniform(3.0, 4.5), 2),
                '2': round(random.uniform(1.8, 5.0), 2)
            },
            'over_2_5': round(random.uniform(1.6, 2.2), 2),
            'btts_yes': round(random.uniform(1.6, 2.0), 2),
            'data_source': 'Simulation'
        }

# ════════════════════════════════════════════════════════════════════════════
# 🧠 PROMPT SYSTÈME ULTRA-AVANCÉ
# ════════════════════════════════════════════════════════════════════════════

ULTRA_SYSTEM_PROMPT = """Tu es un analyste sportif d'élite mondiale avec 20+ ans d'expérience, spécialisé dans:
- Analyse statistique avancée (xG, xA, possession pondérée)
- Modélisation prédictive (régression, machine learning)
- Psychologie sportive et dynamique d'équipe
- Analyse tactique approfondie

═══════════════════════════════════════════════════════════════════════════════
🎯 OBJECTIFS D'ANALYSE
═══════════════════════════════════════════════════════════════════════════════

Tu dois fournir des prédictions ULTRA-DÉTAILLÉES sur:

1. 🏆 RÉSULTAT DU MATCH (1/X/2) - avec probabilités précises
2. ⚽ SCORE EXACT - top 3 scores les plus probables
3. 📊 TOTAL DE BUTS - Over/Under (1.5, 2.5, 3.5, 4.5)
4. 🥅 BTTS (Les deux équipes marquent) - Oui/Non
5. 🚩 CORNERS - Total, par équipe, Over/Under
6. 🟨 CARTONS JAUNES - Total, Over/Under
7. 🟥 CARTONS ROUGES - Probabilité
8. ⏱️ MI-TEMPS - Résultat et score HT
9. 🎯 PREMIER BUTEUR - Équipe et période
10. 🛡️ CLEAN SHEET - Par équipe
11. 📈 PARIS COMBINÉS recommandés
12. 💎 MEILLEUR PARI VALEUR

═══════════════════════════════════════════════════════════════════════════════
📐 MÉTHODOLOGIE DE CALCUL
═══════════════════════════════════════════════════════════════════════════════

Pour chaque prédiction, utilise cette méthodologie:

1. **Base statistique** (40%): 
   - Forme récente (5 derniers matchs)
   - Statistiques de la saison
   - Performance domicile/extérieur

2. **Facteur H2H** (25%):
   - Historique des confrontations directes
   - Tendances récentes

3. **Contexte** (20%):
   - Importance du match
   - Fatigue/calendrier
   - Motivations

4. **Ajustements** (15%):
   - Blessures/Suspensions
   - Conditions météo
   - Arbitrage

═══════════════════════════════════════════════════════════════════════════════
📊 ÉCHELLE DE CONFIANCE
═══════════════════════════════════════════════════════════════════════════════

- 65-70%: 🟢 TRÈS FORTE - Multiples facteurs alignés
- 55-64%: 🟡 FORTE - Bons indicateurs
- 45-54%: 🟠 MOYENNE - Incertitudes modérées
- 35-44%: 🔴 FAIBLE - Données limitées
- <35%: ⚫ TRÈS FAIBLE - Ne pas parier

⚠️ IMPORTANT: Ne JAMAIS dépasser 70% de confiance

═══════════════════════════════════════════════════════════════════════════════
📋 FORMAT JSON OBLIGATOIRE
═══════════════════════════════════════════════════════════════════════════════

{
  "analysis": {
    "overview": "Résumé contextuel du match",
    "key_factors": ["facteur1", "facteur2", "facteur3", "facteur4", "facteur5"],
    "tactical_preview": "Analyse tactique attendue",
    "momentum": {
      "team1": "Bon/Moyen/Mauvais + explication",
      "team2": "Bon/Moyen/Mauvais + explication"
    }
  },
  
  "predictions": {
    "match_result": {
      "prediction": "1/X/2",
      "probabilities": {"1": 45, "X": 28, "2": 27},
      "confidence": 58,
      "odds_value": 1.95,
      "reasoning": "Justification détaillée"
    },
    
    "exact_score": {
      "top_3": [
        {"score": "2-1", "probability": 12, "odds": 8.5},
        {"score": "1-1", "probability": 10, "odds": 6.0},
        {"score": "2-0", "probability": 9, "odds": 9.0}
      ],
      "confidence": 35,
      "reasoning": "Justification"
    },
    
    "total_goals": {
      "expected": 2.7,
      "over_1_5": {"prediction": "Oui", "probability": 78, "odds": 1.25},
      "over_2_5": {"prediction": "Oui", "probability": 55, "odds": 1.85},
      "over_3_5": {"prediction": "Non", "probability": 35, "odds": 2.40},
      "over_4_5": {"prediction": "Non", "probability": 18, "odds": 4.00},
      "confidence": 52,
      "reasoning": "Justification"
    },
    
    "btts": {
      "prediction": "Oui/Non",
      "probability": 62,
      "odds": 1.72,
      "confidence": 55,
      "reasoning": "Justification"
    },
    
    "corners": {
      "expected_total": 10.5,
      "team1": {"expected": 5.5, "range": "4-7"},
      "team2": {"expected": 5.0, "range": "4-6"},
      "over_8_5": {"prediction": "Oui", "probability": 68},
      "over_9_5": {"prediction": "Oui", "probability": 55},
      "over_10_5": {"prediction": "Non", "probability": 42},
      "over_11_5": {"prediction": "Non", "probability": 30},
      "confidence": 48,
      "reasoning": "Justification"
    },
    
    "cards": {
      "yellow": {
        "expected": 4.2,
        "range": "3-6",
        "over_2_5": {"prediction": "Oui", "probability": 75},
        "over_3_5": {"prediction": "Oui", "probability": 58},
        "over_4_5": {"prediction": "Non", "probability": 40},
        "over_5_5": {"prediction": "Non", "probability": 25}
      },
      "red": {
        "probability": 15,
        "expected": "0-1"
      },
      "confidence": 45,
      "reasoning": "Justification basée sur arbitre et style de jeu"
    },
    
    "halftime": {
      "result": "1/X/2",
      "score": "1-0",
      "probabilities": {"1": 40, "X": 35, "2": 25},
      "confidence": 42,
      "reasoning": "Justification"
    },
    
    "special": {
      "first_goal": {
        "team": "Équipe 1/Équipe 2",
        "period": "0-15min/16-30min/31-45min/46-60min/61-75min/76-90min",
        "probability": 45,
        "confidence": 38
      },
      "clean_sheet": {
        "team1": {"prediction": "Non", "probability": 35},
        "team2": {"prediction": "Non", "probability": 28}
      },
      "win_to_nil": {
        "team1": {"prediction": "Non", "probability": 22},
        "team2": {"prediction": "Non", "probability": 18}
      }
    },
    
    "combo_bets": [
      {
        "name": "Combo Sûr",
        "selections": ["1X", "Over 1.5", "BTTS Oui"],
        "combined_odds": 2.10,
        "confidence": 60,
        "risk": "Faible"
      },
      {
        "name": "Combo Valeur",
        "selections": ["1", "Over 2.5", "Corners +9.5"],
        "combined_odds": 4.50,
        "confidence": 40,
        "risk": "Moyen"
      }
    ],
    
    "best_value_bet": {
      "selection": "Description du pari",
      "odds": 2.20,
      "confidence": 55,
      "value_rating": "★★★★☆",
      "stake_suggestion": "2-3% de la bankroll",
      "reasoning": "Pourquoi ce pari a de la valeur"
    }
  },
  
  "risk_assessment": {
    "overall_risk": "Faible/Moyen/Élevé/Très élevé",
    "volatility": "Faible/Moyenne/Élevée",
    "upset_potential": 25,
    "key_risks": ["risque1", "risque2", "risque3"],
    "bet_recommendation": "Paris recommandés vs éviter"
  },
  
  "summary": {
    "overall_confidence": 52,
    "data_quality": "Excellent/Bon/Moyen/Faible",
    "prediction_grade": "A/B/C/D/F",
    "key_insight": "L'insight principal à retenir"
  },
  
  "disclaimer": "⚠️ Avertissement obligatoire"
}

═══════════════════════════════════════════════════════════════════════════════
⚠️ RÈGLES STRICTES
═══════════════════════════════════════════════════════════════════════════════

1. JAMAIS de confiance > 70%
2. TOUJOURS justifier chaque prédiction
3. Être PRÉCIS (fourchettes, pas vague)
4. Indiquer clairement si données manquantes
5. Format JSON STRICT obligatoire
6. Inclure TOUJOURS le disclaimer
7. Proposer des paris à VALEUR, pas populaires"""

# ════════════════════════════════════════════════════════════════════════════
# 🤖 PRÉDICTEUR IA ULTRA-AVANCÉ
# ════════════════════════════════════════════════════════════════════════════

class UltraPredictor:
    """Prédicteur IA de niveau professionnel"""
    
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.session: Optional[aiohttp.ClientSession] = None
        self.current_model_index = 0
        self.stats = {
            'total_predictions': 0,
            'cache_hits': 0,
            'api_calls': 0,
            'errors': 0,
            'model_fallbacks': 0
        }
    
    async def __aenter__(self):
        if not self.api_key:
            logger.warning("⚠️ GROQ_API_KEY non configurée - Mode simulation")
        
        timeout = aiohttp.ClientTimeout(total=90)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _call_groq(self, messages: List[Dict], model: str = None) -> Optional[str]:
        """Appel à l'API Groq avec fallback de modèles"""
        if not self.api_key:
            return None
        
        model = model or GROQ_MODELS[self.current_model_index]
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.15,
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
                    
                    usage = data.get('usage', {})
                    logger.info(
                        f"✅ Groq [{model[:20]}] | "
                        f"Tokens: {usage.get('total_tokens', 0)}"
                    )
                    
                    return content
                
                elif response.status == 429:
                    logger.warning(f"⚠️ Rate limit {model}, essai modèle suivant...")
                    self.stats['model_fallbacks'] += 1
                    
                    # Fallback au modèle suivant
                    if self.current_model_index < len(GROQ_MODELS) - 1:
                        self.current_model_index += 1
                        return await self._call_groq(messages, GROQ_MODELS[self.current_model_index])
                
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Groq {response.status}: {error_text[:200]}")
                    self.stats['errors'] += 1
        
        except asyncio.TimeoutError:
            logger.error("⏱️ Timeout Groq")
            self.stats['errors'] += 1
        except Exception as e:
            logger.error(f"❌ Exception Groq: {e}")
            self.stats['errors'] += 1
        
        return None
    
    async def analyze_match(
        self,
        match: Dict,
        user_id: int,
        real_stats: Dict = None,
        community_votes: Dict = None
    ) -> Dict:
        """Analyse complète d'un match"""
        
        # Vérifier le cache
        cache_key = f"ultra_{match['id']}"
        cached = AdvancedDataManager.get_prediction_cache(cache_key)
        if cached:
            self.stats['cache_hits'] += 1
            logger.info(f"💾 Cache hit: {match['title']}")
            return cached
        
        team1 = match.get('team1', match.get('title', 'Équipe 1'))
        team2 = match.get('team2', 'Équipe 2')
        sport = match.get('sport_name', match.get('sport', 'Sport'))
        
        # Construire le prompt utilisateur enrichi
        user_prompt = self._build_prompt(match, real_stats, community_votes)
        
        messages = [
            {"role": "system", "content": ULTRA_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        logger.info(f"🤖 Analyse IA: {team1} vs {team2}")
        
        response = await self._call_groq(messages)
        
        if response:
            try:
                prediction = self._parse_response(response)
                prediction = self._enrich_prediction(prediction, match, community_votes)
                
                # Sauvegarder dans le cache
                AdvancedDataManager.set_prediction_cache(cache_key, prediction)
                
                # Ajouter à l'historique
                AdvancedDataManager.add_prediction_to_history(user_id, match, prediction)
                
                # Mettre à jour le profil
                profile = AdvancedDataManager.get_user_profile(user_id)
                profile.predictions_count += 1
                AdvancedDataManager.save_user_profile(profile)
                
                # Vérifier les achievements
                new_achievements = AdvancedDataManager.check_and_award_achievements(profile)
                if new_achievements:
                    prediction['new_achievements'] = new_achievements
                
                self.stats['total_predictions'] += 1
                return prediction
                
            except Exception as e:
                logger.error(f"❌ Erreur parsing: {e}")
        
        # Fallback: prédiction simulée
        return self._generate_fallback_prediction(match)
    
    def _build_prompt(self, match: Dict, stats: Dict = None, votes: Dict = None) -> str:
        """Construit le prompt enrichi"""
        team1 = match.get('team1', match.get('title', 'Équipe 1'))
        team2 = match.get('team2', 'Équipe 2')
        
        prompt = f"""═══════════════════════════════════════════════════════════════════════════════
📋 ANALYSE DEMANDÉE
═══════════════════════════════════════════════════════════════════════════════

🏟️ MATCH: {team1} vs {team2}
🏆 COMPÉTITION: {match.get('sport_name', match.get('sport', 'N/A'))}
⏰ HORAIRE: {match.get('start_time', 'En direct')}
📅 DATE: {datetime.now().strftime('%d/%m/%Y')}
🔴 STATUT: {match.get('status', 'À venir')}

"""
        
        if stats:
            prompt += f"""═══════════════════════════════════════════════════════════════════════════════
📊 STATISTIQUES DISPONIBLES
═══════════════════════════════════════════════════════════════════════════════

{json.dumps(stats, indent=2, ensure_ascii=False)}

"""
        
        if votes:
            prompt += f"""═══════════════════════════════════════════════════════════════════════════════
👥 VOTES COMMUNAUTAIRES
═══════════════════════════════════════════════════════════════════════════════

Total votes: {votes.get('total_votes', 0)}
• Victoire {team1}: {votes.get('percentages', {}).get('1', 0)}%
• Match Nul: {votes.get('percentages', {}).get('X', 0)}%
• Victoire {team2}: {votes.get('percentages', {}).get('2', 0)}%

"""
        
        prompt += """═══════════════════════════════════════════════════════════════════════════════
🎯 INSTRUCTIONS
═══════════════════════════════════════════════════════════════════════════════

Fournis une analyse COMPLÈTE au format JSON avec TOUTES les prédictions demandées:
- Résultat (1/X/2)
- Score exact
- Total de buts
- BTTS
- Corners
- Cartons
- Mi-temps
- Paris spéciaux
- Combos recommandés
- Meilleur pari valeur

Sois PRÉCIS et JUSTIFIE chaque prédiction."""
        
        return prompt
    
    def _parse_response(self, response: str) -> Dict:
        """Parse la réponse JSON de l'IA"""
        response = response.strip()
        
        # Nettoyer les balises markdown
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        return json.loads(response.strip())
    
    def _enrich_prediction(self, prediction: Dict, match: Dict, votes: Dict = None) -> Dict:
        """Enrichit la prédiction avec des métadonnées"""
        prediction['meta'] = {
            'match_id': match['id'],
            'match_title': match['title'],
            'team1': match.get('team1', ''),
            'team2': match.get('team2', ''),
            'sport': match.get('sport', ''),
            'sport_icon': match.get('sport_icon', '⚽'),
            'analyzed_at': datetime.now().isoformat(),
            'model': GROQ_MODELS[self.current_model_index],
            'community_votes': votes
        }
        
        # Assurer le disclaimer
        if 'disclaimer' not in prediction:
            prediction['disclaimer'] = (
                "⚠️ Ces prédictions sont fournies à titre informatif uniquement. "
                "Le sport est imprévisible et aucun résultat n'est garanti. "
                "Pariez de manière responsable."
            )
        
        return prediction
    
    def _generate_fallback_prediction(self, match: Dict) -> Dict:
        """Génère une prédiction de secours"""
        team1 = match.get('team1', 'Équipe 1')
        team2 = match.get('team2', 'Équipe 2')
        
        return {
            'analysis': {
                'overview': f"Analyse basique pour {team1} vs {team2}",
                'key_factors': ["Données limitées", "Analyse simplifiée"],
                'tactical_preview': "Analyse tactique non disponible"
            },
            'predictions': {
                'match_result': {
                    'prediction': random.choice(['1', 'X', '2']),
                    'probabilities': {'1': 35, 'X': 30, '2': 35},
                    'confidence': 30,
                    'reasoning': "Prédiction basée sur données limitées"
                },
                'total_goals': {
                    'expected': 2.5,
                    'over_2_5': {'prediction': 'Oui', 'probability': 50},
                    'confidence': 30
                },
                'btts': {
                    'prediction': 'Oui',
                    'probability': 50,
                    'confidence': 30
                },
                'corners': {
                    'expected_total': 10,
                    'confidence': 25
                },
                'cards': {
                    'yellow': {'expected': 4, 'range': '2-6'},
                    'red': {'probability': 10},
                    'confidence': 25
                }
            },
            'summary': {
                'overall_confidence': 30,
                'data_quality': 'Faible',
                'prediction_grade': 'D',
                'key_insight': "Données insuffisantes pour une analyse fiable"
            },
            'disclaimer': "⚠️ Prédiction générée avec données limitées. Faible fiabilité.",
            'meta': {
                'match_id': match['id'],
                'match_title': match['title'],
                'analyzed_at': datetime.now().isoformat(),
                'model': 'Fallback',
                'is_fallback': True
            }
        }

# ════════════════════════════════════════════════════════════════════════════
# 🎨 FORMATEUR DE MESSAGES TELEGRAM
# ════════════════════════════════════════════════════════════════════════════

class TelegramFormatter:
    """Formateur de messages Telegram ultra-professionnel"""
    
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
        risk = prediction.get('risk_assessment', {})
        
        # En-tête
        msg = f"""╔═══════════════════════════════════════╗
   🔮 <b>ANALYSE PROFESSIONNELLE IA</b>
╚═══════════════════════════════════════╝

{meta.get('sport_icon', '⚽')} <b>{match.get('title', 'Match')}</b>
⏰ {match.get('start_time', 'N/A')} | 📅 {datetime.now().strftime('%d/%m/%Y')}

"""
        
        # Vue d'ensemble
        if analysis.get('overview'):
            msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 <b>ANALYSE</b>

{analysis['overview'][:300]}

"""
        
        # Résultat du match
        match_result = preds.get('match_result', {})
        if match_result:
            probs = match_result.get('probabilities', {})
            conf = match_result.get('confidence', 0)
            conf_emoji = "🟢" if conf >= 55 else "🟡" if conf >= 40 else "🔴"
            
            msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 <b>RÉSULTAT DU MATCH</b>

🎯 Prédiction: <b>{match_result.get('prediction', 'N/A')}</b>
{conf_emoji} Confiance: <b>{conf}%</b>

📊 Probabilités:
├ 1️⃣ Victoire {match.get('team1', 'Domicile')}: <b>{probs.get('1', 0)}%</b>
├ ❌ Match Nul: <b>{probs.get('X', 0)}%</b>
└ 2️⃣ Victoire {match.get('team2', 'Extérieur')}: <b>{probs.get('2', 0)}%</b>

"""
        
        # Score exact
        exact = preds.get('exact_score', {})
        if exact.get('top_3'):
            msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚽ <b>SCORES LES PLUS PROBABLES</b>

"""
            for i, score in enumerate(exact['top_3'][:3], 1):
                msg += f"{'🥇' if i==1 else '🥈' if i==2 else '🥉'} <b>{score.get('score', 'N/A')}</b> ({score.get('probability', 0)}%)\n"
            msg += "\n"
        
        # Total de buts
        goals = preds.get('total_goals', {})
        if goals:
            msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>TOTAL DE BUTS</b>

🎯 Attendu: <b>{goals.get('expected', 'N/A')} buts</b>

"""
            for key in ['over_1_5', 'over_2_5', 'over_3_5']:
                if key in goals:
                    data = goals[key]
                    emoji = "✅" if data.get('prediction') == 'Oui' else "❌"
                    label = key.replace('over_', 'Over ').replace('_', '.')
                    msg += f"{emoji} {label}: <b>{data.get('probability', 0)}%</b>\n"
            msg += "\n"
        
        # BTTS
        btts = preds.get('btts', {})
        if btts:
            btts_emoji = "✅" if btts.get('prediction') == 'Oui' else "❌"
            msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🥅 <b>LES DEUX ÉQUIPES MARQUENT</b>

{btts_emoji} Prédiction: <b>{btts.get('prediction', 'N/A')}</b>
📊 Probabilité: <b>{btts.get('probability', 0)}%</b>

"""
        
        # Corners
        corners = preds.get('corners', {})
        if corners:
            msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚩 <b>CORNERS</b>

📊 Total attendu: <b>{corners.get('expected_total', 'N/A')}</b>
"""
            team1_data = corners.get('team1', {})
            team2_data = corners.get('team2', {})
            if team1_data:
                msg += f"🔵 {match.get('team1', 'Dom')}: <b>{team1_data.get('range', team1_data.get('expected', 'N/A'))}</b>\n"
            if team2_data:
                msg += f"🔴 {match.get('team2', 'Ext')}: <b>{team2_data.get('range', team2_data.get('expected', 'N/A'))}</b>\n"
            msg += "\n"
        
        # Cartons
        cards = preds.get('cards', {})
        if cards:
            yellow = cards.get('yellow', {})
            red = cards.get('red', {})
            msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟨 <b>CARTONS</b>

🟨 Jaunes: <b>{yellow.get('expected', 'N/A')}</b> ({yellow.get('range', 'N/A')})
🟥 Rouges: <b>{red.get('probability', 0)}%</b> de probabilité

"""
        
        # Meilleur pari
        best_bet = preds.get('best_value_bet', {})
        if best_bet:
            msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💎 <b>MEILLEUR PARI VALEUR</b>

🎯 <b>{best_bet.get('selection', 'N/A')}</b>
💰 Cote: <b>{best_bet.get('odds', 'N/A')}</b>
⭐ Valeur: <b>{best_bet.get('value_rating', '★★★☆☆')}</b>
📝 {best_bet.get('reasoning', '')[:150]}

"""
        
        # Combos
        combos = preds.get('combo_bets', [])
        if combos:
            msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎲 <b>PARIS COMBINÉS</b>

"""
            for combo in combos[:2]:
                selections = ' + '.join(combo.get('selections', []))
                msg += f"• <b>{combo.get('name', 'Combo')}</b>\n"
                msg += f"  {selections}\n"
                msg += f"  💰 Cote: {combo.get('combined_odds', 'N/A')} | 🎯 {combo.get('confidence', 0)}%\n\n"
        
        # Résumé
        overall_conf = summary.get('overall_confidence', 0)
        grade = summary.get('prediction_grade', 'C')
        grade_emoji = {'A': '🏆', 'B': '🥈', 'C': '🥉', 'D': '📊', 'F': '❌'}.get(grade, '📊')
        
        msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>RÉSUMÉ</b>

{grade_emoji} Grade: <b>{grade}</b>
🎯 Confiance globale: <b>{overall_conf}%</b>
📈 Qualité données: <b>{summary.get('data_quality', 'N/A')}</b>

💡 <i>{summary.get('key_insight', '')[:200]}</i>

"""
        
        # Disclaimer
        msg += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>AVERTISSEMENT</b>

{prediction.get('disclaimer', '')[:200]}

🎮 <b>DIVERTISSEMENT UNIQUEMENT</b>
📞 Aide: joueurs-info-service.fr

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<i>🤖 Groq IA | {datetime.now().strftime('%d/%m/%Y %H:%M')}</i>"""
        
        # Nouveaux achievements
        if prediction.get('new_achievements'):
            msg += "\n\n🎉 <b>NOUVEAUX ACHIEVEMENTS !</b>\n"
            for ach_key in prediction['new_achievements']:
                try:
                    ach_type = AchievementType(ach_key)
                    ach = ACHIEVEMENTS_CONFIG[ach_type]
                    msg += f"{ach['icon']} <b>{ach['name']}</b> (+{ach['points']} pts)\n"
                except:
                    pass
        
        return msg
    
    @staticmethod
    def _format_error(prediction: Dict) -> str:
        """Formate un message d'erreur"""
        error_type = prediction.get('error')
        message = prediction.get('message', 'Erreur inconnue')
        
        if error_type == 'rate_limit':
            wait = prediction.get('wait_time', 60)
            return f"""⏳ <b>LIMITE TEMPORAIRE ATTEINTE</b>

Trop de requêtes en peu de temps.
⏰ Attendez <b>{wait}s</b> avant de réessayer.

💡 Cette limite protège le service."""
        
        elif error_type == 'daily_limit':
            used = prediction.get('used', 0)
            limit = prediction.get('limit', 5)
            return f"""🚫 <b>QUOTA JOURNALIER ATTEINT</b>

Vous avez utilisé <b>{used}/{limit}</b> analyses.

🔄 Revenez demain pour plus d'analyses !
⭐ Passez Premium pour 50 analyses/jour"""
        
        return f"""❌ <b>ERREUR</b>

{message}

🔄 Réessayez dans quelques instants."""
    
    @staticmethod
    def format_community_votes(match: Dict, votes: Dict, user_vote: str = None) -> str:
        """Formate les votes communautaires"""
        totals = votes.get('totals', {})
        percs = votes.get('percentages', {})
        total_votes = votes.get('total_votes', 0)
        
        team1 = match.get('team1', 'Équipe 1')
        team2 = match.get('team2', 'Équipe 2')
        
        # Barres de progression
        def make_bar(pct: float, length: int = 10) -> str:
            filled = int(pct / 100 * length)
            return "▓" * filled + "░" * (length - filled)
        
        msg = f"""╔═══════════════════════════════════════╗
   👥 <b>VOTES COMMUNAUTAIRES</b>
╚═══════════════════════════════════════╝

🏟️ <b>{match.get('title', 'Match')}</b>

📊 <b>Résultats ({total_votes} votes)</b>

1️⃣ <b>{team1}</b>
   {make_bar(percs.get('1', 0))} <b>{percs.get('1', 0)}%</b> ({totals.get('1', 0)})

❌ <b>Match Nul</b>
   {make_bar(percs.get('X', 0))} <b>{percs.get('X', 0)}%</b> ({totals.get('X', 0)})

2️⃣ <b>{team2}</b>
   {make_bar(percs.get('2', 0))} <b>{percs.get('2', 0)}%</b> ({totals.get('2', 0)})

"""
        
        if user_vote:
            vote_text = {'1': team1, 'X': 'Match Nul', '2': team2}.get(user_vote, user_vote)
            msg += f"✅ <b>Votre vote:</b> {vote_text}\n\n"
        else:
            msg += "👇 <b>Votez ci-dessous !</b>\n\n"
        
        msg += "<i>Votez pour gagner des points et comparez avec l'IA !</i>"
        
        return msg
    
    @staticmethod
    def format_leaderboard(leaderboard: List[Dict], user_rank: int = 0) -> str:
        """Formate le classement"""
        msg = """╔═══════════════════════════════════════╗
   🏆 <b>CLASSEMENT GÉNÉRAL</b>
╚═══════════════════════════════════════╝

"""
        
        medals = ['🥇', '🥈', '🥉']
        
        for i, user in enumerate(leaderboard[:15]):
            rank = user.get('rank', i + 1)
            medal = medals[rank - 1] if rank <= 3 else f"{rank}."
            username = user.get('username', 'Anonyme')[:15]
            points = user.get('total_points', 0)
            wins = user.get('wins_count', 0)
            win_rate = (wins / user.get('predictions_count', 1) * 100) if user.get('predictions_count', 0) > 0 else 0
            
            highlight = " 👈" if user.get('user_id') == user_rank else ""
            
            msg += f"{medal} <b>{username}</b>{highlight}\n"
            msg += f"   💰 {points} pts | ✅ {wins} wins ({win_rate:.0f}%)\n\n"
        
        if user_rank and user_rank > 15:
            msg += f"\n━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"📍 <b>Votre position:</b> #{user_rank}\n"
        
        return msg
    
    @staticmethod
    def format_user_stats(profile: UserProfile) -> str:
        """Formate les statistiques utilisateur"""
        tier_emoji = {
            UserTier.FREE: '🆓',
            UserTier.PREMIUM: '⭐',
            UserTier.VIP: '👑',
            UserTier.ADMIN: '🛡️'
        }
        
        msg = f"""╔═══════════════════════════════════════╗
   📊 <b>VOS STATISTIQUES</b>
╚═══════════════════════════════════════╝

👤 <b>{profile.username}</b>
{tier_emoji.get(profile.tier, '🆓')} Statut: <b>{profile.tier.value.upper()}</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 <b>PERFORMANCES</b>

💰 Points totaux: <b>{profile.total_points}</b>
🔮 Prédictions: <b>{profile.predictions_count}</b>
✅ Victoires: <b>{profile.wins_count}</b>
📊 Taux de réussite: <b>{profile.win_rate:.1f}%</b>

⚡ Série actuelle: <b>{profile.current_streak}</b>
🔥 Meilleure série: <b>{profile.best_streak}</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 <b>ACHIEVEMENTS ({len(profile.achievements)})</b>

"""
        
        if profile.achievements:
            for ach_key in profile.achievements[-5:]:  # 5 derniers
                try:
                    ach_type = AchievementType(ach_key)
                    ach = ACHIEVEMENTS_CONFIG[ach_type]
                    msg += f"{ach['icon']} <b>{ach['name']}</b>\n"
                except:
                    pass
        else:
            msg += "<i>Aucun achievement encore</i>\n"
        
        msg += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 <b>LIMITES</b>

📊 Analyses aujourd'hui: <b>?/{profile.daily_limit}</b>
🔄 Reset à minuit UTC

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📆 Membre depuis: {profile.joined_at[:10] if profile.joined_at else 'N/A'}"""
        
        return msg

# ════════════════════════════════════════════════════════════════════════════
# 🎮 HANDLERS TELEGRAM
# ════════════════════════════════════════════════════════════════════════════

async def handle_prediction_request(query, match_id: str, DataManager):
    """Handler principal pour les demandes de prédiction"""
    user = query.from_user
    user_id = user.id
    username = user.username or user.first_name or 'User'
    
    await query.answer("🔮 Lancement de l'analyse IA...")
    
    # Récupérer le profil utilisateur
    profile = AdvancedDataManager.get_user_profile(user_id, username)
    
    # Vérifier le quota journalier
    today_count = AdvancedDataManager.get_today_predictions_count(user_id)
    if today_count >= profile.daily_limit:
        keyboard = [
            [InlineKeyboardButton("⭐ Passer Premium", callback_data="upgrade_premium")],
            [InlineKeyboardButton("🔙 Retour", callback_data=f"watch_{match_id}")]
        ]
        await query.edit_message_text(
            TelegramFormatter._format_error({
                'error': 'daily_limit',
                'used': today_count,
                'limit': profile.daily_limit
            }),
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Message de chargement
    await query.edit_message_text(
        "╔═══════════════════════════════════════╗\n"
        "   ⏳ <b>ANALYSE IA EN COURS</b>\n"
        "╚═══════════════════════════════════════╝\n\n"
        "🤖 Initialisation Groq IA...\n"
        "📊 Collecte des statistiques...\n"
        "🧠 Analyse tactique...\n"
        "🎯 Calcul des probabilités...\n"
        "🔮 Génération des prédictions...\n\n"
        f"⏱️ <i>Estimation: 15-45 secondes</i>\n\n"
        f"📊 Analyses restantes: <b>{profile.daily_limit - today_count - 1}/{profile.daily_limit}</b>",
        parse_mode='HTML'
    )
    
    # Récupérer le match
    data = DataManager.load_data()
    match = next((m for m in data['matches'] if m['id'] == match_id), None)
    
    if not match:
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]
        await query.edit_message_text(
            "❌ <b>Match introuvable</b>\n\nLe match n'est plus disponible.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Récupérer les stats réelles et votes
    real_stats = None
    community_votes = AdvancedDataManager.get_vote_stats(match_id)
    
    # Optionnel: récupérer stats réelles si API configurée
    if API_FOOTBALL_KEY:
        try:
            async with RealStatsProvider() as provider:
                team1_search = await provider.search_team(match.get('team1', ''))
                team2_search = await provider.search_team(match.get('team2', ''))
                
                if team1_search and team2_search:
                    team1_id = team1_search['team']['id']
                    team2_id = team2_search['team']['id']
                    
                    team1_stats = await provider.get_team_stats(team1_id)
                    team2_stats = await provider.get_team_stats(team2_id)
                    h2h = await provider.get_h2h(team1_id, team2_id)
                    
                    real_stats = {
                        'team1': team1_stats,
                        'team2': team2_stats,
                        'h2h': h2h
                    }
        except Exception as e:
            logger.error(f"Erreur stats réelles: {e}")
    
    # Générer la prédiction
    try:
        async with UltraPredictor() as predictor:
            prediction = await predictor.analyze_match(
                match, user_id, real_stats, community_votes
            )
    except Exception as e:
        logger.error(f"Erreur prédiction: {e}")
        prediction = {'error': True, 'message': f"Erreur: {str(e)[:100]}"}
    
    # Formater le message
    message = TelegramFormatter.format_prediction(match, prediction, profile)
    
    # Créer le clavier
    keyboard = []
    
    if not prediction.get('error'):
        # Boutons de vote
        user_vote = AdvancedDataManager.get_user_vote(match_id, user_id)
        if not user_vote:
            keyboard.append([
                InlineKeyboardButton("1️⃣", callback_data=f"vote_{match_id}_1"),
                InlineKeyboardButton("❌", callback_data=f"vote_{match_id}_X"),
                InlineKeyboardButton("2️⃣", callback_data=f"vote_{match_id}_2")
            ])
        
        keyboard.append([
            InlineKeyboardButton("👥 Votes Communauté", callback_data=f"votes_{match_id}")
        ])
        
        keyboard.append([
            InlineKeyboardButton("🔄 Nouvelle Analyse", callback_data=f"predict_{match_id}")
        ])
    
    keyboard.extend([
        [InlineKeyboardButton("🔙 Match", callback_data=f"watch_{match_id}")],
        [
            InlineKeyboardButton("📊 Mes Stats", callback_data="my_stats"),
            InlineKeyboardButton("🏆 Classement", callback_data="leaderboard")
        ],
        [InlineKeyboardButton("🏠 Menu", callback_data="main_menu")]
    ])
    
    # Envoyer le message (avec gestion de la longueur)
    try:
        if len(message) > 4096:
            # Diviser en plusieurs messages
            parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for i, part in enumerate(parts[:-1]):
                await query.message.reply_text(part, parse_mode='HTML')
            await query.edit_message_text(
                parts[-1],
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text(
                message,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        logger.error(f"Erreur envoi: {e}")
        await query.edit_message_text(
            message[:3500] + "\n\n<i>[Message tronqué]</i>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_vote(query, match_id: str, vote: str, DataManager):
    """Handler pour les votes communautaires"""
    user_id = query.from_user.id
    
    # Enregistrer le vote
    totals = AdvancedDataManager.add_vote(match_id, user_id, vote)
    
    # Mettre à jour les points
    profile = AdvancedDataManager.get_user_profile(user_id)
    profile.total_points += Limits.POINTS_VOTE
    AdvancedDataManager.save_user_profile(profile)
    
    await query.answer(f"✅ Vote enregistré ! +{Limits.POINTS_VOTE} point")
    
    # Afficher les résultats
    data = DataManager.load_data()
    match = next((m for m in data['matches'] if m['id'] == match_id), None)
    
    if match:
        votes = AdvancedDataManager.get_vote_stats(match_id)
        message = TelegramFormatter.format_community_votes(match, votes, vote)
        
        keyboard = [
            [
                InlineKeyboardButton("1️⃣", callback_data=f"vote_{match_id}_1"),
                InlineKeyboardButton("❌", callback_data=f"vote_{match_id}_X"),
                InlineKeyboardButton("2️⃣", callback_data=f"vote_{match_id}_2")
            ],
            [InlineKeyboardButton("🔮 Voir Analyse IA", callback_data=f"predict_{match_id}")],
            [InlineKeyboardButton("🔙 Match", callback_data=f"watch_{match_id}")]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def show_community_votes(query, match_id: str, DataManager):
    """Affiche les votes communautaires"""
    await query.answer()
    
    user_id = query.from_user.id
    
    data = DataManager.load_data()
    match = next((m for m in data['matches'] if m['id'] == match_id), None)
    
    if not match:
        await query.answer("Match introuvable", show_alert=True)
        return
    
    votes = AdvancedDataManager.get_vote_stats(match_id)
    user_vote = AdvancedDataManager.get_user_vote(match_id, user_id)
    
    message = TelegramFormatter.format_community_votes(match, votes, user_vote)
    
    keyboard = []
    if not user_vote:
        keyboard.append([
            InlineKeyboardButton("1️⃣ Voter", callback_data=f"vote_{match_id}_1"),
            InlineKeyboardButton("❌ Voter", callback_data=f"vote_{match_id}_X"),
            InlineKeyboardButton("2️⃣ Voter", callback_data=f"vote_{match_id}_2")
        ])
    
    keyboard.extend([
        [InlineKeyboardButton("🔮 Analyse IA", callback_data=f"predict_{match_id}")],
        [InlineKeyboardButton("🔙 Match", callback_data=f"watch_{match_id}")]
    ])
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_user_prediction_stats(query):
    """Affiche les statistiques utilisateur"""
    await query.answer()
    
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    
    profile = AdvancedDataManager.get_user_profile(user_id, username)
    today_count = AdvancedDataManager.get_today_predictions_count(user_id)
    
    # Mettre à jour le nombre d'analyses aujourd'hui dans le message
    message = TelegramFormatter.format_user_stats(profile)
    message = message.replace(
        f"Analyses aujourd'hui: <b>?/{profile.daily_limit}</b>",
        f"Analyses aujourd'hui: <b>{today_count}/{profile.daily_limit}</b>"
    )
    
    # Récupérer la position au classement
    rank = AdvancedDataManager.update_leaderboard_position(user_id)
    if rank:
        message += f"\n🏆 <b>Classement:</b> #{rank}"
    
    keyboard = [
        [InlineKeyboardButton("🏆 Voir Classement", callback_data="leaderboard")],
        [InlineKeyboardButton("📜 Historique", callback_data="my_history")],
        [InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_leaderboard(query):
    """Affiche le classement"""
    await query.answer()
    
    user_id = query.from_user.id
    leaderboard = AdvancedDataManager.get_leaderboard(limit=15)
    
    message = TelegramFormatter.format_leaderboard(leaderboard, user_id)
    
    keyboard = [
        [
            InlineKeyboardButton("📅 Cette Semaine", callback_data="leaderboard_weekly"),
            InlineKeyboardButton("📆 Ce Mois", callback_data="leaderboard_monthly")
        ],
        [InlineKeyboardButton("📊 Mes Stats", callback_data="my_stats")],
        [InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_prediction_history(query):
    """Affiche l'historique des prédictions"""
    await query.answer()
    
    user_id = query.from_user.id
    predictions = AdvancedDataManager.get_user_predictions(user_id, limit=10)
    
    msg = """╔═══════════════════════════════════════╗
   📜 <b>HISTORIQUE DES PRÉDICTIONS</b>
╚═══════════════════════════════════════╝

"""
    
    if not predictions:
        msg += "<i>Aucune prédiction encore</i>\n\n"
        msg += "🔮 Faites votre première analyse !"
    else:
        for pred in predictions:
            status = pred.get('status', 'pending')
            status_emoji = {
                'pending': '⏳',
                'won': '✅',
                'lost': '❌',
                'partial': '🟡',
                'void': '⚫'
            }.get(status, '⏳')
            
            title = pred.get('match_title', 'Match')[:30]
            date = pred.get('timestamp', '')[:10]
            points = pred.get('points_earned', 0)
            
            msg += f"{status_emoji} <b>{title}</b>\n"
            msg += f"   📅 {date}"
            if points:
                msg += f" | 💰 +{points} pts"
            msg += "\n\n"
    
    keyboard = [
        [InlineKeyboardButton("📊 Mes Stats", callback_data="my_stats")],
        [InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        msg,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ════════════════════════════════════════════════════════════════════════════
# 🔄 EXPORTS
# ════════════════════════════════════════════════════════════════════════════

# Classes principales
PredictionsManager = AdvancedDataManager  # Alias pour compatibilité

# Exports pour footbot.py
__all__ = [
    'handle_prediction_request',
    'handle_vote',
    'show_community_votes',
    'show_user_prediction_stats',
    'show_leaderboard',
    'show_prediction_history',
    'PredictionsManager',
    'AdvancedDataManager',
    'UltraPredictor',
    'TelegramFormatter',
    'PREDICTIONS_ENABLED'
]

PREDICTIONS_ENABLED = True