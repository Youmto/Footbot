"""
⚽ FOOTBOT ULTIMATE PRO V2.0 - Bot Telegram Sports Streaming
═══════════════════════════════════════════════════════════════════════════════
Version professionnelle avec:
- Streaming multi-sports VIPRow
- Prédictions IA Ultra-Avancées (Groq)
- Votes communautaires & Gamification
- Classements & Achievements
- Système de favoris intelligent
- Notifications push
═══════════════════════════════════════════════════════════════════════════════
"""
import logging
import os
import sys
import json
import asyncio
import aiohttp
import hashlib
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from telegram.error import TelegramError

# ════════════════════════════════════════════════════════════════════════════
# ⚙️ CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("footbot")

# Chargement du module de prédictions (V4 > V3 > V2)
try:
    from prediction_module import (
        handle_prediction_request,
        handle_vote,
        show_community_votes,
        show_user_prediction_stats,
        show_leaderboard,
        show_prediction_history,
        PredictionsManager,
        AdvancedDataManager,
        PREDICTIONS_ENABLED,
        AI_AVAILABLE,
        SPORTS_CONFIG,
        EventValidator
    )
    mode = "🤖 IA" if AI_AVAILABLE else "📊 Algorithme"
    logger.info(f"✅ Module prédictions V4 ULTRA chargé - Mode: {mode}")
except ImportError as e:
    logger.warning(f"⚠️ Module prédictions V4 non disponible: {e}")
    
    try:
        from prediction_module_v2 import (
            handle_prediction_request,
            handle_vote,
            show_community_votes,
            show_user_prediction_stats,
            show_leaderboard,
            show_prediction_history,
            PredictionsManager,
            AdvancedDataManager,
            PREDICTIONS_ENABLED
        )
        AI_AVAILABLE = False
        SPORTS_CONFIG = None
        EventValidator = None
        logger.info("✅ Module prédictions V2 chargé (fallback)")
    except ImportError as e2:
        PREDICTIONS_ENABLED = False
        AI_AVAILABLE = False
        SPORTS_CONFIG = None
        EventValidator = None
        logger.warning(f"⚠️ Aucun module de prédictions disponible: {e2}")


# Configuration Bot
BOT_TOKEN = os.environ.get("FOOTBOT_TOKEN", "").strip()
ADMIN_IDS = [
    int(x.strip())
    for x in os.environ.get("FOOTBOT_ADMIN_IDS", "5854095196").split(",")
    if x.strip().isdigit()
]
CHANNEL_ID = os.environ.get("FOOTBOT_CHANNEL_ID", "-1002415523895").strip()
REQUIRED_CHANNEL = os.environ.get("FOOTBOT_REQUIRED_CHANNEL", "https://t.me/+mh1Ps_HZdQkzYjk0").strip()

# VIPRow Configuration
VIPROW_BASE = "https://www.viprow.nu"

SPORTS_CONFIGURATION = {
    'football': {'name': 'Football', 'icon': '⚽', 'url': f'{VIPROW_BASE}/sports-football-online', 'popular': True},
    'ufc': {'name': 'UFC', 'icon': '🥊', 'url': f'{VIPROW_BASE}/sports-ufc-online', 'popular': True},
    'boxing': {'name': 'Boxing', 'icon': '🥊', 'url': f'{VIPROW_BASE}/sports-boxing-online', 'popular': True},
    'wwe': {'name': 'WWE', 'icon': '🤼', 'url': f'{VIPROW_BASE}/sports-wwe-online', 'popular': False},
    'tennis': {'name': 'Tennis', 'icon': '🎾', 'url': f'{VIPROW_BASE}/sports-tennis-online', 'popular': True},
    'nfl': {'name': 'NFL', 'icon': '🏈', 'url': f'{VIPROW_BASE}/sports-american-football-online', 'popular': True},
    'nba': {'name': 'NBA', 'icon': '🏀', 'url': f'{VIPROW_BASE}/sports-basketball-online', 'popular': True},
    'nhl': {'name': 'NHL', 'icon': '🏒', 'url': f'{VIPROW_BASE}/sports-ice-hockey-online', 'popular': False},
    'golf': {'name': 'Golf', 'icon': '⛳', 'url': f'{VIPROW_BASE}/sports-golf-online', 'popular': False},
    'darts': {'name': 'Darts', 'icon': '🎯', 'url': f'{VIPROW_BASE}/sports-darts-online', 'popular': False},
    'rugby': {'name': 'Rugby', 'icon': '🏉', 'url': f'{VIPROW_BASE}/sports-rugby-online', 'popular': False},
    'f1': {'name': 'Formula 1', 'icon': '🏎️', 'url': f'{VIPROW_BASE}/sports-formula-1-online', 'popular': True},
    'motogp': {'name': 'MotoGP', 'icon': '🏍️', 'url': f'{VIPROW_BASE}/sports-moto-gp-online', 'popular': False},
    'nascar': {'name': 'NASCAR', 'icon': '🏁', 'url': f'{VIPROW_BASE}/sports-nascar-online', 'popular': False},
    'volleyball': {'name': 'Volleyball', 'icon': '🏐', 'url': f'{VIPROW_BASE}/sports-volleyball-online', 'popular': False},
    'other': {'name': 'Other Sports', 'icon': '🎯', 'url': f'{VIPROW_BASE}/sports-others-online', 'popular': False}
}

# Fichiers de données
DATA_DIR = Path("data/footbot")
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATA_FILE = DATA_DIR / "matches_data.json"
FAVORITES_FILE = DATA_DIR / "favorites_data.json"
USERS_FILE = DATA_DIR / "users_data.json"
CACHE_FILE = DATA_DIR / "stream_cache.json"

# Cache & Performance
CACHE_DURATION = 300  # 5 minutes
MAX_RETRIES = 3
TIMEOUT = 25
REQUEST_DELAY = 0.5
AUTO_UPDATE_INTERVAL = 600  # 10 minutes

# Variables globales
background_tasks: set = set()
shutdown_event: Optional[asyncio.Event] = None

# ════════════════════════════════════════════════════════════════════════════
# 📦 GESTIONNAIRE DE DONNÉES
# ════════════════════════════════════════════════════════════════════════════

class DataManager:
    """Gestionnaire de données centralisé avec cache"""
    
    _data_cache: Optional[Dict] = None
    _users_cache: Optional[Dict] = None
    _favorites_cache: Optional[Dict] = None
    _stream_cache: Optional[Dict] = None
    
    @classmethod
    def load_data(cls) -> Dict:
        """Charge les données des matchs"""
        try:
            if DATA_FILE.exists():
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Vérifier si nouveau jour -> reset
                today = datetime.now().date().isoformat()
                if data.get('last_reset') != today:
                    logger.info(f"🔄 Nouveau jour ({today}), réinitialisation...")
                    return cls._create_fresh_data()
                
                return data
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Erreur chargement données: {e}")
        
        return cls._create_fresh_data()
    
    @classmethod
    def _create_fresh_data(cls) -> Dict:
        """Crée une structure de données vide"""
        data = {
            "matches": [],
            "last_update": None,
            "last_reset": datetime.now().date().isoformat(),
            "total_scraped": 0,
            "sports_count": {},
            "version": "2.0"
        }
        cls.save_data(data)
        return data
    
    @classmethod
    def save_data(cls, data: Dict, trigger_backup: bool = False):
        """Sauvegarde les données"""
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            cls._data_cache = data
            
            if trigger_backup:
                cls._trigger_backup()
                
        except IOError as e:
            logger.error(f"Erreur sauvegarde données: {e}")
    
    @classmethod
    def _trigger_backup(cls):
        """Déclenche un backup vers GitHub Gist"""
        try:
            from backup_manager import backup_manager
            if backup_manager.enabled:
                backup_manager.backup_all_bots()
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"❌ Erreur backup: {e}")
    
    @classmethod
    def load_favorites(cls) -> Dict:
        """Charge les favoris"""
        try:
            if FAVORITES_FILE.exists():
                with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return {}
    
    @classmethod
    def save_favorites(cls, favorites: Dict, trigger_backup: bool = True):
        """Sauvegarde les favoris"""
        try:
            with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
                json.dump(favorites, f, indent=2)
            
            if trigger_backup:
                cls._trigger_backup()
                
        except IOError as e:
            logger.error(f"Erreur sauvegarde favoris: {e}")
    
    @classmethod
    def load_users(cls) -> Dict:
        """Charge les utilisateurs"""
        try:
            if USERS_FILE.exists():
                with open(USERS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return {}
    
    @classmethod
    def save_users(cls, users: Dict):
        """Sauvegarde les utilisateurs"""
        try:
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(users, f, indent=2)
        except IOError as e:
            logger.error(f"Erreur sauvegarde users: {e}")
    
    @classmethod
    def register_user(cls, user_id: int, username: str = None, first_name: str = None) -> Dict:
        """Enregistre ou met à jour un utilisateur"""
        users = cls.load_users()
        user_key = str(user_id)
        
        if user_key not in users:
            users[user_key] = {
                'id': user_id,
                'username': username,
                'first_name': first_name,
                'first_seen': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat(),
                'total_visits': 1,
                'tier': 'free'
            }
            logger.info(f"👤 Nouvel utilisateur: {user_id} ({username or first_name})")
        else:
            users[user_key]['last_seen'] = datetime.now().isoformat()
            users[user_key]['total_visits'] = users[user_key].get('total_visits', 0) + 1
            if username:
                users[user_key]['username'] = username
            if first_name:
                users[user_key]['first_name'] = first_name
        
        cls.save_users(users)
        return users[user_key]
    
    @classmethod
    def load_cache(cls) -> Dict:
        """Charge le cache des streams"""
        try:
            if CACHE_FILE.exists():
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                
                now = time.time()
                return {
                    k: v for k, v in cache.items()
                    if now - v.get('timestamp', 0) < CACHE_DURATION
                }
        except (json.JSONDecodeError, IOError):
            pass
        return {}
    
    @classmethod
    def save_cache(cls, cache: Dict):
        """Sauvegarde le cache"""
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2)
        except IOError as e:
            logger.error(f"Erreur sauvegarde cache: {e}")

# ════════════════════════════════════════════════════════════════════════════
# 🕷️ SCRAPER VIPROW
# ════════════════════════════════════════════════════════════════════════════

class VIPRowScraper:
    """Scraper professionnel pour VIPRow"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache = DataManager.load_cache()
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'failed_requests': 0,
            'streams_found': 0
        }
    
    async def __aenter__(self):
        """Initialise la session HTTP"""
        connector = aiohttp.TCPConnector(
            limit=30,
            limit_per_host=10,
            ssl=False,
            force_close=True
        )
        timeout = aiohttp.ClientTimeout(total=TIMEOUT, connect=10)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ferme la session HTTP"""
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.25)
    
    async def fetch_page(self, url: str, retries: int = MAX_RETRIES) -> Optional[str]:
        """Récupère une page avec retry"""
        self.stats['total_requests'] += 1
        
        for attempt in range(retries):
            try:
                await asyncio.sleep(REQUEST_DELAY)
                
                async with self.session.get(url, ssl=False, allow_redirects=True) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 404:
                        return None
                    else:
                        logger.warning(f"HTTP {response.status}: {url}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout ({attempt+1}/{retries}): {url[:50]}...")
            except aiohttp.ClientError as e:
                logger.warning(f"Client error ({attempt+1}/{retries}): {str(e)[:50]}")
            except Exception as e:
                logger.error(f"Erreur fetch ({attempt+1}/{retries}): {str(e)[:100]}")
            
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)
        
        self.stats['failed_requests'] += 1
        return None
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Nettoie le texte"""
        return re.sub(r'\s+', ' ', text.strip())
    
    @staticmethod
    def extract_match_info(title: str) -> Dict[str, str]:
        """Extrait les informations du match depuis le titre"""
        title = VIPRowScraper.clean_text(title)
        
        time_match = re.search(r'(\d{1,2}:\d{2}(?:\s*(?:AM|PM|am|pm))?)', title)
        match_time = time_match.group(1) if time_match else 'Live'
        
        title_clean = re.sub(r'\d{1,2}:\d{2}(?:\s*(?:AM|PM|am|pm))?', '', title).strip()
        
        team_patterns = [
            r'(.+?)\s+vs\.?\s+(.+)',
            r'(.+?)\s+-\s+(.+)',
            r'(.+?)\s+@\s+(.+)',
            r'(.+?)\s+v\s+(.+)',
        ]
        
        for pattern in team_patterns:
            match = re.search(pattern, title_clean, re.IGNORECASE)
            if match:
                return {
                    'title': title_clean,
                    'team1': VIPRowScraper.clean_text(match.group(1)),
                    'team2': VIPRowScraper.clean_text(match.group(2)),
                    'time': match_time
                }
        
        return {
            'title': title_clean,
            'team1': title_clean,
            'team2': '',
            'time': match_time
        }
    
    async def parse_sport_page(self, html: str, sport_key: str, sport_url: str) -> List[Dict]:
        """Parse une page de sport"""
        soup = BeautifulSoup(html, 'html.parser')
        sport_info = SPORTS_CONFIGURATION[sport_key]
        matches = []
        seen = set()
        
        match_links = soup.find_all('a', href=True)
        
        for link in match_links:
            try:
                href = link.get('href', '').strip()
                if not href or href.startswith('#') or href.startswith('javascript:'):
                    continue
                
                match_url = href if href.startswith('http') else urljoin(sport_url, href)
                
                if not any(x in match_url.lower() for x in ['viprow.nu', 'stream', 'watch', 'live']):
                    continue
                
                if match_url in seen:
                    continue
                
                if any(x in match_url.lower() for x in ['/sports-', 'schedule', 'contact', 'about', 'privacy']):
                    continue
                
                seen.add(match_url)
                
                link_text = link.get_text(strip=True)
                if not link_text or len(link_text) < 5:
                    parent = link.find_parent(['div', 'td', 'li', 'tr', 'span'])
                    if parent:
                        link_text = parent.get_text(strip=True)
                
                if not link_text or len(link_text) < 5:
                    continue
                
                if any(x in link_text.lower() for x in ['menu', 'home', 'schedule', 'contact', 'login']):
                    continue
                
                match_info = self.extract_match_info(link_text)
                
                match_id = hashlib.md5(
                    f"{sport_key}_{match_info['title']}_{datetime.now().date()}".encode()
                ).hexdigest()[:12]
                
                match_data = {
                    'id': match_id,
                    'title': match_info['title'],
                    'team1': match_info['team1'],
                    'team2': match_info['team2'],
                    'sport': sport_key.upper(),
                    'sport_icon': sport_info['icon'],
                    'sport_name': sport_info['name'],
                    'status': 'live',
                    'start_time': match_info['time'],
                    'page_url': match_url,
                    'stream_urls': [],
                    'iframe_url': None,
                    'quality': ['HD'],
                    'scraped_at': datetime.now().isoformat()
                }
                
                matches.append(match_data)
                
            except Exception as e:
                logger.debug(f"Erreur parsing lien: {e}")
                continue
        
        logger.info(f"✅ {sport_info['icon']} {sport_info['name']}: {len(matches)} événements")
        return matches
    
    async def extract_stream_urls(self, match_url: str, match_id: str) -> Tuple[Optional[str], List[str]]:
        """Extrait les URLs de stream"""
        cache_key = f"stream_{match_id}"
        
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached.get('timestamp', 0) < CACHE_DURATION:
                self.stats['cache_hits'] += 1
                return cached.get('iframe'), cached.get('streams', [])
        
        try:
            html = await self.fetch_page(match_url)
            if not html:
                return None, []
            
            soup = BeautifulSoup(html, 'html.parser')
            iframe_url = None
            stream_urls = []
            
            iframes = soup.find_all('iframe', src=True)
            for iframe in iframes:
                src = iframe.get('src', '').strip()
                if src and self._is_valid_stream_url(src):
                    if not src.startswith('http'):
                        src = urljoin(match_url, src)
                    
                    if not iframe_url:
                        iframe_url = src
                    stream_urls.append(src)
            
            self.cache[cache_key] = {
                'iframe': iframe_url,
                'streams': stream_urls,
                'timestamp': time.time()
            }
            DataManager.save_cache(self.cache)
            
            self.stats['streams_found'] += len(stream_urls)
            return iframe_url, stream_urls
            
        except Exception as e:
            logger.error(f"Erreur extraction streams: {e}")
            return None, []
    
    @staticmethod
    def _is_valid_stream_url(url: str) -> bool:
        """Vérifie si l'URL est un stream valide"""
        if not url or len(url) < 10:
            return False
        
        blocked = ['facebook', 'twitter', 'ads', 'doubleclick', 'analytics', 'google']
        if any(block in url.lower() for block in blocked):
            return False
        
        valid = ['embed', 'player', 'stream', 'watch', 'live', '.m3u8', '.mp4']
        return any(v in url.lower() for v in valid)
    
    async def scrape_sport(self, sport_key: str, url: str) -> List[Dict]:
        """Scrape un sport spécifique"""
        html = await self.fetch_page(url)
        if html:
            return await self.parse_sport_page(html, sport_key, url)
        return []
    
    async def scrape_all_sports(self) -> int:
        """Scrape tous les sports"""
        logger.info("🚀 Démarrage scraping multi-sports VIPRow...")
        start = time.time()
        
        tasks = [
            self.scrape_sport(key, config['url'])
            for key, config in SPORTS_CONFIGURATION.items()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_matches = []
        sports_count = {}
        
        for result in results:
            if isinstance(result, list):
                all_matches.extend(result)
                for match in result:
                    sport = match['sport']
                    sports_count[sport] = sports_count.get(sport, 0) + 1
            elif isinstance(result, Exception):
                logger.error(f"Erreur scraping: {result}")
        
        final_matches = list({m['id']: m for m in all_matches}.values())
        
        data = DataManager.load_data()
        data['matches'] = final_matches
        data['last_update'] = datetime.now().isoformat()
        data['total_scraped'] = len(final_matches)
        data['sports_count'] = sports_count
        DataManager.save_data(data)
        
        elapsed = time.time() - start
        logger.info(f"✅ Scraping terminé en {elapsed:.1f}s - {len(final_matches)} événements")
        
        return len(final_matches)

# ════════════════════════════════════════════════════════════════════════════
# 🔐 VÉRIFICATION ABONNEMENT
# ════════════════════════════════════════════════════════════════════════════

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Vérifie si l'utilisateur est abonné au canal"""
    if not CHANNEL_ID:
        return True
    
    try:
        await asyncio.sleep(0.2)
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except TelegramError as e:
        logger.debug(f"Erreur vérification abonnement: {e}")
        return False

# ════════════════════════════════════════════════════════════════════════════
# 🎨 GÉNÉRATEURS D'INTERFACE
# ════════════════════════════════════════════════════════════════════════════

def create_subscription_keyboard() -> InlineKeyboardMarkup:
    """Crée le clavier pour l'abonnement"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Rejoindre le Canal VIP", url=REQUIRED_CHANNEL)],
        [InlineKeyboardButton("✅ J'ai rejoint !", callback_data="check_sub")]
    ])


def create_main_menu_keyboard(sports_count: Dict, user_id: int) -> InlineKeyboardMarkup:
    """Crée le clavier du menu principal avec prédictions IA"""
    keyboard = []
    
    # Section prédictions IA (si disponible)
    if PREDICTIONS_ENABLED:
        keyboard.append([
            InlineKeyboardButton("🔮 Prédictions IA", callback_data="predictions_menu"),
            InlineKeyboardButton("🏆 Classement", callback_data="leaderboard")
        ])
    
    # Sports populaires en premier (2 par ligne)
    popular_sports = [(k, v) for k, v in SPORTS_CONFIGURATION.items() if v.get('popular', False)]
    other_sports = [(k, v) for k, v in SPORTS_CONFIGURATION.items() if not v.get('popular', False)]
    
    # Sports populaires
    for i in range(0, len(popular_sports), 2):
        row = []
        for j in range(2):
            if i + j < len(popular_sports):
                key, config = popular_sports[i + j]
                count = sports_count.get(key.upper(), 0)
                row.append(InlineKeyboardButton(
                    f"{config['icon']} {config['name']} ({count})",
                    callback_data=f"sport_{key}"
                ))
        keyboard.append(row)
    
    # Bouton pour plus de sports
    if other_sports:
        keyboard.append([
            InlineKeyboardButton("📋 Plus de sports...", callback_data="more_sports")
        ])
    
    # Actions utilisateur
    keyboard.append([
        InlineKeyboardButton("⭐ Favoris", callback_data="favorites"),
        InlineKeyboardButton("📊 Stats", callback_data="my_stats")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🔄 Actualiser", callback_data="refresh_all")
    ])
    
    # Admin
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin")])
    
    return InlineKeyboardMarkup(keyboard)


def create_predictions_menu_keyboard() -> InlineKeyboardMarkup:
    """Crée le menu des prédictions"""
    keyboard = [
        [InlineKeyboardButton("🔮 Analyser un Match", callback_data="select_sport_predict")],
        [InlineKeyboardButton("👥 Votes Communauté", callback_data="community_hub")],
        [
            InlineKeyboardButton("📊 Mes Stats", callback_data="my_stats"),
            InlineKeyboardButton("🏆 Classement", callback_data="leaderboard")
        ],
        [InlineKeyboardButton("📜 Historique", callback_data="my_history")],
        [InlineKeyboardButton("🔙 Menu Principal", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ════════════════════════════════════════════════════════════════════════════
# 🤖 COMMANDES UTILISATEUR
# ════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /start"""
    user = update.effective_user
    user_id = user.id
    
    DataManager.register_user(user_id, user.username, user.first_name)
    logger.info(f"👤 {user_id} ({user.username or user.first_name}) => /start")
    
    is_sub = await check_subscription(user_id, context)
    
    if not is_sub:
        predictions_text = ""
        if PREDICTIONS_ENABLED:
            predictions_text = """
🔮 <b>PRÉDICTIONS IA (NOUVEAU!)</b>
  • Résultat du match
  • Score exact
  • Corners, Cartons
  • Paris combinés
  • Votes communautaires
  • Classements & Points
"""
        
        msg = (
            "🏆 <b>VIPROW ULTIMATE PRO V2</b> 🏆\n\n"
            f"👋 Bienvenue <b>{user.first_name}</b> !\n\n"
            "🎯 <b>ACCÈS ILLIMITÉ À TOUS LES SPORTS HD</b>\n\n"
            f"{predictions_text}"
            "⚽ Football • 🥊 UFC/Boxing • 🤼 WWE\n"
            "🏈 NFL • 🏀 NBA • 🏒 NHL • 🎾 Tennis\n"
            "⛳ Golf • 🎯 Darts • 🏉 Rugby\n"
            "🏎️ F1 • 🏍️ MotoGP • 🏁 NASCAR\n\n"
            "✨ <b>FONCTIONNALITÉS:</b>\n\n"
            "📺 Visionnage DIRECT dans Telegram\n"
            "🎬 Streams HD multi-qualité\n"
            "⭐ Système de favoris\n"
            "🔄 MAJ auto toutes les 10 min\n"
            "🚫 ZÉRO pub • ZÉRO redirection\n\n"
            "🔐 Rejoignez le canal pour commencer:"
        )
        
        await update.message.reply_text(
            msg, 
            parse_mode='HTML',
            reply_markup=create_subscription_keyboard()
        )
    else:
        await show_main_menu(update, context)


async def cmd_predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /predict - Accès direct aux prédictions"""
    if not PREDICTIONS_ENABLED:
        await update.message.reply_text(
            "❌ Les prédictions IA ne sont pas disponibles pour le moment.",
            parse_mode='HTML'
        )
        return
    
    await update.message.reply_text(
        "🔮 <b>PRÉDICTIONS IA</b>\n\n"
        "Choisissez une option:",
        parse_mode='HTML',
        reply_markup=create_predictions_menu_keyboard()
    )


async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /leaderboard - Classement"""
    if PREDICTIONS_ENABLED:
        # Créer un faux query pour réutiliser la fonction
        class FakeQuery:
            def __init__(self, message, user):
                self.message = message
                self.from_user = user
            async def answer(self): pass
            async def edit_message_text(self, *args, **kwargs):
                await self.message.reply_text(*args, **kwargs)
        
        fake_query = FakeQuery(update.message, update.effective_user)
        await show_leaderboard(fake_query)
    else:
        await update.message.reply_text("❌ Fonctionnalité non disponible")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /stats - Statistiques utilisateur"""
    if PREDICTIONS_ENABLED:
        class FakeQuery:
            def __init__(self, message, user):
                self.message = message
                self.from_user = user
            async def answer(self): pass
            async def edit_message_text(self, *args, **kwargs):
                await self.message.reply_text(*args, **kwargs)
        
        fake_query = FakeQuery(update.message, update.effective_user)
        await show_user_prediction_stats(fake_query)
    else:
        await update.message.reply_text("❌ Fonctionnalité non disponible")


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche le menu principal"""
    user_id = update.effective_user.id
    data = DataManager.load_data()
    sports_count = data.get('sports_count', {})
    total = len(data.get('matches', []))
    
    last_update = data.get('last_update')
    update_time = datetime.fromisoformat(last_update).strftime("%H:%M:%S") if last_update else "Jamais"
    
    predictions_status = "🟢 Actif" if PREDICTIONS_ENABLED else "🔴 Indisponible"
    
    msg = (
        "🏆 <b>VIPROW ULTIMATE PRO V2</b> 🏆\n\n"
        f"📊 <b>{total} événements en direct</b>\n"
        f"🔄 MAJ: <code>{update_time}</code>\n"
        f"🔮 Prédictions IA: {predictions_status}\n\n"
        "🎯 <b>Choisissez une option:</b>"
    )
    
    keyboard_markup = create_main_menu_keyboard(sports_count, user_id)
    
    if hasattr(update, 'callback_query') and update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                msg, parse_mode='HTML', reply_markup=keyboard_markup
            )
        except Exception:
            await update.callback_query.message.reply_text(
                msg, parse_mode='HTML', reply_markup=keyboard_markup
            )
    else:
        await update.message.reply_text(
            msg, parse_mode='HTML', reply_markup=keyboard_markup
        )

# ════════════════════════════════════════════════════════════════════════════
# 📺 AFFICHAGE MATCHS ET STREAMS
# ════════════════════════════════════════════════════════════════════════════

async def show_predictions_menu(query):
    """Affiche le menu des prédictions"""
    await query.answer()
    
    msg = """╔═══════════════════════════════════════╗
   🔮 <b>PRÉDICTIONS IA</b>
╚═══════════════════════════════════════╝

Bienvenue dans le hub des prédictions !

🤖 <b>Analyse IA Ultra-Avancée</b>
  • Résultat du match (1/X/2)
  • Score exact
  • Total de buts
  • Corners & Cartons
  • Paris combinés

👥 <b>Communauté</b>
  • Votez sur les matchs
  • Comparez avec l'IA
  • Gagnez des points

🏆 <b>Gamification</b>
  • Classement global
  • Achievements à débloquer
  • Séries de victoires

Choisissez une option:"""
    
    await query.edit_message_text(
        msg,
        parse_mode='HTML',
        reply_markup=create_predictions_menu_keyboard()
    )


async def show_sport_for_prediction(query):
    """Affiche les sports pour sélectionner un match à analyser"""
    await query.answer()
    
    data = DataManager.load_data()
    sports_count = data.get('sports_count', {})
    
    keyboard = []
    
    # Sports avec des matchs disponibles
    for key, config in SPORTS_CONFIGURATION.items():
        count = sports_count.get(key.upper(), 0)
        if count > 0:
            keyboard.append([
                InlineKeyboardButton(
                    f"{config['icon']} {config['name']} ({count})",
                    callback_data=f"predict_sport_{key}"
                )
            ])
    
    if not keyboard:
        keyboard.append([
            InlineKeyboardButton("🔄 Actualiser les matchs", callback_data="refresh_all")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data="predictions_menu")])
    
    msg = """🔮 <b>SÉLECTION DU SPORT</b>

Choisissez un sport pour voir les matchs disponibles:"""
    
    await query.edit_message_text(
        msg,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_matches_for_prediction(query, sport_key: str):
    """Affiche les matchs d'un sport pour prédiction"""
    await query.answer()
    
    data = DataManager.load_data()
    matches = [m for m in data.get('matches', []) if m['sport'].lower() == sport_key.lower()]
    
    config = SPORTS_CONFIGURATION.get(sport_key, {'icon': '🎯', 'name': sport_key.upper()})
    
    if not matches:
        keyboard = [
            [InlineKeyboardButton("🔄 Rafraîchir", callback_data=f"predict_sport_{sport_key}")],
            [InlineKeyboardButton("🔙 Retour", callback_data="select_sport_predict")]
        ]
        
        await query.edit_message_text(
            f"{config['icon']} <b>{config['name'].upper()}</b>\n\n"
            "❌ Aucun match disponible pour analyse\n\n"
            "💡 Revenez dans quelques minutes !",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    keyboard = []
    for match in matches[:15]:  # Limite à 15 matchs
        if match['team2']:
            text = f"🔮 {match['team1']} vs {match['team2']}"
        else:
            text = f"🔮 {match['title'][:40]}"
        
        keyboard.append([InlineKeyboardButton(text, callback_data=f"predict_{match['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data="select_sport_predict")])
    
    msg = (
        f"{config['icon']} <b>{config['name'].upper()} - PRÉDICTIONS</b>\n\n"
        f"📊 {len(matches)} match(s) disponible(s)\n\n"
        "👇 Sélectionnez un match pour l'analyse IA:"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_more_sports(query):
    """Affiche les sports supplémentaires"""
    await query.answer()
    
    data = DataManager.load_data()
    sports_count = data.get('sports_count', {})
    
    other_sports = [(k, v) for k, v in SPORTS_CONFIGURATION.items() if not v.get('popular', False)]
    
    keyboard = []
    for i in range(0, len(other_sports), 2):
        row = []
        for j in range(2):
            if i + j < len(other_sports):
                key, config = other_sports[i + j]
                count = sports_count.get(key.upper(), 0)
                row.append(InlineKeyboardButton(
                    f"{config['icon']} {config['name']} ({count})",
                    callback_data=f"sport_{key}"
                ))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Menu Principal", callback_data="main_menu")])
    
    await query.edit_message_text(
        "📋 <b>AUTRES SPORTS</b>\n\n"
        "Sélectionnez un sport:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_sport_matches(query, sport_key: str):
    """Affiche les matchs d'un sport"""
    await query.answer()
    
    data = DataManager.load_data()
    matches = [m for m in data.get('matches', []) if m['sport'].lower() == sport_key.lower()]
    
    config = SPORTS_CONFIGURATION.get(sport_key, {'icon': '🎯', 'name': sport_key.upper()})
    
    if not matches:
        keyboard = [
            [InlineKeyboardButton("🔄 Rafraîchir", callback_data=f"sport_{sport_key}")],
            [InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            f"{config['icon']} <b>{config['name'].upper()}</b>\n\n"
            "❌ Aucun événement en direct\n\n"
            "💡 Revenez dans quelques minutes !",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    favorites = DataManager.load_favorites()
    user_favs = favorites.get(str(query.from_user.id), [])
    
    keyboard = []
    for match in matches[:30]:
        is_fav = match['id'] in user_favs
        icon = "⭐" if is_fav else config['icon']
        
        if match['team2']:
            text = f"{icon} {match['team1']} vs {match['team2']}"
        else:
            text = f"{icon} {match['title'][:50]}"
        
        keyboard.append([InlineKeyboardButton(text, callback_data=f"watch_{match['id']}")])
    
    keyboard.append([
        InlineKeyboardButton("🔄", callback_data=f"sport_{sport_key}"),
        InlineKeyboardButton("🔙 Menu", callback_data="main_menu")
    ])
    
    msg = (
        f"{config['icon']} <b>{config['name'].upper()} - EN DIRECT</b>\n\n"
        f"🎯 <b>{len(matches)}</b> événement(s)\n"
        f"⭐ = Favoris\n\n"
        "👇 Cliquez pour regarder:"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def watch_match(query, match_id: str):
    """Affiche les détails d'un match avec option prédiction"""
    await query.answer("⏳ Chargement...")
    
    data = DataManager.load_data()
    match = next((m for m in data['matches'] if m['id'] == match_id), None)
    
    if not match:
        await query.edit_message_text(
            "❌ Match introuvable",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Menu", callback_data="main_menu")
            ]])
        )
        return
    
    favorites = DataManager.load_favorites()
    user_id = str(query.from_user.id)
    user_favs = favorites.get(user_id, [])
    is_fav = match_id in user_favs
    
    # Extraire les streams si pas encore fait
    if not match.get('stream_urls') and not match.get('iframe_url'):
        await query.edit_message_text(
            "🔍 <b>EXTRACTION DES STREAMS...</b>\n\n"
            "⏳ Analyse en cours...",
            parse_mode='HTML'
        )
        
        async with VIPRowScraper() as scraper:
            iframe, streams = await scraper.extract_stream_urls(match['page_url'], match_id)
            match['iframe_url'] = iframe
            match['stream_urls'] = streams
            
            for i, m in enumerate(data['matches']):
                if m['id'] == match_id:
                    data['matches'][i] = match
                    break
            DataManager.save_data(data)
    
    iframe = match.get('iframe_url')
    streams = match.get('stream_urls', [])
    
    # Construire le clavier
    keyboard = []
    
    # Bouton prédiction IA en premier (si disponible)
    if PREDICTIONS_ENABLED:
        keyboard.append([
            InlineKeyboardButton(
                "🔮 Analyse IA Complète", 
                callback_data=f"predict_{match_id}"
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                "👥 Votes Communauté", 
                callback_data=f"votes_{match_id}"
            )
        ])
    
    # Boutons de lecture
    if iframe:
        keyboard.append([
            InlineKeyboardButton("📺 REGARDER DANS TELEGRAM", callback_data=f"embed_{match_id}")
        ])
    
    if streams:
        if len(streams) > 1:
            keyboard.append([
                InlineKeyboardButton(f"🎬 Alternatives ({len(streams)-1})", callback_data=f"streams_{match_id}")
            ])
        keyboard.append([
            InlineKeyboardButton("🌐 Ouvrir dans Navigateur", url=streams[0])
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("🌐 Page du Match", url=match['page_url'])
        ])
    
    # Favoris et retour
    fav_text = "💔 Retirer des favoris" if is_fav else "⭐ Ajouter aux favoris"
    keyboard.append([InlineKeyboardButton(fav_text, callback_data=f"fav_{match_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data=f"sport_{match['sport'].lower()}")])
    
    # Message
    msg = (
        f"{match['sport_icon']} <b>{match['title']}</b>\n\n"
        f"🏆 {match['sport_name']}\n"
        f"⏰ {match['start_time']}\n"
        f"🔴 <b>EN DIRECT</b>\n\n"
    )
    
    if PREDICTIONS_ENABLED:
        msg += "🔮 <b>NOUVEAU:</b> Obtenez l'analyse IA complète !\n\n"
    
    if iframe:
        msg += (
            "✅ <b>LECTEUR DISPONIBLE</b>\n"
            "📺 Regarder directement dans Telegram\n\n"
        )
    elif streams:
        msg += f"✅ {len(streams)} stream(s) disponible(s)\n\n"
    else:
        msg += "⚠️ Streams en cours d'extraction...\n\n"
    
    msg += "👇 <b>Choisissez une option:</b>"
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def embed_stream(query, match_id: str):
    """Affiche le lecteur intégré"""
    await query.answer("🎬 Chargement du lecteur...")
    
    data = DataManager.load_data()
    match = next((m for m in data['matches'] if m['id'] == match_id), None)
    
    if not match:
        await query.answer("❌ Match introuvable", show_alert=True)
        return
    
    iframe = match.get('iframe_url')
    streams = match.get('stream_urls', [])
    
    if not iframe and not streams:
        await query.answer("⚠️ Aucun stream disponible", show_alert=True)
        return
    
    player_url = iframe if iframe else streams[0]
    
    keyboard = []
    
    if len(streams) > 1:
        keyboard.append([
            InlineKeyboardButton("🔄 Changer de qualité", callback_data=f"streams_{match_id}")
        ])
    
    keyboard.extend([
        [InlineKeyboardButton("🌐 Ouvrir dans Navigateur", url=player_url)],
        [InlineKeyboardButton("♻️ Rafraîchir", callback_data=f"embed_{match_id}")],
        [InlineKeyboardButton("🔙 Retour", callback_data=f"watch_{match_id}")]
    ])
    
    msg = (
        f"📺 <b>LECTEUR STREAM</b>\n\n"
        f"🎯 <b>{match['title']}</b>\n"
        f"{match['sport_icon']} {match['sport_name']} • {match['start_time']}\n\n"
        f"<a href='{player_url}'>▶️ CLIQUER POUR REGARDER</a>\n\n"
        "💡 <b>CONSEILS:</b>\n"
        "📱 Mobile: Mode plein écran\n"
        "💻 PC: F11 pour plein écran\n\n"
        "🚫 <b>SANS PUB • SANS REDIRECT</b>"
    )
    
    try:
        await query.edit_message_text(
            msg, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=False
        )
    except Exception:
        await query.edit_message_text(
            f"📺 <b>STREAM</b>\n\n"
            f"🎯 {match['title']}\n\n"
            f"<a href='{player_url}'>▶️ CLIQUER POUR REGARDER</a>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def show_stream_options(query, match_id: str):
    """Affiche les options de qualité"""
    await query.answer()
    
    data = DataManager.load_data()
    match = next((m for m in data['matches'] if m['id'] == match_id), None)
    
    if not match:
        await query.answer("❌ Match introuvable", show_alert=True)
        return
    
    streams = match.get('stream_urls', [])
    
    if not streams:
        await query.answer("⚠️ Aucun stream disponible", show_alert=True)
        return
    
    keyboard = []
    
    for idx, stream_url in enumerate(streams[:10], 1):
        quality = "HD"
        if 'hd' in stream_url.lower():
            quality = "HD+"
        elif 'sd' in stream_url.lower():
            quality = "SD"
        
        keyboard.append([
            InlineKeyboardButton(f"🎬 Stream {idx} ({quality})", url=stream_url)
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data=f"watch_{match_id}")])
    
    msg = (
        f"{match['sport_icon']} <b>{match['title']}</b>\n\n"
        f"🎬 <b>SÉLECTION QUALITÉ</b>\n\n"
        f"✅ {len(streams)} stream(s) disponible(s)\n\n"
        "💡 Choisissez un stream:"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ════════════════════════════════════════════════════════════════════════════
# ⭐ FAVORIS
# ════════════════════════════════════════════════════════════════════════════

async def toggle_favorite(query, match_id: str):
    """Toggle un match dans les favoris"""
    user_id = str(query.from_user.id)
    
    favorites = DataManager.load_favorites()
    user_favs = favorites.get(user_id, [])
    
    if match_id in user_favs:
        user_favs.remove(match_id)
        await query.answer("💔 Retiré des favoris")
    else:
        user_favs.append(match_id)
        await query.answer("⭐ Ajouté aux favoris !")
    
    favorites[user_id] = user_favs
    DataManager.save_favorites(favorites)
    
    await watch_match(query, match_id)


async def show_favorites(query):
    """Affiche les favoris de l'utilisateur"""
    await query.answer()
    
    user_id = str(query.from_user.id)
    favorites = DataManager.load_favorites()
    user_favs = favorites.get(user_id, [])
    
    if not user_favs:
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]
        await query.edit_message_text(
            "⭐ <b>MES FAVORIS</b>\n\n"
            "❌ Aucun favori\n\n"
            "💡 Ajoutez vos matchs préférés !",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    data = DataManager.load_data()
    fav_matches = [m for m in data['matches'] if m['id'] in user_favs]
    
    if not fav_matches:
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]
        await query.edit_message_text(
            "⭐ <b>MES FAVORIS</b>\n\n"
            "⚠️ Favoris expirés (reset quotidien)\n\n"
            "💡 Ajoutez de nouveaux matchs !",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    keyboard = []
    for match in fav_matches[:25]:
        if match['team2']:
            text = f"⭐ {match['team1']} vs {match['team2']}"
        else:
            text = f"⭐ {match['title'][:45]}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"watch_{match['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Menu", callback_data="main_menu")])
    
    await query.edit_message_text(
        f"⭐ <b>MES FAVORIS</b> ⭐\n\n"
        f"🎯 {len(fav_matches)} match(s)\n\n"
        "👇 Cliquez pour regarder:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ════════════════════════════════════════════════════════════════════════════
# 🔄 ACTUALISATION
# ════════════════════════════════════════════════════════════════════════════

async def refresh_all(query):
    """Actualise tous les matchs"""
    await query.answer("🔄 Actualisation en cours...")
    
    await query.edit_message_text(
        "⏳ <b>ACTUALISATION EN COURS</b>\n\n"
        "🔍 Scan de tous les sports...\n"
        "📡 Extraction des événements...\n\n"
        "⏱️ Estimation: 30-90 secondes",
        parse_mode='HTML'
    )
    
    try:
        async with VIPRowScraper() as scraper:
            count = await scraper.scrape_all_sports()
        
        keyboard = [[InlineKeyboardButton("✅ Voir les Événements", callback_data="main_menu")]]
        
        await query.edit_message_text(
            "✅ <b>ACTUALISATION TERMINÉE !</b>\n\n"
            f"📊 {count} événements trouvés\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}\n\n"
            "🎯 Tous les matchs sont disponibles !",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Erreur refresh: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]
        await query.edit_message_text(
            f"❌ <b>Erreur lors de l'actualisation</b>\n\n"
            f"<code>{str(e)[:100]}</code>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ════════════════════════════════════════════════════════════════════════════
# ⚙️ PANEL ADMIN
# ════════════════════════════════════════════════════════════════════════════

async def admin_panel(query):
    """Panel administrateur"""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Accès refusé", show_alert=True)
        return
    
    await query.answer()
    
    data = DataManager.load_data()
    favorites = DataManager.load_favorites()
    users = DataManager.load_users()
    sports_count = data.get('sports_count', {})
    
    keyboard = [
        [InlineKeyboardButton("🔄 MAJ Complète", callback_data="admin_update")],
        [InlineKeyboardButton("📊 Statistiques Détaillées", callback_data="admin_stats")],
        [InlineKeyboardButton("🗑️ Reset Données", callback_data="admin_reset")],
        [InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]
    ]
    
    total_favs = sum(len(v) for v in favorites.values())
    predictions_status = "✅ Actif" if PREDICTIONS_ENABLED else "❌ Inactif"
    
    msg = (
        "⚙️ <b>PANEL ADMINISTRATEUR</b>\n\n"
        "📊 <b>Statistiques:</b>\n"
        f"• Événements: <code>{len(data['matches'])}</code>\n"
        f"• Sports actifs: <code>{len(sports_count)}</code>\n"
        f"• Utilisateurs: <code>{len(users)}</code>\n"
        f"• Favoris totaux: <code>{total_favs}</code>\n"
        f"• Prédictions IA: {predictions_status}\n"
        f"• Dernière MAJ: <code>{data.get('last_update', 'N/A')[:19]}</code>\n"
        f"• Dernier reset: <code>{data.get('last_reset', 'N/A')}</code>"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_stats(query):
    """Statistiques détaillées admin"""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Accès refusé", show_alert=True)
        return
    
    await query.answer()
    
    data = DataManager.load_data()
    favorites = DataManager.load_favorites()
    users = DataManager.load_users()
    sports_count = data.get('sports_count', {})
    
    total_favs = sum(len(v) for v in favorites.values())
    avg_favs = total_favs / len(favorites) if favorites else 0
    
    msg = "📊 <b>STATISTIQUES DÉTAILLÉES</b>\n\n🎯 <b>Par sport:</b>\n"
    
    for sport, count in sorted(sports_count.items(), key=lambda x: x[1], reverse=True):
        config = SPORTS_CONFIGURATION.get(sport.lower(), {'icon': '🎯', 'name': sport})
        msg += f"• {config['icon']} {config['name']}: {count}\n"
    
    msg += (
        f"\n👥 <b>Utilisateurs:</b>\n"
        f"• Total: <code>{len(users)}</code>\n"
        f"• Favoris totaux: <code>{total_favs}</code>\n"
        f"• Moyenne par user: <code>{avg_favs:.1f}</code>\n\n"
        f"📅 <b>Derniers utilisateurs actifs:</b>\n"
    )
    
    sorted_users = sorted(
        users.values(),
        key=lambda x: x.get('last_seen', ''),
        reverse=True
    )[:5]
    
    for user in sorted_users:
        username = user.get('username', 'N/A')
        first_name = user.get('first_name', 'User')
        visits = user.get('total_visits', 0)
        msg += f"• @{username or first_name} ({visits} visites)\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Admin", callback_data="admin")]]
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_reset(query):
    """Reset des données"""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Accès refusé", show_alert=True)
        return
    
    await query.answer("🗑️ Reset en cours...")
    
    DataManager._create_fresh_data()
    
    keyboard = [[InlineKeyboardButton("✅ OK", callback_data="admin")]]
    await query.edit_message_text(
        "✅ <b>RESET EFFECTUÉ</b>\n\n"
        "🗑️ Toutes les données ont été supprimées\n"
        "📊 Compteurs remis à zéro",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ════════════════════════════════════════════════════════════════════════════
# 🎯 CALLBACK HANDLER PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestionnaire principal des callbacks"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    # Vérification abonnement (sauf admin et check_sub)
    if user_id not in ADMIN_IDS and data != "check_sub":
        is_sub = await check_subscription(user_id, context)
        if not is_sub:
            await query.answer("⚠️ Rejoignez le canal d'abord !", show_alert=True)
            return
    
    # ═══════════════════════════════════════════════════════════════════════
    # NAVIGATION PRINCIPALE
    # ═══════════════════════════════════════════════════════════════════════
    
    if data == "check_sub":
        is_sub = await check_subscription(user_id, context)
        if is_sub:
            await query.answer("✅ Accès autorisé !")
            await show_main_menu(update, context)
        else:
            await query.answer("❌ Vous devez rejoindre le canal", show_alert=True)
    
    elif data == "main_menu":
        await show_main_menu(update, context)
    
    elif data == "more_sports":
        await show_more_sports(query)
    
    elif data == "favorites":
        await show_favorites(query)
    
    elif data == "refresh_all":
        await refresh_all(query)
    
    # ═══════════════════════════════════════════════════════════════════════
    # PRÉDICTIONS IA (si disponible)
    # ═══════════════════════════════════════════════════════════════════════
    
    elif data == "predictions_menu" and PREDICTIONS_ENABLED:
        await show_predictions_menu(query)
    
    elif data == "select_sport_predict" and PREDICTIONS_ENABLED:
        await show_sport_for_prediction(query)
    
    elif data.startswith("predict_sport_") and PREDICTIONS_ENABLED:
        sport = data.split("_", 2)[2]
        await show_matches_for_prediction(query, sport)
    
    elif data.startswith("predict_") and PREDICTIONS_ENABLED:
        match_id = data.split("_", 1)[1]
        await handle_prediction_request(query, match_id, DataManager)
    
    elif data.startswith("vote_") and PREDICTIONS_ENABLED:
        parts = data.split("_")
        if len(parts) == 3:
            match_id = parts[1]
            vote = parts[2]
            await handle_vote(query, match_id, vote, DataManager)
    
    elif data.startswith("votes_") and PREDICTIONS_ENABLED:
        match_id = data.split("_", 1)[1]
        await show_community_votes(query, match_id, DataManager)
    
    elif data == "my_stats" and PREDICTIONS_ENABLED:
        await show_user_prediction_stats(query)
    
    elif data == "leaderboard" and PREDICTIONS_ENABLED:
        await show_leaderboard(query)
    
    elif data == "my_history" and PREDICTIONS_ENABLED:
        await show_prediction_history(query)
    
    elif data == "community_hub" and PREDICTIONS_ENABLED:
        await show_sport_for_prediction(query)
    
    # ═══════════════════════════════════════════════════════════════════════
    # SPORTS & MATCHS
    # ═══════════════════════════════════════════════════════════════════════
    
    elif data.startswith("sport_"):
        sport = data.split("_", 1)[1]
        await show_sport_matches(query, sport)
    
    elif data.startswith("watch_"):
        match_id = data.split("_", 1)[1]
        await watch_match(query, match_id)
    
    elif data.startswith("embed_"):
        match_id = data.split("_", 1)[1]
        await embed_stream(query, match_id)
    
    elif data.startswith("streams_"):
        match_id = data.split("_", 1)[1]
        await show_stream_options(query, match_id)
    
    elif data.startswith("fav_"):
        match_id = data.split("_", 1)[1]
        await toggle_favorite(query, match_id)
    
    # ═══════════════════════════════════════════════════════════════════════
    # ADMIN
    # ═══════════════════════════════════════════════════════════════════════
    
    elif data == "admin":
        await admin_panel(query)
    
    elif data == "admin_update":
        await refresh_all(query)
    
    elif data == "admin_stats":
        await admin_stats(query)
    
    elif data == "admin_reset":
        await admin_reset(query)
    
    # ═══════════════════════════════════════════════════════════════════════
    # FALLBACK
    # ═══════════════════════════════════════════════════════════════════════
    
    else:
        await query.answer("❓ Action non reconnue")

# ════════════════════════════════════════════════════════════════════════════
# 🔄 TÂCHES DE FOND
# ════════════════════════════════════════════════════════════════════════════

async def auto_update_task():
    """Tâche de mise à jour automatique"""
    global shutdown_event
    
    await asyncio.sleep(60)
    
    logger.info("🔄 Tâche auto-update démarrée")
    
    while True:
        try:
            if shutdown_event and shutdown_event.is_set():
                break
            
            logger.info("🔄 Exécution MAJ automatique...")
            async with VIPRowScraper() as scraper:
                count = await scraper.scrape_all_sports()
            logger.info(f"✅ MAJ auto terminée: {count} événements")
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Erreur auto-update: {e}")
        
        try:
            if shutdown_event:
                await asyncio.wait_for(shutdown_event.wait(), timeout=AUTO_UPDATE_INTERVAL)
                break
            else:
                await asyncio.sleep(AUTO_UPDATE_INTERVAL)
        except asyncio.TimeoutError:
            continue


async def daily_reset_task():
    """Tâche de reset quotidien à minuit"""
    global shutdown_event
    
    logger.info("🌙 Tâche daily-reset démarrée")
    
    while True:
        try:
            now = datetime.now()
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            seconds_until_midnight = (tomorrow - now).total_seconds()
            
            logger.info(f"⏰ Prochain reset dans {seconds_until_midnight/3600:.1f}h")
            
            if shutdown_event:
                try:
                    await asyncio.wait_for(shutdown_event.wait(), timeout=seconds_until_midnight)
                    break
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(seconds_until_midnight)
            
            if shutdown_event and shutdown_event.is_set():
                break
            
            logger.info("🌙 Exécution reset quotidien...")
            DataManager._create_fresh_data()
            logger.info("✅ Reset quotidien terminé")
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Erreur daily-reset: {e}")
            await asyncio.sleep(3600)

# ════════════════════════════════════════════════════════════════════════════
# 🚀 POINTS D'ENTRÉE
# ════════════════════════════════════════════════════════════════════════════

def main():
    """Point d'entrée principal"""
    logger.info("=" * 70)
    logger.info("⚽ FOOTBOT VIPROW ULTIMATE PRO V2 - DÉMARRAGE")
    logger.info("=" * 70)
    
    if not BOT_TOKEN or len(BOT_TOKEN) < 20:
        logger.error("❌ FOOTBOT_TOKEN invalide ou manquant!")
        return
    
    logger.info(f"👮 Admins: {ADMIN_IDS}")
    logger.info(f"📢 Canal requis: {REQUIRED_CHANNEL}")
    
    # Afficher le mode de prédiction
    if PREDICTIONS_ENABLED:
        if AI_AVAILABLE:
            logger.info("🔮 Prédictions: ✅ MODE IA (Groq)")
        else:
            logger.info("🔮 Prédictions: ⚠️ MODE ALGORITHME (sans clé API)")
    else:
        logger.info("🔮 Prédictions: ❌ Désactivé")
    
    # Créer l'application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers de commandes
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("predict", cmd_predict))
    application.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    application.add_handler(CommandHandler("stats", cmd_stats))
    
    # Handler de callbacks
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    logger.info("✅ Handlers configurés")
    logger.info("")
    logger.info("🌐 SPORTS DISPONIBLES:")
    for key, config in SPORTS_CONFIGURATION.items():
        popular = "⭐" if config.get('popular') else ""
        logger.info(f"   {config['icon']} {config['name']} {popular}")
    logger.info("")
    logger.info("🚀 Démarrage du polling...")
    
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            close_loop=False,
            stop_signals=None
        )
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        raise
    finally:
        logger.info("👋 FootBot arrêté")


async def main_async():
    """Version async du point d'entrée"""
    global shutdown_event, background_tasks
    
    logger.info("=" * 70)
    logger.info("⚽ FOOTBOT VIPROW ULTIMATE PRO V2 - DÉMARRAGE (Async)")
    logger.info("=" * 70)
    
    if not BOT_TOKEN or len(BOT_TOKEN) < 20:
        logger.error("❌ FOOTBOT_TOKEN invalide ou manquant!")
        return
    
    logger.info(f"👮 Admins: {ADMIN_IDS}")
    logger.info(f"📢 Canal requis: {REQUIRED_CHANNEL}")
    logger.info(f"🔮 Prédictions IA: {'✅ Activé' if PREDICTIONS_ENABLED else '❌ Désactivé'}")
    
    shutdown_event = asyncio.Event()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("predict", cmd_predict))
    application.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    logger.info("✅ Handlers configurés")
    
    async with application:
        await application.start()
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
        logger.info("✅ FootBot V2 actif et en écoute")
        
        # Tâches de fond
        task_update = asyncio.create_task(auto_update_task(), name="footbot_auto_update")
        task_reset = asyncio.create_task(daily_reset_task(), name="footbot_daily_reset")
        
        background_tasks.add(task_update)
        background_tasks.add(task_reset)
        
        task_update.add_done_callback(background_tasks.discard)
        task_reset.add_done_callback(background_tasks.discard)
        
        logger.info("🔄 Tâches de fond démarrées")
        
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("⏹️ Arrêt demandé")
        finally:
            shutdown_event.set()
            
            for task in background_tasks:
                if not task.done():
                    task.cancel()
            
            if background_tasks:
                await asyncio.gather(*background_tasks, return_exceptions=True)
            
            await application.updater.stop()
            await application.stop()
            
            logger.info("👋 FootBot V2 arrêté proprement")


if __name__ == '__main__':
    main()