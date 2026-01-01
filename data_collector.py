"""
🔬 DATA COLLECTOR ULTRA PRO V2.0 - RECHERCHE WEB RÉELLE
═══════════════════════════════════════════════════════════════════════════════
Collecte de données RÉELLES depuis:
- Sofascore (API + scraping)
- Flashscore (scraping)
- API-Football (API gratuite)
- Odds API (cotes des bookmakers)
- Recherche web (actualités, contexte)

L'IA reçoit TOUTES les données et génère SES PROPRES prédictions librement.
═══════════════════════════════════════════════════════════════════════════════
"""

import asyncio
import aiohttp
import logging
import json
import re
import os
import time
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from urllib.parse import quote

logger = logging.getLogger("footbot.data_collector")

# ════════════════════════════════════════════════════════════════════════════
# ⚙️ CONFIGURATION APIs
# ════════════════════════════════════════════════════════════════════════════

# API-Football (gratuit: 100 req/jour) - https://www.api-football.com/
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "")
API_FOOTBALL_URL = "https://v3.football.api-sports.io"

# The Odds API (gratuit: 500 req/mois) - https://the-odds-api.com/
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
ODDS_API_URL = "https://api.the-odds-api.com/v4"

# Log de configuration au démarrage
def log_api_status():
    """Affiche le statut des APIs configurées"""
    status = []
    if API_FOOTBALL_KEY:
        status.append("✅ API-Football: Configurée")
    else:
        status.append("⚠️ API-Football: Non configurée (ajoutez API_FOOTBALL_KEY)")
    
    if ODDS_API_KEY:
        status.append("✅ Odds API: Configurée")
    else:
        status.append("⚠️ Odds API: Non configurée (ajoutez ODDS_API_KEY)")
    
    for s in status:
        logger.info(s)
    
    return {
        'api_football': bool(API_FOOTBALL_KEY),
        'odds_api': bool(ODDS_API_KEY)
    }

# Appel au chargement du module
try:
    API_STATUS = log_api_status()
except:
    API_STATUS = {'api_football': False, 'odds_api': False}

# User agents pour le scraping
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
]

# ════════════════════════════════════════════════════════════════════════════
# 🔍 COLLECTEUR SOFASCORE
# ════════════════════════════════════════════════════════════════════════════

class SofascoreCollector:
    """Collecte les données depuis Sofascore API"""
    
    BASE_URL = "https://api.sofascore.com/api/v1"
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.headers = {
            'User-Agent': USER_AGENTS[0],
            'Accept': 'application/json',
            'Accept-Language': 'fr-FR,fr;q=0.9',
            'Origin': 'https://www.sofascore.com',
            'Referer': 'https://www.sofascore.com/'
        }
    
    async def search_match(self, team1: str, team2: str, sport: str = 'football') -> Optional[Dict]:
        """Recherche un match par noms d'équipes"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            url = f"{self.BASE_URL}/sport/{sport}/scheduled-events/{today}"
            
            async with self.session.get(url, headers=self.headers, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    events = data.get('events', [])
                    
                    team1_lower = team1.lower().strip()
                    team2_lower = team2.lower().strip()
                    
                    for event in events:
                        home = event.get('homeTeam', {}).get('name', '').lower()
                        away = event.get('awayTeam', {}).get('name', '').lower()
                        
                        if self._fuzzy_match(team1_lower, home) and self._fuzzy_match(team2_lower, away):
                            return event
                        if self._fuzzy_match(team2_lower, home) and self._fuzzy_match(team1_lower, away):
                            return event
                else:
                    logger.warning(f"Sofascore API: {response.status}")
        except Exception as e:
            logger.error(f"Sofascore search error: {e}")
        return None
    
    def _fuzzy_match(self, search: str, target: str) -> bool:
        """Match flexible entre deux noms"""
        if search in target or target in search:
            return True
        search_words = set(search.split())
        target_words = set(target.split())
        return len(search_words & target_words) >= 1
    
    async def get_match_details(self, event_id: int) -> Dict:
        """Récupère tous les détails d'un match"""
        data = {}
        endpoints = {
            'statistics': f"/event/{event_id}/statistics",
            'lineups': f"/event/{event_id}/lineups",
            'h2h': f"/event/{event_id}/h2h",
            'form': f"/event/{event_id}/pregame-form",
            'odds': f"/event/{event_id}/odds/1/all"
        }
        
        for key, endpoint in endpoints.items():
            try:
                url = f"{self.BASE_URL}{endpoint}"
                async with self.session.get(url, headers=self.headers, timeout=10) as r:
                    if r.status == 200:
                        data[key] = await r.json()
            except:
                pass
        
        return data
    
    async def get_team_stats(self, team_id: int) -> Dict:
        """Récupère les statistiques d'une équipe"""
        data = {}
        try:
            recent_url = f"{self.BASE_URL}/team/{team_id}/events/last/0"
            async with self.session.get(recent_url, headers=self.headers, timeout=10) as r:
                if r.status == 200:
                    data['recent_matches'] = await r.json()
        except:
            pass
        return data
    
    async def collect_all(self, team1: str, team2: str, sport: str = 'football') -> Dict:
        """Collecte toutes les données"""
        result = {'source': 'Sofascore', 'success': False, 'data': {}}
        
        try:
            match = await self.search_match(team1, team2, sport)
            if match:
                result['success'] = True
                result['data']['match'] = match
                
                event_id = match.get('id')
                if event_id:
                    result['data']['details'] = await self.get_match_details(event_id)
                
                home_id = match.get('homeTeam', {}).get('id')
                away_id = match.get('awayTeam', {}).get('id')
                
                if home_id:
                    result['data']['team1_stats'] = await self.get_team_stats(home_id)
                if away_id:
                    result['data']['team2_stats'] = await self.get_team_stats(away_id)
        except Exception as e:
            result['error'] = str(e)
        
        return result

# ════════════════════════════════════════════════════════════════════════════
# 🔍 COLLECTEUR API-FOOTBALL (GRATUIT 100 req/jour)
# ════════════════════════════════════════════════════════════════════════════

class APIFootballCollector:
    """
    Collecte via API-Football - LA MEILLEURE SOURCE DE DONNÉES
    Gratuit: 100 requêtes/jour
    Inscription: https://www.api-football.com/
    """
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.api_key = API_FOOTBALL_KEY
        self.headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }
        self.requests_today = 0
    
    @property
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    async def search_fixture(self, team1: str, team2: str, date: str = None) -> Optional[Dict]:
        """Recherche un match par équipes"""
        if not self.is_available:
            logger.warning("❌ API-Football: Clé non configurée")
            return None
        
        try:
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")
            
            # Chercher aussi demain si pas trouvé aujourd'hui
            dates_to_check = [date]
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            if date != tomorrow:
                dates_to_check.append(tomorrow)
            
            for check_date in dates_to_check:
                url = f"{API_FOOTBALL_URL}/fixtures"
                params = {'date': check_date}
                
                async with self.session.get(url, headers=self.headers, params=params, timeout=15) as r:
                    self.requests_today += 1
                    
                    if r.status == 200:
                        data = await r.json()
                        fixtures = data.get('response', [])
                        
                        # Log du quota restant
                        remaining = r.headers.get('x-ratelimit-requests-remaining', '?')
                        logger.info(f"📊 API-Football: {len(fixtures)} matchs trouvés, quota restant: {remaining}")
                        
                        team1_lower = team1.lower()
                        team2_lower = team2.lower()
                        
                        for fixture in fixtures:
                            home = fixture.get('teams', {}).get('home', {}).get('name', '').lower()
                            away = fixture.get('teams', {}).get('away', {}).get('name', '').lower()
                            
                            # Match flexible
                            if self._match_team(team1_lower, home) and self._match_team(team2_lower, away):
                                logger.info(f"✅ Match trouvé: {fixture.get('teams', {}).get('home', {}).get('name')} vs {fixture.get('teams', {}).get('away', {}).get('name')}")
                                return fixture
                            if self._match_team(team2_lower, home) and self._match_team(team1_lower, away):
                                logger.info(f"✅ Match trouvé: {fixture.get('teams', {}).get('home', {}).get('name')} vs {fixture.get('teams', {}).get('away', {}).get('name')}")
                                return fixture
                    
                    elif r.status == 429:
                        logger.error("❌ API-Football: Quota épuisé (100 req/jour)")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ API-Football search error: {e}")
        return None
    
    def _match_team(self, search: str, target: str) -> bool:
        """Match flexible entre noms d'équipes"""
        if search in target or target in search:
            return True
        # Match par mots
        search_words = set(search.replace('-', ' ').split())
        target_words = set(target.replace('-', ' ').split())
        common = search_words & target_words
        return len(common) >= 1
    
    async def get_fixture_statistics(self, fixture_id: int) -> Dict:
        """Récupère les statistiques détaillées du match"""
        if not self.is_available:
            return {}
        
        try:
            url = f"{API_FOOTBALL_URL}/fixtures/statistics"
            params = {'fixture': fixture_id}
            
            async with self.session.get(url, headers=self.headers, params=params, timeout=10) as r:
                self.requests_today += 1
                if r.status == 200:
                    data = await r.json()
                    return data.get('response', [])
        except Exception as e:
            logger.error(f"API-Football stats error: {e}")
        return []
    
    async def get_fixture_lineups(self, fixture_id: int) -> Dict:
        """Récupère les compositions"""
        if not self.is_available:
            return {}
        
        try:
            url = f"{API_FOOTBALL_URL}/fixtures/lineups"
            params = {'fixture': fixture_id}
            
            async with self.session.get(url, headers=self.headers, params=params, timeout=10) as r:
                self.requests_today += 1
                if r.status == 200:
                    data = await r.json()
                    return data.get('response', [])
        except:
            pass
        return []
    
    async def get_predictions(self, fixture_id: int) -> Dict:
        """Récupère les prédictions officielles API-Football"""
        if not self.is_available:
            return {}
        
        try:
            url = f"{API_FOOTBALL_URL}/predictions"
            params = {'fixture': fixture_id}
            
            async with self.session.get(url, headers=self.headers, params=params, timeout=10) as r:
                self.requests_today += 1
                if r.status == 200:
                    data = await r.json()
                    response = data.get('response', [])
                    return response[0] if response else {}
        except:
            pass
        return {}
    
    async def get_team_statistics(self, team_id: int, league_id: int, season: int = 2024) -> Dict:
        """Récupère les statistiques complètes d'une équipe"""
        if not self.is_available:
            return {}
        
        try:
            url = f"{API_FOOTBALL_URL}/teams/statistics"
            params = {'team': team_id, 'league': league_id, 'season': season}
            
            async with self.session.get(url, headers=self.headers, params=params, timeout=10) as r:
                self.requests_today += 1
                if r.status == 200:
                    data = await r.json()
                    return data.get('response', {})
        except:
            pass
        return {}
    
    async def get_h2h(self, team1_id: int, team2_id: int, last: int = 10) -> List[Dict]:
        """Récupère l'historique des confrontations directes"""
        if not self.is_available:
            return []
        
        try:
            url = f"{API_FOOTBALL_URL}/fixtures/headtohead"
            params = {'h2h': f"{team1_id}-{team2_id}", 'last': last}
            
            async with self.session.get(url, headers=self.headers, params=params, timeout=10) as r:
                self.requests_today += 1
                if r.status == 200:
                    data = await r.json()
                    return data.get('response', [])
        except:
            pass
        return []
    
    async def get_injuries(self, fixture_id: int) -> List[Dict]:
        """Récupère les blessures pour un match"""
        if not self.is_available:
            return []
        
        try:
            url = f"{API_FOOTBALL_URL}/injuries"
            params = {'fixture': fixture_id}
            
            async with self.session.get(url, headers=self.headers, params=params, timeout=10) as r:
                self.requests_today += 1
                if r.status == 200:
                    data = await r.json()
                    return data.get('response', [])
        except:
            pass
        return []
    
    async def collect_all(self, team1: str, team2: str) -> Dict:
        """Collecte TOUTES les données disponibles pour un match"""
        result = {
            'source': 'API-Football',
            'success': False,
            'data': {},
            'requests_used': 0
        }
        
        if not self.is_available:
            result['error'] = "API_FOOTBALL_KEY non configurée. Obtenez une clé gratuite sur https://www.api-football.com/"
            return result
        
        start_requests = self.requests_today
        
        try:
            # 1. Trouver le match
            fixture = await self.search_fixture(team1, team2)
            if not fixture:
                result['error'] = f"Match non trouvé: {team1} vs {team2}"
                return result
            
            result['success'] = True
            result['data']['fixture'] = fixture
            
            fixture_id = fixture.get('fixture', {}).get('id')
            home_team = fixture.get('teams', {}).get('home', {})
            away_team = fixture.get('teams', {}).get('away', {})
            league_id = fixture.get('league', {}).get('id')
            
            # 2. Collecter en parallèle pour économiser les requêtes
            if fixture_id:
                tasks = [
                    self.get_predictions(fixture_id),
                    self.get_fixture_lineups(fixture_id),
                    self.get_injuries(fixture_id)
                ]
                
                predictions, lineups, injuries = await asyncio.gather(*tasks, return_exceptions=True)
                
                if not isinstance(predictions, Exception) and predictions:
                    result['data']['predictions'] = predictions
                
                if not isinstance(lineups, Exception) and lineups:
                    result['data']['lineups'] = lineups
                
                if not isinstance(injuries, Exception) and injuries:
                    result['data']['injuries'] = injuries
            
            # 3. Stats des équipes (si quota suffisant)
            if home_team.get('id') and away_team.get('id') and league_id:
                # H2H
                h2h = await self.get_h2h(home_team['id'], away_team['id'])
                if h2h:
                    result['data']['h2h'] = h2h
                
                # Stats équipe domicile
                team1_stats = await self.get_team_statistics(home_team['id'], league_id)
                if team1_stats:
                    result['data']['team1_stats'] = team1_stats
                
                # Stats équipe extérieur
                team2_stats = await self.get_team_statistics(away_team['id'], league_id)
                if team2_stats:
                    result['data']['team2_stats'] = team2_stats
            
            result['requests_used'] = self.requests_today - start_requests
            logger.info(f"✅ API-Football: {result['requests_used']} requêtes utilisées")
            
        except Exception as e:
            logger.error(f"API-Football collect error: {e}")
            result['error'] = str(e)
        
        return result

# ════════════════════════════════════════════════════════════════════════════
# 🔍 COLLECTEUR DE COTES (GRATUIT 500 req/mois)
# ════════════════════════════════════════════════════════════════════════════

class OddsCollector:
    """
    Collecte les cotes depuis The Odds API
    Gratuit: 500 requêtes/mois
    Inscription: https://the-odds-api.com/
    """
    
    # Mapping des sports
    SPORT_KEYS = {
        'football': [
            'soccer_epl',           # Premier League
            'soccer_france_ligue_one',  # Ligue 1
            'soccer_spain_la_liga',     # La Liga
            'soccer_italy_serie_a',     # Serie A
            'soccer_germany_bundesliga', # Bundesliga
            'soccer_uefa_champs_league', # Champions League
            'soccer_uefa_europa_league', # Europa League
            'soccer_fifa_world_cup',     # World Cup
        ],
        'soccer': ['soccer_epl'],
        'nba': ['basketball_nba'],
        'basketball': ['basketball_nba', 'basketball_euroleague'],
        'nfl': ['americanfootball_nfl'],
        'tennis': ['tennis_atp_aus_open', 'tennis_atp_french_open', 'tennis_atp_wimbledon'],
        'ufc': ['mma_mixed_martial_arts'],
        'mma': ['mma_mixed_martial_arts'],
        'nhl': ['icehockey_nhl'],
        'mlb': ['baseball_mlb']
    }
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.api_key = ODDS_API_KEY
        self.requests_used = 0
    
    @property
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    async def get_sports(self) -> List[Dict]:
        """Liste tous les sports disponibles"""
        if not self.is_available:
            return []
        
        try:
            url = f"{ODDS_API_URL}/sports"
            params = {'apiKey': self.api_key}
            
            async with self.session.get(url, params=params, timeout=10) as r:
                self.requests_used += 1
                if r.status == 200:
                    return await r.json()
        except:
            pass
        return []
    
    async def get_odds(self, team1: str, team2: str, sport: str = 'football') -> Dict:
        """Récupère les cotes pour un match"""
        result = {
            'source': 'The Odds API',
            'success': False,
            'data': {},
            'requests_used': 0
        }
        
        if not self.is_available:
            result['error'] = "ODDS_API_KEY non configurée. Obtenez une clé gratuite sur https://the-odds-api.com/"
            return result
        
        try:
            # Essayer plusieurs clés de sport
            sport_keys = self.SPORT_KEYS.get(sport.lower(), ['soccer_epl'])
            
            for sport_key in sport_keys:
                url = f"{ODDS_API_URL}/sports/{sport_key}/odds"
                params = {
                    'apiKey': self.api_key,
                    'regions': 'eu,uk',
                    'markets': 'h2h,totals,spreads,btts,draw_no_bet',
                    'oddsFormat': 'decimal',
                    'bookmakers': 'bet365,unibet,betfair,pinnacle,williamhill,1xbet'
                }
                
                async with self.session.get(url, params=params, timeout=15) as r:
                    self.requests_used += 1
                    result['requests_used'] += 1
                    
                    # Log du quota restant
                    remaining = r.headers.get('x-requests-remaining', '?')
                    used = r.headers.get('x-requests-used', '?')
                    logger.info(f"💰 Odds API: quota utilisé {used}, restant {remaining}")
                    
                    if r.status == 200:
                        data = await r.json()
                        
                        team1_lower = team1.lower()
                        team2_lower = team2.lower()
                        
                        for event in data:
                            home = event.get('home_team', '').lower()
                            away = event.get('away_team', '').lower()
                            
                            if self._match_team(team1_lower, home) and self._match_team(team2_lower, away):
                                result['success'] = True
                                result['data'] = {
                                    'event': event,
                                    'odds': self._parse_all_odds(event),
                                    'bookmakers': [b['title'] for b in event.get('bookmakers', [])],
                                    'sport_key': sport_key
                                }
                                logger.info(f"✅ Cotes trouvées: {event.get('home_team')} vs {event.get('away_team')}")
                                return result
                            
                            if self._match_team(team2_lower, home) and self._match_team(team1_lower, away):
                                result['success'] = True
                                result['data'] = {
                                    'event': event,
                                    'odds': self._parse_all_odds(event),
                                    'bookmakers': [b['title'] for b in event.get('bookmakers', [])],
                                    'sport_key': sport_key
                                }
                                return result
                    
                    elif r.status == 401:
                        result['error'] = "Clé API invalide"
                        return result
                    elif r.status == 429:
                        result['error'] = "Quota épuisé (500 req/mois)"
                        return result
            
            result['error'] = f"Match non trouvé: {team1} vs {team2}"
            
        except Exception as e:
            logger.error(f"Odds API error: {e}")
            result['error'] = str(e)
        
        return result
    
    def _match_team(self, search: str, target: str) -> bool:
        """Match flexible"""
        if search in target or target in search:
            return True
        search_words = set(search.replace('-', ' ').split())
        target_words = set(target.replace('-', ' ').split())
        return len(search_words & target_words) >= 1
    
    def _parse_all_odds(self, event: Dict) -> Dict:
        """Parse TOUTES les cotes disponibles"""
        odds = {
            'match_winner': {},
            'over_under': {},
            'btts': {},
            'draw_no_bet': {},
            'spreads': {},
            'best_odds': {},
            'implied_probabilities': {}
        }
        
        home_team = event.get('home_team', '')
        away_team = event.get('away_team', '')
        
        # Collecter les meilleures cotes de tous les bookmakers
        best_home = 0
        best_draw = 0
        best_away = 0
        best_over = {}
        best_under = {}
        
        for bookmaker in event.get('bookmakers', []):
            bm_name = bookmaker.get('title', '')
            
            for market in bookmaker.get('markets', []):
                market_key = market.get('key', '')
                
                if market_key == 'h2h':
                    for outcome in market.get('outcomes', []):
                        name = outcome.get('name', '')
                        price = outcome.get('price', 0)
                        
                        if name == home_team:
                            odds['match_winner']['1'] = odds['match_winner'].get('1') or price
                            if price > best_home:
                                best_home = price
                        elif name == away_team:
                            odds['match_winner']['2'] = odds['match_winner'].get('2') or price
                            if price > best_away:
                                best_away = price
                        elif name == 'Draw':
                            odds['match_winner']['X'] = odds['match_winner'].get('X') or price
                            if price > best_draw:
                                best_draw = price
                
                elif market_key == 'totals':
                    for outcome in market.get('outcomes', []):
                        point = outcome.get('point', 2.5)
                        price = outcome.get('price', 0)
                        
                        if outcome.get('name') == 'Over':
                            key = f'over_{point}'
                            odds['over_under'][key] = odds['over_under'].get(key) or price
                            if key not in best_over or price > best_over[key]:
                                best_over[key] = price
                        else:
                            key = f'under_{point}'
                            odds['over_under'][key] = odds['over_under'].get(key) or price
                            if key not in best_under or price > best_under[key]:
                                best_under[key] = price
                
                elif market_key == 'btts':
                    for outcome in market.get('outcomes', []):
                        name = outcome.get('name', '').lower()
                        price = outcome.get('price', 0)
                        if 'yes' in name:
                            odds['btts']['yes'] = odds['btts'].get('yes') or price
                        else:
                            odds['btts']['no'] = odds['btts'].get('no') or price
                
                elif market_key == 'draw_no_bet':
                    for outcome in market.get('outcomes', []):
                        name = outcome.get('name', '')
                        price = outcome.get('price', 0)
                        if name == home_team:
                            odds['draw_no_bet']['1'] = price
                        elif name == away_team:
                            odds['draw_no_bet']['2'] = price
        
        # Meilleures cotes
        odds['best_odds'] = {
            '1': best_home,
            'X': best_draw,
            '2': best_away,
            **{f'over_{k.split("_")[1]}': v for k, v in best_over.items()},
            **{f'under_{k.split("_")[1]}': v for k, v in best_under.items()}
        }
        
        # Calculer les probabilités implicites
        if odds['match_winner']:
            mw = odds['match_winner']
            if all(k in mw for k in ['1', 'X', '2']):
                try:
                    total = sum(1/mw[k] for k in ['1', 'X', '2'])
                    odds['implied_probabilities'] = {
                        '1': round(100 / mw['1'] / total, 1),
                        'X': round(100 / mw['X'] / total, 1),
                        '2': round(100 / mw['2'] / total, 1),
                        'margin': round((total - 1) * 100, 2)
                    }
                except:
                    pass
        
        return odds

# ════════════════════════════════════════════════════════════════════════════
# 🎯 COLLECTEUR PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════

class UltraDataCollector:
    """
    Collecteur principal - agrège TOUTES les sources.
    Formate les données pour que l'IA génère librement ses prédictions.
    """
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.sofascore: Optional[SofascoreCollector] = None
        self.api_football: Optional[APIFootballCollector] = None
        self.odds: Optional[OddsCollector] = None
        self.cache: Dict[str, Tuple[str, float]] = {}
        self.cache_ttl = 1800
    
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=60)
        self.session = aiohttp.ClientSession(timeout=timeout)
        self.sofascore = SofascoreCollector(self.session)
        self.api_football = APIFootballCollector(self.session)
        self.odds = OddsCollector(self.session)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _cache_key(self, team1: str, team2: str) -> str:
        content = f"{team1.lower()}_{team2.lower()}_{datetime.now().strftime('%Y-%m-%d')}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def collect_all_data(self, match: Dict) -> str:
        """Collecte TOUTES les données et retourne un texte pour l'IA"""
        team1 = match.get('team1', '')
        team2 = match.get('team2', '')
        sport = match.get('sport', 'FOOTBALL').lower()
        
        # Extraire du titre si nécessaire
        if not team1 or not team2:
            title = match.get('title', '')
            if ' vs ' in title:
                parts = title.split(' vs ')
                team1 = parts[0].strip()
                team2 = parts[1].strip() if len(parts) > 1 else ''
            elif ' - ' in title:
                parts = title.split(' - ')
                team1 = parts[0].strip()
                team2 = parts[1].strip() if len(parts) > 1 else ''
        
        # Vérifier le cache
        cache_key = self._cache_key(team1, team2)
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                logger.info(f"📦 Cache hit: {team1} vs {team2}")
                return cached_data
        
        logger.info(f"🔍 Collecte: {team1} vs {team2} ({sport})")
        
        # Collecter en parallèle
        tasks = [
            self.sofascore.collect_all(team1, team2, sport),
            self.api_football.collect_all(team1, team2),
            self.odds.get_odds(team1, team2, sport)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        sofascore_data = results[0] if not isinstance(results[0], Exception) else {'success': False}
        api_football_data = results[1] if not isinstance(results[1], Exception) else {'success': False}
        odds_data = results[2] if not isinstance(results[2], Exception) else {'success': False}
        
        # Formater pour l'IA
        formatted = self._format_for_ai(match, team1, team2, sport, sofascore_data, api_football_data, odds_data)
        
        # Mettre en cache
        self.cache[cache_key] = (formatted, time.time())
        
        return formatted
    
    def _format_for_ai(self, match: Dict, team1: str, team2: str, sport: str,
                       sofascore: Dict, api_football: Dict, odds: Dict) -> str:
        """Formate TOUTES les données pour l'IA"""
        
        sources = []
        quality = 0
        
        output = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  📊 DONNÉES COLLECTÉES POUR ANALYSE IA - {datetime.now().strftime('%d/%m/%Y %H:%M')}
╚══════════════════════════════════════════════════════════════════════════════╝

🏟️ MATCH: {team1} vs {team2}
🏆 SPORT: {sport.upper()}
⏰ HEURE: {match.get('start_time', 'N/A')}

"""
        
        # ═══════════════════════════════════════════════════════════════════════
        # API-FOOTBALL (SOURCE PRINCIPALE)
        # ═══════════════════════════════════════════════════════════════════════
        if api_football.get('success'):
            sources.append('API-Football')
            quality += 40
            
            output += """
════════════════════════════════════════════════════════════════════════════════
📊 API-FOOTBALL - Données officielles (source principale)
════════════════════════════════════════════════════════════════════════════════

"""
            data = api_football.get('data', {})
            
            # Fixture info
            fixture = data.get('fixture', {})
            if fixture:
                league = fixture.get('league', {})
                venue = fixture.get('fixture', {}).get('venue', {})
                referee = fixture.get('fixture', {}).get('referee', 'N/A')
                
                output += f"""📋 INFORMATIONS MATCH
• Compétition: {league.get('name', 'N/A')} ({league.get('country', 'N/A')})
• Saison: {league.get('season', 'N/A')}
• Tour: {league.get('round', 'N/A')}
• Stade: {venue.get('name', 'N/A')} (capacité: {venue.get('capacity', 'N/A')})
• Ville: {venue.get('city', 'N/A')}
• Arbitre: {referee}

"""
            
            # Prédictions API-Football
            predictions = data.get('predictions', {})
            if predictions:
                pred = predictions.get('predictions', {})
                teams = predictions.get('teams', {})
                comparison = predictions.get('comparison', {})
                
                output += f"""🔮 PRÉDICTIONS API-FOOTBALL (Officielles)
• Vainqueur prédit: {pred.get('winner', {}).get('name', 'N/A')}
• Conseil: {pred.get('advice', 'N/A')}
• Score prédit: {pred.get('goals', {}).get('home', '?')}-{pred.get('goals', {}).get('away', '?')}
• Pourcentages: Dom {pred.get('percent', {}).get('home', 'N/A')} | Nul {pred.get('percent', {}).get('draw', 'N/A')} | Ext {pred.get('percent', {}).get('away', 'N/A')}

"""
                if comparison:
                    output += f"""📊 COMPARAISON DES ÉQUIPES
• Forme: {comparison.get('form', {}).get('home', 'N/A')}% vs {comparison.get('form', {}).get('away', 'N/A')}%
• Attaque: {comparison.get('att', {}).get('home', 'N/A')}% vs {comparison.get('att', {}).get('away', 'N/A')}%
• Défense: {comparison.get('def', {}).get('home', 'N/A')}% vs {comparison.get('def', {}).get('away', 'N/A')}%
• H2H: {comparison.get('h2h', {}).get('home', 'N/A')}% vs {comparison.get('h2h', {}).get('away', 'N/A')}%
• Buts: {comparison.get('goals', {}).get('home', 'N/A')}% vs {comparison.get('goals', {}).get('away', 'N/A')}%
• Total: {comparison.get('total', {}).get('home', 'N/A')}% vs {comparison.get('total', {}).get('away', 'N/A')}%

"""
            
            # Compositions
            lineups = data.get('lineups', [])
            if lineups:
                output += "👥 COMPOSITIONS OFFICIELLES\n"
                for lineup in lineups:
                    team_name = lineup.get('team', {}).get('name', 'Équipe')
                    formation = lineup.get('formation', 'N/A')
                    coach = lineup.get('coach', {}).get('name', 'N/A')
                    
                    output += f"\n🔷 {team_name} ({formation})\n"
                    output += f"   Coach: {coach}\n"
                    output += "   Titulaires: "
                    
                    starters = lineup.get('startXI', [])
                    player_names = [p.get('player', {}).get('name', '') for p in starters]
                    output += ', '.join(player_names[:11]) + "\n"
                
                output += "\n"
            
            # Blessures
            injuries = data.get('injuries', [])
            if injuries:
                output += "🚑 BLESSURES / ABSENCES\n"
                for inj in injuries[:10]:
                    player = inj.get('player', {}).get('name', 'N/A')
                    team = inj.get('team', {}).get('name', 'N/A')
                    reason = inj.get('player', {}).get('reason', 'N/A')
                    output += f"   • {player} ({team}): {reason}\n"
                output += "\n"
            
            # Stats équipe 1
            team1_stats = data.get('team1_stats', {})
            if team1_stats:
                output += self._format_team_stats(team1_stats, team1)
            
            # Stats équipe 2
            team2_stats = data.get('team2_stats', {})
            if team2_stats:
                output += self._format_team_stats(team2_stats, team2)
            
            # H2H
            h2h = data.get('h2h', [])
            if h2h:
                output += "🔄 HISTORIQUE CONFRONTATIONS DIRECTES (H2H)\n\n"
                
                home_wins = 0
                away_wins = 0
                draws = 0
                home_goals = 0
                away_goals = 0
                
                for match_h2h in h2h[:10]:
                    teams_h2h = match_h2h.get('teams', {})
                    goals = match_h2h.get('goals', {})
                    
                    home_name = teams_h2h.get('home', {}).get('name', 'Home')
                    away_name = teams_h2h.get('away', {}).get('name', 'Away')
                    home_score = goals.get('home', 0) or 0
                    away_score = goals.get('away', 0) or 0
                    
                    home_goals += home_score
                    away_goals += away_score
                    
                    if home_score > away_score:
                        home_wins += 1
                    elif away_score > home_score:
                        away_wins += 1
                    else:
                        draws += 1
                    
                    date = match_h2h.get('fixture', {}).get('date', '')[:10]
                    output += f"   • {date}: {home_name} {home_score}-{away_score} {away_name}\n"
                
                total = len(h2h[:10])
                output += f"""
   📈 Résumé ({total} derniers matchs):
   • Victoires domicile: {home_wins}
   • Nuls: {draws}
   • Victoires extérieur: {away_wins}
   • Buts moyens: {round((home_goals + away_goals) / max(total, 1), 2)}/match

"""
        elif api_football.get('error'):
            output += f"""
⚠️ API-FOOTBALL: {api_football.get('error')}

"""
        
        # ═══════════════════════════════════════════════════════════════════════
        # SOFASCORE
        # ═══════════════════════════════════════════════════════════════════════
        if sofascore.get('success'):
            sources.append('Sofascore')
            quality += 25
            
            output += """
════════════════════════════════════════════════════════════════════════════════
📊 SOFASCORE - Statistiques complémentaires
════════════════════════════════════════════════════════════════════════════════

"""
            data = sofascore.get('data', {})
            
            # Match info
            match_info = data.get('match', {})
            if match_info:
                tournament = match_info.get('tournament', {}).get('name', 'N/A')
                home = match_info.get('homeTeam', {}).get('name', team1)
                away = match_info.get('awayTeam', {}).get('name', team2)
                
                output += f"""📋 MATCH: {home} vs {away}
• Compétition: {tournament}

"""
            
            # Détails
            details = data.get('details', {})
            
            if details.get('statistics'):
                output += "📈 STATISTIQUES DÉTAILLÉES\n"
                output += self._json_to_readable(details['statistics'], max_length=1500)
                output += "\n\n"
            
            if details.get('form'):
                output += "📊 FORME RÉCENTE\n"
                output += self._json_to_readable(details['form'], max_length=800)
                output += "\n\n"
            
            if details.get('h2h'):
                output += "🔄 H2H SOFASCORE\n"
                output += self._json_to_readable(details['h2h'], max_length=1000)
                output += "\n\n"
        
        # ═══════════════════════════════════════════════════════════════════════
        # COTES DES BOOKMAKERS
        # ═══════════════════════════════════════════════════════════════════════
        if odds.get('success'):
            sources.append('Bookmakers')
            quality += 25
            
            output += """
════════════════════════════════════════════════════════════════════════════════
💰 COTES DES BOOKMAKERS (The Odds API)
════════════════════════════════════════════════════════════════════════════════

"""
            data = odds.get('data', {})
            bookmakers = data.get('bookmakers', [])
            output += f"📊 Sources: {', '.join(bookmakers[:5])}\n\n"
            
            parsed_odds = data.get('odds', {})
            
            # Match Winner
            mw = parsed_odds.get('match_winner', {})
            if mw:
                output += f"""🏆 RÉSULTAT DU MATCH (1X2)
• Victoire {team1} (1): {mw.get('1', 'N/A')}
• Match Nul (X): {mw.get('X', 'N/A')}
• Victoire {team2} (2): {mw.get('2', 'N/A')}

"""
            
            # Meilleures cotes
            best = parsed_odds.get('best_odds', {})
            if best and any(best.values()):
                output += f"""⭐ MEILLEURES COTES DU MARCHÉ
• Meilleure cote 1: {best.get('1', 'N/A')}
• Meilleure cote X: {best.get('X', 'N/A')}
• Meilleure cote 2: {best.get('2', 'N/A')}

"""
            
            # Probabilités implicites
            impl = parsed_odds.get('implied_probabilities', {})
            if impl:
                output += f"""💡 PROBABILITÉS IMPLICITES (calculées des cotes)
• Probabilité {team1}: {impl.get('1', 'N/A')}%
• Probabilité Nul: {impl.get('X', 'N/A')}%
• Probabilité {team2}: {impl.get('2', 'N/A')}%
• Marge bookmaker: {impl.get('margin', 'N/A')}%

⚠️ Ces probabilités reflètent l'opinion du marché, pas la réalité.
Si TU estimes une probabilité supérieure → c'est un VALUE BET potentiel.

"""
            
            # Over/Under
            ou = parsed_odds.get('over_under', {})
            if ou:
                output += "⚽ TOTAL BUTS (Over/Under)\n"
                for key in sorted(ou.keys()):
                    label = key.replace('_', ' ').title()
                    output += f"• {label}: {ou[key]}\n"
                output += "\n"
            
            # BTTS
            btts = parsed_odds.get('btts', {})
            if btts:
                output += f"""🎯 BTTS (Les deux équipes marquent)
• Oui: {btts.get('yes', 'N/A')}
• Non: {btts.get('no', 'N/A')}

"""
        elif odds.get('error'):
            output += f"""
⚠️ ODDS API: {odds.get('error')}

"""
        
        # ═══════════════════════════════════════════════════════════════════════
        # RÉSUMÉ
        # ═══════════════════════════════════════════════════════════════════════
        output += f"""
════════════════════════════════════════════════════════════════════════════════
📋 RÉSUMÉ DE LA COLLECTE DE DONNÉES
════════════════════════════════════════════════════════════════════════════════

✅ Sources utilisées: {', '.join(sources) if sources else 'Aucune source externe'}
📊 Score de qualité: {quality}%
⏰ Collecté le: {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}

"""
        
        if not sources:
            output += """
⚠️ ATTENTION: Aucune donnée externe n'a pu être collectée.
L'analyse sera basée uniquement sur les connaissances générales de l'IA.
Raisons possibles:
- APIs non configurées (ajoutez API_FOOTBALL_KEY et/ou ODDS_API_KEY)
- Match non trouvé dans les bases de données
- Quota API épuisé

"""
        
        output += """
════════════════════════════════════════════════════════════════════════════════
🎯 MISSION POUR L'IA - GÉNÈRE TES PROPRES PRÉDICTIONS
════════════════════════════════════════════════════════════════════════════════

Tu as reçu toutes les données disponibles. Maintenant:

1. ANALYSE les statistiques des équipes
2. ÉTUDIE l'historique H2H
3. COMPARE avec les probabilités implicites des bookmakers
4. IDENTIFIE les VALUE BETS (où tu vois une meilleure probabilité)
5. GÉNÈRE tes prédictions pour TOUS les marchés pertinents:
   - Résultat (1X2)
   - Score exact
   - Total buts (Over/Under)
   - BTTS
   - Corners
   - Cartons
   - Fautes
   - Mi-temps
   - Tout autre marché pertinent

IMPORTANT:
- Base-toi UNIQUEMENT sur les données fournies
- Justifie CHAQUE prédiction
- Donne ton niveau de confiance (%)
- Indique si des données manquent

Réponds en JSON valide uniquement.
════════════════════════════════════════════════════════════════════════════════
"""
        
        return output
    
    def _format_team_stats(self, stats: Dict, team_name: str) -> str:
        """Formate les statistiques d'une équipe de manière lisible"""
        output = f"""
📈 STATISTIQUES SAISON - {team_name.upper()}
────────────────────────────────────────

"""
        
        # Forme
        form = stats.get('form', '')
        if form:
            output += f"• Forme récente: {form}\n"
        
        # Fixtures
        fixtures = stats.get('fixtures', {})
        if fixtures:
            played = fixtures.get('played', {})
            wins = fixtures.get('wins', {})
            draws = fixtures.get('draws', {})
            loses = fixtures.get('loses', {})
            
            output += f"""• Matchs joués: {played.get('total', 'N/A')} (Dom: {played.get('home', 'N/A')}, Ext: {played.get('away', 'N/A')})
• Victoires: {wins.get('total', 'N/A')} (Dom: {wins.get('home', 'N/A')}, Ext: {wins.get('away', 'N/A')})
• Nuls: {draws.get('total', 'N/A')} (Dom: {draws.get('home', 'N/A')}, Ext: {draws.get('away', 'N/A')})
• Défaites: {loses.get('total', 'N/A')} (Dom: {loses.get('home', 'N/A')}, Ext: {loses.get('away', 'N/A')})

"""
        
        # Buts
        goals = stats.get('goals', {})
        if goals:
            scored = goals.get('for', {})
            conceded = goals.get('against', {})
            
            output += f"""• Buts marqués: {scored.get('total', {}).get('total', 'N/A')} (Dom: {scored.get('total', {}).get('home', 'N/A')}, Ext: {scored.get('total', {}).get('away', 'N/A')})
• Moyenne buts marqués: {scored.get('average', {}).get('total', 'N/A')}/match
• Buts encaissés: {conceded.get('total', {}).get('total', 'N/A')} (Dom: {conceded.get('total', {}).get('home', 'N/A')}, Ext: {conceded.get('total', {}).get('away', 'N/A')})
• Moyenne buts encaissés: {conceded.get('average', {}).get('total', 'N/A')}/match

"""
        
        # Clean sheets et Failed to score
        clean_sheet = stats.get('clean_sheet', {})
        failed = stats.get('failed_to_score', {})
        if clean_sheet or failed:
            output += f"""• Clean sheets: {clean_sheet.get('total', 'N/A')} (Dom: {clean_sheet.get('home', 'N/A')}, Ext: {clean_sheet.get('away', 'N/A')})
• Matchs sans marquer: {failed.get('total', 'N/A')} (Dom: {failed.get('home', 'N/A')}, Ext: {failed.get('away', 'N/A')})

"""
        
        # Cartons
        cards = stats.get('cards', {})
        if cards:
            yellow = cards.get('yellow', {})
            red = cards.get('red', {})
            
            total_yellow = sum(v.get('total', 0) or 0 for v in yellow.values() if isinstance(v, dict))
            total_red = sum(v.get('total', 0) or 0 for v in red.values() if isinstance(v, dict))
            
            output += f"""• Cartons jaunes total: {total_yellow}
• Cartons rouges total: {total_red}

"""
        
        # Pénaltys
        penalty = stats.get('penalty', {})
        if penalty:
            output += f"""• Pénaltys marqués: {penalty.get('scored', {}).get('total', 'N/A')}/{penalty.get('total', 'N/A')}
• Pénaltys manqués: {penalty.get('missed', {}).get('total', 'N/A')}

"""
        
        return output
    
    def _json_to_readable(self, data: Any, max_length: int = 1500) -> str:
        """Convertit JSON en texte lisible"""
        try:
            text = json.dumps(data, indent=2, ensure_ascii=False)
            if len(text) > max_length:
                text = text[:max_length] + "\n... [tronqué]"
            return text
        except:
            return str(data)[:max_length]

# Alias pour compatibilité
DataCollector = UltraDataCollector
CollectedData = None  # Pour compatibilité

__all__ = ['UltraDataCollector', 'DataCollector', 'SofascoreCollector', 'APIFootballCollector', 'OddsCollector']