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
# 🔍 COLLECTEUR API-FOOTBALL
# ════════════════════════════════════════════════════════════════════════════

class APIFootballCollector:
    """Collecte via API-Football (plus fiable)"""
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.api_key = API_FOOTBALL_KEY
        self.headers = {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }
    
    @property
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    async def search_fixture(self, team1: str, team2: str, date: str = None) -> Optional[Dict]:
        """Recherche des matchs"""
        if not self.is_available:
            return None
        
        try:
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")
            
            url = f"{API_FOOTBALL_URL}/fixtures"
            params = {'date': date}
            
            async with self.session.get(url, headers=self.headers, params=params, timeout=15) as r:
                if r.status == 200:
                    data = await r.json()
                    fixtures = data.get('response', [])
                    
                    team1_lower = team1.lower()
                    team2_lower = team2.lower()
                    
                    for fixture in fixtures:
                        home = fixture.get('teams', {}).get('home', {}).get('name', '').lower()
                        away = fixture.get('teams', {}).get('away', {}).get('name', '').lower()
                        
                        if (team1_lower in home or home in team1_lower) and \
                           (team2_lower in away or away in team2_lower):
                            return fixture
                        if (team2_lower in home or home in team2_lower) and \
                           (team1_lower in away or away in team1_lower):
                            return fixture
        except Exception as e:
            logger.error(f"API-Football search: {e}")
        return None
    
    async def get_fixture_details(self, fixture_id: int) -> Dict:
        """Récupère les détails d'un match"""
        data = {}
        if not self.is_available:
            return data
        
        endpoints = {
            'statistics': '/fixtures/statistics',
            'lineups': '/fixtures/lineups',
            'predictions': '/predictions',
            'events': '/fixtures/events'
        }
        
        for key, endpoint in endpoints.items():
            try:
                url = f"{API_FOOTBALL_URL}{endpoint}"
                params = {'fixture': fixture_id}
                async with self.session.get(url, headers=self.headers, params=params, timeout=10) as r:
                    if r.status == 200:
                        data[key] = (await r.json()).get('response', [])
            except:
                pass
        
        return data
    
    async def get_team_statistics(self, team_id: int, league_id: int, season: int = 2024) -> Dict:
        """Récupère les statistiques d'une équipe"""
        if not self.is_available:
            return {}
        
        try:
            url = f"{API_FOOTBALL_URL}/teams/statistics"
            params = {'team': team_id, 'league': league_id, 'season': season}
            
            async with self.session.get(url, headers=self.headers, params=params, timeout=10) as r:
                if r.status == 200:
                    return (await r.json()).get('response', {})
        except:
            pass
        return {}
    
    async def get_h2h(self, team1_id: int, team2_id: int) -> List[Dict]:
        """Récupère l'historique H2H"""
        if not self.is_available:
            return []
        
        try:
            url = f"{API_FOOTBALL_URL}/fixtures/headtohead"
            params = {'h2h': f"{team1_id}-{team2_id}"}
            
            async with self.session.get(url, headers=self.headers, params=params, timeout=10) as r:
                if r.status == 200:
                    return (await r.json()).get('response', [])
        except:
            pass
        return []
    
    async def collect_all(self, team1: str, team2: str) -> Dict:
        """Collecte toutes les données"""
        result = {'source': 'API-Football', 'success': False, 'data': {}}
        
        if not self.is_available:
            result['error'] = "API_FOOTBALL_KEY non configurée"
            return result
        
        try:
            fixture = await self.search_fixture(team1, team2)
            if fixture:
                result['success'] = True
                result['data']['fixture'] = fixture
                
                fixture_id = fixture.get('fixture', {}).get('id')
                if fixture_id:
                    result['data']['details'] = await self.get_fixture_details(fixture_id)
                
                home_team = fixture.get('teams', {}).get('home', {})
                away_team = fixture.get('teams', {}).get('away', {})
                league_id = fixture.get('league', {}).get('id')
                
                if home_team.get('id') and league_id:
                    result['data']['team1_stats'] = await self.get_team_statistics(home_team['id'], league_id)
                
                if away_team.get('id') and league_id:
                    result['data']['team2_stats'] = await self.get_team_statistics(away_team['id'], league_id)
                
                if home_team.get('id') and away_team.get('id'):
                    result['data']['h2h'] = await self.get_h2h(home_team['id'], away_team['id'])
        except Exception as e:
            result['error'] = str(e)
        
        return result

# ════════════════════════════════════════════════════════════════════════════
# 🔍 COLLECTEUR DE COTES
# ════════════════════════════════════════════════════════════════════════════

class OddsCollector:
    """Collecte les cotes depuis The Odds API"""
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.api_key = ODDS_API_KEY
    
    @property
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    async def get_odds(self, team1: str, team2: str, sport: str = 'football') -> Dict:
        """Récupère les cotes pour un match"""
        result = {'source': 'Odds API', 'success': False, 'data': {}}
        
        if not self.is_available:
            result['error'] = "ODDS_API_KEY non configurée"
            return result
        
        try:
            sport_key = self._get_sport_key(sport)
            url = f"{ODDS_API_URL}/sports/{sport_key}/odds"
            params = {
                'apiKey': self.api_key,
                'regions': 'eu',
                'markets': 'h2h,totals,spreads',
                'oddsFormat': 'decimal'
            }
            
            async with self.session.get(url, params=params, timeout=15) as r:
                if r.status == 200:
                    data = await r.json()
                    
                    team1_lower = team1.lower()
                    team2_lower = team2.lower()
                    
                    for event in data:
                        home = event.get('home_team', '').lower()
                        away = event.get('away_team', '').lower()
                        
                        if (team1_lower in home or home in team1_lower) and \
                           (team2_lower in away or away in team2_lower):
                            result['success'] = True
                            result['data'] = {
                                'event': event,
                                'odds': self._parse_odds(event),
                                'bookmakers': [b['title'] for b in event.get('bookmakers', [])]
                            }
                            break
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def _get_sport_key(self, sport: str) -> str:
        mapping = {
            'football': 'soccer_epl', 'soccer': 'soccer_epl',
            'nba': 'basketball_nba', 'basketball': 'basketball_nba',
            'nfl': 'americanfootball_nfl',
            'tennis': 'tennis_atp_french_open',
            'ufc': 'mma_mixed_martial_arts', 'mma': 'mma_mixed_martial_arts'
        }
        return mapping.get(sport.lower(), 'soccer_epl')
    
    def _parse_odds(self, event: Dict) -> Dict:
        odds = {'match_winner': {}, 'over_under': {}}
        
        for bookmaker in event.get('bookmakers', [])[:1]:
            for market in bookmaker.get('markets', []):
                if market['key'] == 'h2h':
                    for outcome in market['outcomes']:
                        name = outcome['name']
                        price = outcome['price']
                        if name == event['home_team']:
                            odds['match_winner']['1'] = price
                        elif name == event['away_team']:
                            odds['match_winner']['2'] = price
                        elif name == 'Draw':
                            odds['match_winner']['X'] = price
                
                elif market['key'] == 'totals':
                    for outcome in market['outcomes']:
                        point = outcome.get('point', 2.5)
                        key = f"{'over' if outcome['name'] == 'Over' else 'under'}_{point}"
                        odds['over_under'][key] = outcome['price']
        
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
║  📊 DONNÉES COLLECTÉES - {datetime.now().strftime('%d/%m/%Y %H:%M')}
╚══════════════════════════════════════════════════════════════════════════════╝

🏟️ MATCH: {team1} vs {team2}
🏆 SPORT: {sport.upper()}
⏰ HEURE: {match.get('start_time', 'N/A')}

"""
        
        # ═══════════════════════════════════════════════════════════════════════
        # SOFASCORE
        # ═══════════════════════════════════════════════════════════════════════
        if sofascore.get('success'):
            sources.append('Sofascore')
            quality += 35
            
            output += """
════════════════════════════════════════════════════════════════════════════════
📊 SOFASCORE - Statistiques détaillées
════════════════════════════════════════════════════════════════════════════════

"""
            data = sofascore.get('data', {})
            
            # Match info
            match_info = data.get('match', {})
            if match_info:
                tournament = match_info.get('tournament', {}).get('name', 'N/A')
                home = match_info.get('homeTeam', {}).get('name', team1)
                away = match_info.get('awayTeam', {}).get('name', team2)
                
                output += f"""📋 MATCH INFO
• Compétition: {tournament}
• Domicile: {home}
• Extérieur: {away}

"""
            
            # Détails
            details = data.get('details', {})
            
            if details.get('statistics'):
                output += "📈 STATISTIQUES\n"
                output += self._json_to_readable(details['statistics'], max_length=2000)
                output += "\n\n"
            
            if details.get('lineups'):
                output += "👥 COMPOSITIONS\n"
                output += self._json_to_readable(details['lineups'], max_length=1500)
                output += "\n\n"
            
            if details.get('h2h'):
                output += "🔄 CONFRONTATIONS H2H\n"
                output += self._json_to_readable(details['h2h'], max_length=1000)
                output += "\n\n"
            
            if details.get('form'):
                output += "📊 FORME\n"
                output += self._json_to_readable(details['form'], max_length=800)
                output += "\n\n"
            
            if details.get('odds'):
                output += "💰 COTES SOFASCORE\n"
                output += self._json_to_readable(details['odds'], max_length=1000)
                output += "\n\n"
        
        # ═══════════════════════════════════════════════════════════════════════
        # API-FOOTBALL
        # ═══════════════════════════════════════════════════════════════════════
        if api_football.get('success'):
            sources.append('API-Football')
            quality += 35
            
            output += """
════════════════════════════════════════════════════════════════════════════════
📊 API-FOOTBALL - Données officielles
════════════════════════════════════════════════════════════════════════════════

"""
            data = api_football.get('data', {})
            
            fixture = data.get('fixture', {})
            if fixture:
                league = fixture.get('league', {})
                venue = fixture.get('fixture', {}).get('venue', {})
                referee = fixture.get('fixture', {}).get('referee', 'N/A')
                
                output += f"""📋 FIXTURE
• Ligue: {league.get('name', 'N/A')} ({league.get('country', 'N/A')})
• Stade: {venue.get('name', 'N/A')}
• Arbitre: {referee}

"""
            
            details = data.get('details', {})
            
            if details.get('statistics'):
                output += "📊 STATISTIQUES\n"
                output += self._json_to_readable(details['statistics'], max_length=2000)
                output += "\n\n"
            
            if details.get('lineups'):
                output += "👥 COMPOSITIONS\n"
                output += self._json_to_readable(details['lineups'], max_length=1500)
                output += "\n\n"
            
            if details.get('predictions'):
                output += "🔮 PRÉDICTIONS API-FOOTBALL\n"
                output += self._json_to_readable(details['predictions'], max_length=1500)
                output += "\n\n"
            
            if data.get('team1_stats'):
                output += f"📈 STATS SAISON {team1.upper()}\n"
                output += self._json_to_readable(data['team1_stats'], max_length=1500)
                output += "\n\n"
            
            if data.get('team2_stats'):
                output += f"📈 STATS SAISON {team2.upper()}\n"
                output += self._json_to_readable(data['team2_stats'], max_length=1500)
                output += "\n\n"
            
            if data.get('h2h'):
                output += "🔄 H2H\n"
                output += self._json_to_readable(data['h2h'][:5], max_length=1500)
                output += "\n\n"
        
        # ═══════════════════════════════════════════════════════════════════════
        # COTES
        # ═══════════════════════════════════════════════════════════════════════
        if odds.get('success'):
            sources.append('Bookmakers')
            quality += 20
            
            output += """
════════════════════════════════════════════════════════════════════════════════
💰 COTES DES BOOKMAKERS
════════════════════════════════════════════════════════════════════════════════

"""
            data = odds.get('data', {})
            bookmakers = data.get('bookmakers', [])
            output += f"📊 Sources: {', '.join(bookmakers[:3])}\n\n"
            
            odds_parsed = data.get('odds', {})
            
            mw = odds_parsed.get('match_winner', {})
            if mw:
                output += f"""🏆 RÉSULTAT (1X2)
• Victoire {team1}: {mw.get('1', 'N/A')}
• Match Nul: {mw.get('X', 'N/A')}
• Victoire {team2}: {mw.get('2', 'N/A')}

"""
                # Probabilités implicites
                if all(k in mw for k in ['1', 'X', '2']):
                    try:
                        total = sum(1/mw[k] for k in ['1', 'X', '2'])
                        output += f"""💡 PROBABILITÉS IMPLICITES
• {team1}: {round(100/mw['1']/total, 1)}%
• Nul: {round(100/mw['X']/total, 1)}%
• {team2}: {round(100/mw['2']/total, 1)}%
• Marge bookmaker: {round((total-1)*100, 1)}%

"""
                    except:
                        pass
            
            ou = odds_parsed.get('over_under', {})
            if ou:
                output += "⚽ TOTAL BUTS\n"
                for key, value in sorted(ou.items()):
                    output += f"• {key.replace('_', ' ').title()}: {value}\n"
                output += "\n"
        
        # ═══════════════════════════════════════════════════════════════════════
        # RÉSUMÉ
        # ═══════════════════════════════════════════════════════════════════════
        output += f"""
════════════════════════════════════════════════════════════════════════════════
📋 RÉSUMÉ DE COLLECTE
════════════════════════════════════════════════════════════════════════════════

✅ Sources: {', '.join(sources) if sources else 'Aucune'}
📊 Qualité: {quality}%
⏰ Collecté: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

"""
        
        if not sources:
            output += """
⚠️ AUCUNE DONNÉE EXTERNE - L'analyse sera basée sur les connaissances de l'IA.

"""
        
        output += """
════════════════════════════════════════════════════════════════════════════════
🎯 INSTRUCTIONS POUR L'IA
════════════════════════════════════════════════════════════════════════════════

Analyse TOUTES les données et génère TES PROPRES PRÉDICTIONS.

Tu as LIBERTÉ TOTALE sur:
• Les marchés (résultat, buts, corners, cartons, etc.)
• Le format de tes prédictions
• Les probabilités estimées
• Les value bets identifiés

Méthodologie:
1. Analyse les STATISTIQUES (forme, buts marqués/encaissés, cartons, corners)
2. Étudie le H2H (historique des confrontations)
3. Compare avec les COTES (probabilités implicites vs tes estimations)
4. Identifie les VALUE BETS (où tu vois une opportunité)

IMPORTANT:
- Justifie chaque prédiction avec les données
- Donne ton niveau de confiance (%)
- Indique si des données manquent

════════════════════════════════════════════════════════════════════════════════
FIN DES DONNÉES
════════════════════════════════════════════════════════════════════════════════
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