import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import TelegramError
import json
import os
from datetime import datetime, timedelta
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import hashlib
from typing import List, Dict, Optional, Tuple
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ============================================================================
# ⚙️ CONFIGURATION
# ============================================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Configuration
BOT_TOKEN = "8528649034:AAFCz7vV3-YDPq0UVlgkBws-5zG8EQ13vCs"
ADMIN_IDS = [5854095196]
CHANNEL_ID = -1002415523895
REQUIRED_CHANNEL = "https://t.me/+mh1Ps_HZdQkzYjk0"

# VIPRow Configuration
VIPROW_BASE = "https://www.viprow.nu"

SPORTS_CONFIGURATION = {
    'football': {
        'name': 'Football',
        'icon': '⚽',
        'url': 'https://www.viprow.nu/sports-football-online',
    },
    'ufc': {
        'name': 'UFC',
        'icon': '🥊',
        'url': 'https://www.viprow.nu/sports-ufc-online',
    },
    'boxing': {
        'name': 'Boxing',
        'icon': '🥊',
        'url': 'https://www.viprow.nu/sports-boxing-online',
    },
    'wwe': {
        'name': 'WWE',
        'icon': '🤼',
        'url': 'https://www.viprow.nu/sports-wwe-online',
    },
    'tennis': {
        'name': 'Tennis',
        'icon': '🎾',
        'url': 'https://www.viprow.nu/sports-tennis-online',
    },
    'nfl': {
        'name': 'NFL',
        'icon': '🏈',
        'url': 'https://www.viprow.nu/sports-american-football-online',
    },
    'nba': {
        'name': 'NBA',
        'icon': '🏀',
        'url': 'https://www.viprow.nu/sports-basketball-online',
    },
    'nhl': {
        'name': 'NHL',
        'icon': '🏒',
        'url': 'https://www.viprow.nu/sports-ice-hockey-online',
    },
    'golf': {
        'name': 'Golf',
        'icon': '⛳',
        'url': 'https://www.viprow.nu/sports-golf-online',
    },
    'darts': {
        'name': 'Darts',
        'icon': '🎯',
        'url': 'https://www.viprow.nu/sports-darts-online',
    },
    'rugby': {
        'name': 'Rugby',
        'icon': '🏉',
        'url': 'https://www.viprow.nu/sports-rugby-online',
    },
    'f1': {
        'name': 'Formula 1',
        'icon': '🏎️',
        'url': 'https://www.viprow.nu/sports-formula-1-online',
    },
    'motogp': {
        'name': 'MotoGP',
        'icon': '🏍️',
        'url': 'https://www.viprow.nu/sports-moto-gp-online',
    },
    'nascar': {
        'name': 'NASCAR',
        'icon': '🏁',
        'url': 'https://www.viprow.nu/sports-nascar-online',
    },
    'volleyball': {
        'name': 'Volleyball',
        'icon': '🏐',
        'url': 'https://www.viprow.nu/sports-volleyball-online',
    },
    'other': {
        'name': 'Other Sports',
        'icon': '🎯',
        'url': 'https://www.viprow.nu/sports-others-online',
    }
}

# Files
DATA_FILE = "matches_data.json"
FAVORITES_FILE = "favorites_data.json"
USERS_FILE = "users_data.json"
CACHE_FILE = "stream_cache.json"

# Cache & Performance
CACHE_DURATION = 300
MAX_RETRIES = 3
TIMEOUT = 25
REQUEST_DELAY = 0.5

# ============================================================================
# 📦 DATA MANAGER
# ============================================================================

class DataManager:
    """Gestionnaire de données centralisé"""
    
    @staticmethod
    def load_data() -> Dict:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                today = datetime.now().date().isoformat()
                if data.get('last_reset') != today:
                    logger.info(f"🔄 Nouveau jour ({today}), réinitialisation...")
                    return DataManager._create_fresh_data()
                return data
            except Exception as e:
                logger.error(f"❌ Erreur chargement: {e}")
                return DataManager._create_fresh_data()
        return DataManager._create_fresh_data()
    
    @staticmethod
    def _create_fresh_data() -> Dict:
        data = {
            "matches": [],
            "last_update": None,
            "last_reset": datetime.now().date().isoformat(),
            "total_scraped": 0,
            "sports_count": {}
        }
        DataManager.save_data(data)
        return data
    
    @staticmethod
    def save_data(data: Dict):
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde: {e}")
    
    @staticmethod
    def load_favorites() -> Dict:
        if os.path.exists(FAVORITES_FILE):
            try:
                with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    @staticmethod
    def save_favorites(favorites: Dict):
        try:
            with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
                json.dump(favorites, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde favoris: {e}")
    
    @staticmethod
    def load_users() -> Dict:
        """Charge les données utilisateurs"""
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    @staticmethod
    def save_users(users: Dict):
        """Sauvegarde les données utilisateurs"""
        try:
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(users, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde users: {e}")
    
    @staticmethod
    def register_user(user_id: int, username: str = None, first_name: str = None):
        """Enregistre ou met à jour un utilisateur"""
        users = DataManager.load_users()
        user_key = str(user_id)
        
        if user_key not in users:
            users[user_key] = {
                'id': user_id,
                'username': username,
                'first_name': first_name,
                'first_seen': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat(),
                'total_visits': 1
            }
            logger.info(f"👤 Nouvel utilisateur: {user_id} ({username or first_name})")
        else:
            users[user_key]['last_seen'] = datetime.now().isoformat()
            users[user_key]['total_visits'] = users[user_key].get('total_visits', 0) + 1
            if username:
                users[user_key]['username'] = username
            if first_name:
                users[user_key]['first_name'] = first_name
        
        DataManager.save_users(users)
        return users[user_key]
    
    @staticmethod
    def load_cache() -> Dict:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                now = time.time()
                return {k: v for k, v in cache.items() 
                       if now - v.get('timestamp', 0) < CACHE_DURATION}
            except:
                return {}
        return {}
    
    @staticmethod
    def save_cache(cache: Dict):
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Erreur cache: {e}")

# ============================================================================
# 🕷️ VIPROW ULTRA SCRAPER PRO
# ============================================================================

class VIPRowUltraScraper:
    """Scraper professionnel avec extraction directe des iframes"""
    
    def __init__(self):
        self.session = None
        self.cache = DataManager.load_cache()
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'failed_requests': 0,
            'streams_found': 0
        }
    
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=30,
            limit_per_host=10,
            ssl=False,
            force_close=True
        )
        timeout = aiohttp.ClientTimeout(total=TIMEOUT, connect=10)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
        }
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.5)
    
    async def fetch_page(self, url: str, retries: int = MAX_RETRIES) -> Optional[str]:
        """Récupération robuste avec retry"""
        self.stats['total_requests'] += 1
        
        for attempt in range(retries):
            try:
                await asyncio.sleep(REQUEST_DELAY)
                
                async with self.session.get(url, ssl=False, allow_redirects=True) as response:
                    if response.status == 200:
                        html = await response.text()
                        return html
                    elif response.status == 404:
                        logger.warning(f"⚠️ 404: {url}")
                        return None
                        
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Timeout ({attempt+1}/{retries})")
            except Exception as e:
                logger.error(f"❌ Erreur ({attempt+1}/{retries}): {str(e)[:100]}")
            
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)
        
        self.stats['failed_requests'] += 1
        return None
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Nettoie le texte"""
        text = re.sub(r'\s+', ' ', text.strip())
        return text
    
    @staticmethod
    def extract_match_info(title: str) -> Dict[str, str]:
        """Extrait équipes et heure du titre"""
        title = VIPRowUltraScraper.clean_text(title)
        
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
                    'team1': VIPRowUltraScraper.clean_text(match.group(1)),
                    'team2': VIPRowUltraScraper.clean_text(match.group(2)),
                    'time': match_time
                }
        
        return {
            'title': title_clean,
            'team1': title_clean,
            'team2': '',
            'time': match_time
        }
    
    async def parse_sport_page(self, html: str, sport_key: str, sport_url: str) -> List[Dict]:
        """Parse la page sport VIPRow"""
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
                
                if href.startswith('http'):
                    match_url = href
                else:
                    match_url = urljoin(sport_url, href)
                
                if not any(x in match_url.lower() for x in ['viprow.nu', 'stream', 'watch', 'live']):
                    continue
                
                if match_url in seen:
                    continue
                
                if any(x in match_url.lower() for x in ['/sports-', 'schedule', 'contact', 'about']):
                    continue
                
                seen.add(match_url)
                
                link_text = link.get_text(strip=True)
                
                if not link_text or len(link_text) < 5:
                    parent = link.find_parent(['div', 'td', 'li', 'tr', 'span'])
                    if parent:
                        link_text = parent.get_text(strip=True)
                
                if not link_text or len(link_text) < 5:
                    continue
                
                if any(x in link_text.lower() for x in ['menu', 'home', 'schedule', 'contact']):
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
                continue
        
        logger.info(f"✅ {sport_info['name']}: {len(matches)} événements")
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
            logger.error(f"❌ Erreur extraction streams: {e}")
            return None, []
    
    @staticmethod
    def _is_valid_stream_url(url: str) -> bool:
        """Vérifie si URL est valide"""
        if not url or len(url) < 10:
            return False
        
        blocked = ['facebook', 'twitter', 'ads', 'doubleclick', 'analytics']
        url_lower = url.lower()
        if any(block in url_lower for block in blocked):
            return False
        
        valid = ['embed', 'player', 'stream', 'watch', 'live', '.m3u8', '.mp4']
        return any(v in url_lower for v in valid)
    
    async def scrape_all_sports(self) -> int:
        """Scrape TOUS les sports"""
        logger.info("🚀 Scraping multi-sports VIPRow...")
        start = time.time()
        
        tasks = []
        for sport_key, config in SPORTS_CONFIGURATION.items():
            tasks.append(self.scrape_sport(sport_key, config['url']))
        
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
                logger.error(f"❌ Erreur: {result}")
        
        unique = {m['id']: m for m in all_matches}
        final_matches = list(unique.values())
        
        data = DataManager.load_data()
        data['matches'] = final_matches
        data['last_update'] = datetime.now().isoformat()
        data['total_scraped'] = len(final_matches)
        data['sports_count'] = sports_count
        DataManager.save_data(data)
        
        elapsed = time.time() - start
        
        logger.info("=" * 60)
        logger.info(f"✅ SCRAPING TERMINÉ en {elapsed:.1f}s")
        logger.info(f"📊 {len(final_matches)} événements détectés")
        logger.info("=" * 60)
        
        return len(final_matches)
    
    async def scrape_sport(self, sport_key: str, url: str) -> List[Dict]:
        """Scrape un sport"""
        config = SPORTS_CONFIGURATION[sport_key]
        logger.info(f"📡 Scraping {config['name']}")
        
        html = await self.fetch_page(url)
        if not html:
            return []
        
        matches = await self.parse_sport_page(html, sport_key, url)
        return matches

# ============================================================================
# 🤖 TELEGRAM HANDLERS
# ============================================================================

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Vérifie l'abonnement"""
    try:
        await asyncio.sleep(0.3)
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except TelegramError as e:
        logger.error(f"❌ Check subscription: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /start"""
    user = update.effective_user
    user_id = user.id
    
    # Enregistrer l'utilisateur
    DataManager.register_user(user_id, user.username, user.first_name)
    
    logger.info(f"👤 {user_id} ({user.username or user.first_name}) => /start")
    
    is_sub = await check_subscription(user_id, context)
    
    if not is_sub:
        keyboard = [
            [InlineKeyboardButton("🔥 Rejoindre le Canal VIP", url=REQUIRED_CHANNEL)],
            [InlineKeyboardButton("✅ J'ai rejoint !", callback_data="check_sub")]
        ]
        
        msg = (
            "🏆 <b>VIPROW ULTIMATE PRO</b> 🏆\n\n"
            f"👋 Bienvenue <b>{user.first_name}</b> !\n\n"
            "🎯 <b>ACCÈS ILLIMITÉ À TOUS LES SPORTS HD</b>\n\n"
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
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu principal"""
    data = DataManager.load_data()
    sports_count = data.get('sports_count', {})
    total = len(data.get('matches', []))
    user_id = update.effective_user.id
    
    # Enregistrer la visite
    DataManager.register_user(user_id, update.effective_user.username, update.effective_user.first_name)
    
    keyboard = []
    
    sports_items = list(SPORTS_CONFIGURATION.items())
    for i in range(0, len(sports_items), 2):
        row = []
        for j in range(2):
            if i + j < len(sports_items):
                key, config = sports_items[i + j]
                count = sports_count.get(key.upper(), 0)
                row.append(InlineKeyboardButton(
                    f"{config['icon']} {config['name']} ({count})",
                    callback_data=f"sport_{key}"
                ))
        keyboard.append(row)
    
    keyboard.extend([
        [InlineKeyboardButton("⭐ Mes Favoris", callback_data="favorites")],
        [InlineKeyboardButton("🔄 Actualiser Tout", callback_data="refresh_all")]
    ])
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ Admin", callback_data="admin")])
    
    last_update = data.get('last_update')
    update_time = datetime.fromisoformat(last_update).strftime("%H:%M:%S") if last_update else "Jamais"
    
    msg = (
        "🏆 <b>VIPROW ULTIMATE PRO</b> 🏆\n\n"
        f"📊 <b>{total} événements en direct</b>\n"
        f"🔄 MAJ: <code>{update_time}</code>\n"
        f"📅 Reset: <b>Quotidien à minuit</b>\n\n"
        "🎯 <b>Sélectionnez votre sport:</b>"
    )
    
    if hasattr(update, 'callback_query') and update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                msg, parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.callback_query.message.reply_text(
                msg, parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    else:
        await update.message.reply_text(
            msg, parse_mode='HTML',
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
    """Options de visionnage"""
    await query.answer("⏳ Chargement...")
    
    data = DataManager.load_data()
    match = next((m for m in data['matches'] if m['id'] == match_id), None)
    
    if not match:
        await query.edit_message_text("❌ Match introuvable", parse_mode='HTML')
        return
    
    favorites = DataManager.load_favorites()
    user_id = str(query.from_user.id)
    user_favs = favorites.get(user_id, [])
    is_fav = match_id in user_favs
    
    if not match.get('stream_urls') or not match.get('iframe_url'):
        await query.edit_message_text(
            "🔍 <b>EXTRACTION DES STREAMS...</b>\n\n"
            "⏳ Analyse en cours...\n"
            "📡 Détection des lecteurs...",
            parse_mode='HTML'
        )
        
        async with VIPRowUltraScraper() as scraper:
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
    
    keyboard = []
    
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
            InlineKeyboardButton("🌐 Navigateur", url=streams[0])
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("🌐 Page Match", url=match['page_url'])
        ])
    
    fav_text = "💔 Retirer" if is_fav else "⭐ Favoris"
    keyboard.append([InlineKeyboardButton(fav_text, callback_data=f"fav_{match_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data=f"sport_{match['sport'].lower()}")])
    
    msg = (
        f"{match['sport_icon']} <b>{match['title']}</b>\n\n"
        f"🏆 {match['sport_name']}\n"
        f"⏰ {match['start_time']}\n"
        f"🔴 <b>EN DIRECT</b>\n\n"
    )
    
    if iframe:
        msg += (
            "✅ <b>LECTEUR DISPONIBLE</b>\n\n"
            "📺 Regarder directement dans Telegram\n"
            "🚫 Sans pub ni redirections\n\n"
        )
    elif streams:
        msg += f"✅ {len(streams)} stream(s) disponible(s)\n\n"
    else:
        msg += "⚠️ Extraction en cours...\n\n"
    
    msg += "👇 <b>Choisissez:</b>"
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def embed_stream(query, match_id: str):
    """Lecteur intégré Telegram"""
    await query.answer("🎬 Chargement...")
    
    data = DataManager.load_data()
    match = next((m for m in data['matches'] if m['id'] == match_id), None)
    
    if not match:
        await query.answer("❌ Match introuvable", show_alert=True)
        return
    
    iframe = match.get('iframe_url')
    streams = match.get('stream_urls', [])
    
    if not iframe and not streams:
        await query.answer("⚠️ Aucun stream", show_alert=True)
        return
    
    player_url = iframe if iframe else streams[0]
    
    keyboard = []
    
    if len(streams) > 1:
        keyboard.append([
            InlineKeyboardButton("🔄 Changer qualité", callback_data=f"streams_{match_id}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("🌐 Navigateur", url=player_url)
    ])
    
    keyboard.append([
        InlineKeyboardButton("♻️ Rafraîchir", callback_data=f"embed_{match_id}")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 Retour", callback_data=f"watch_{match_id}")
    ])
    
    msg = (
        f"📺 <b>LECTEUR STREAM</b>\n\n"
        f"🎯 <b>{match['title']}</b>\n"
        f"{match['sport_icon']} {match['sport_name']} • {match['start_time']}\n\n"
        f"<a href='{player_url}'>▶️ CLIQUER POUR REGARDER</a>\n\n"
        "💡 <b>CONSEILS:</b>\n\n"
        "📱 <b>Mobile:</b>\n"
        "• Mode plein écran\n"
        "• Rotation automatique\n"
        "• Connexion stable\n\n"
        "💻 <b>PC:</b>\n"
        "• Cliquez sur le lecteur\n"
        "• F11 pour plein écran\n\n"
        "⚡ <b>Problème?</b>\n"
        "• Rafraîchissez\n"
        "• Essayez alternatives\n"
        "• Ouvrez dans navigateur\n\n"
        "🚫 <b>SANS PUB • SANS REDIRECT</b>"
    )
    
    try:
        await query.edit_message_text(
            msg,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=False
        )
    except:
        await query.edit_message_text(
            f"📺 <b>STREAM DIRECT</b>\n\n"
            f"🎯 {match['title']}\n\n"
            f"<a href='{player_url}'>▶️ CLIQUER POUR REGARDER</a>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def show_stream_options(query, match_id: str):
    """Options de qualité"""
    await query.answer()
    
    data = DataManager.load_data()
    match = next((m for m in data['matches'] if m['id'] == match_id), None)
    
    if not match:
        await query.answer("❌ Match introuvable", show_alert=True)
        return
    
    streams = match.get('stream_urls', [])
    
    if not streams:
        await query.answer("⚠️ Aucun stream", show_alert=True)
        return
    
    keyboard = []
    
    for idx, stream_url in enumerate(streams[:10], 1):
        quality = "HD"
        if 'hd' in stream_url.lower():
            quality = "HD+"
        elif 'sd' in stream_url.lower():
            quality = "SD"
        
        keyboard.append([
            InlineKeyboardButton(
                f"🎬 Stream {idx} ({quality})",
                url=stream_url
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 Retour", callback_data=f"watch_{match_id}")
    ])
    
    msg = (
        f"{match['sport_icon']} <b>{match['title']}</b>\n\n"
        f"🎬 <b>SÉLECTION QUALITÉ</b>\n\n"
        f"✅ {len(streams)} stream(s)\n\n"
        "💡 Choisissez un stream"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def toggle_favorite(query, match_id: str):
    """Toggle favoris"""
    user_id = str(query.from_user.id)
    
    favorites = DataManager.load_favorites()
    user_favs = favorites.get(user_id, [])
    
    if match_id in user_favs:
        user_favs.remove(match_id)
        await query.answer("💔 Retiré")
    else:
        user_favs.append(match_id)
        await query.answer("⭐ Ajouté !")
    
    favorites[user_id] = user_favs
    DataManager.save_favorites(favorites)
    
    await watch_match(query, match_id)

async def show_favorites(query):
    """Affiche favoris"""
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
            "⚠️ Favoris expirés\n\n"
            "💡 Réinitialisés quotidiennement",
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
    
    msg = (
        "⭐ <b>MES FAVORIS</b> ⭐\n\n"
        f"🎯 {len(fav_matches)} match(s)\n\n"
        "👇 Cliquez pour regarder:"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def refresh_all(query):
    """Actualisation complète"""
    await query.answer("🔄 Actualisation...")
    
    await query.edit_message_text(
        "⏳ <b>ACTUALISATION</b>\n\n"
        "🔍 Scan tous sports...\n"
        "📡 Extraction événements...\n\n"
        "⏱️ 30-90 secondes",
        parse_mode='HTML'
    )
    
    try:
        async with VIPRowUltraScraper() as scraper:
            count = await scraper.scrape_all_sports()
        
        keyboard = [[InlineKeyboardButton("✅ Voir Événements", callback_data="main_menu")]]
        
        await query.edit_message_text(
            "✅ <b>TERMINÉ !</b>\n\n"
            f"📊 {count} événements\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}\n\n"
            "🎯 Tous les matchs disponibles !",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]
        await query.edit_message_text(
            f"❌ <b>Erreur</b>\n\n<code>{str(e)[:150]}</code>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def admin_panel(query):
    """Panel admin"""
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
        [InlineKeyboardButton("📊 Statistiques", callback_data="admin_stats")],
        [InlineKeyboardButton("🗑️ Reset", callback_data="admin_reset")],
        [InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]
    ]
    
    msg = (
        "⚙️ <b>ADMIN PANEL</b>\n\n"
        "📊 <b>Stats:</b>\n"
        f"• Événements: <code>{len(data['matches'])}</code>\n"
        f"• Sports: <code>{len(sports_count)}</code>\n"
        f"• Utilisateurs: <code>{len(users)}</code>\n"
        f"• Favoris: <code>{sum(len(v) for v in favorites.values())}</code>\n"
        f"• MAJ: <code>{data.get('last_update', 'N/A')[:19]}</code>\n"
        f"• Reset: <code>{data.get('last_reset', 'N/A')}</code>"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_stats(query):
    """Stats détaillées"""
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
    
    msg = "📊 <b>STATS DÉTAILLÉES</b>\n\n🎯 <b>Sports:</b>\n"
    
    for sport, count in sorted(sports_count.items(), key=lambda x: x[1], reverse=True):
        config = SPORTS_CONFIGURATION.get(sport.lower(), {'icon': '🎯', 'name': sport})
        msg += f"• {config['icon']} {config['name']}: {count}\n"
    
    msg += (
        f"\n👥 <b>Utilisateurs:</b>\n"
        f"• Total: <code>{len(users)}</code>\n"
        f"• Favoris totaux: <code>{total_favs}</code>\n"
        f"• Moyenne/user: <code>{avg_favs:.1f}</code>\n\n"
        f"📅 <b>Derniers utilisateurs:</b>\n"
    )
    
    # Liste des 5 derniers utilisateurs
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
    """Reset données"""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Accès refusé", show_alert=True)
        return
    
    await query.answer("🗑️ Reset...")
    
    DataManager._create_fresh_data()
    
    keyboard = [[InlineKeyboardButton("✅ OK", callback_data="admin")]]
    await query.edit_message_text(
        "✅ <b>RESET EFFECTUÉ</b>\n\n"
        "🗑️ Données supprimées\n"
        "📊 Compteurs à zéro",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Router callbacks"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    if user_id not in ADMIN_IDS:
        if data != "check_sub":
            is_sub = await check_subscription(user_id, context)
            if not is_sub:
                await query.answer("⚠️ Rejoignez le canal !", show_alert=True)
                return
    
    # Routing
    if data == "check_sub":
        is_sub = await check_subscription(user_id, context)
        if is_sub:
            await query.answer("✅ Accès autorisé !")
            # FIX: Passer l'objet Update complet
            await show_main_menu(update, context)
        else:
            await query.answer("❌ Rejoignez le canal", show_alert=True)
    
    elif data == "main_menu":
        await show_main_menu(update, context)
    
    elif data == "favorites":
        await show_favorites(query)
    
    elif data == "refresh_all":
        await refresh_all(query)
    
    elif data == "admin":
        await admin_panel(query)
    
    elif data == "admin_update":
        await refresh_all(query)
    
    elif data == "admin_stats":
        await admin_stats(query)
    
    elif data == "admin_reset":
        await admin_reset(query)
    
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

# ============================================================================
# 🔄 TÂCHES AUTO
# ============================================================================

async def auto_update_loop(application):
    """MAJ auto 10 min"""
    await asyncio.sleep(60)
    
    while True:
        try:
            logger.info("🔄 MAJ auto...")
            async with VIPRowUltraScraper() as scraper:
                count = await scraper.scrape_all_sports()
            logger.info(f"✅ MAJ: {count} événements")
        except Exception as e:
            logger.error(f"❌ Erreur MAJ: {e}")
        
        await asyncio.sleep(600)

async def daily_reset_loop(application):
    """Reset quotidien minuit"""
    while True:
        now = datetime.now()
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        seconds = (tomorrow - now).total_seconds()
        
        logger.info(f"⏰ Prochain reset: {seconds/3600:.1f}h")
        await asyncio.sleep(seconds)
        
        logger.info("🌙 Reset quotidien...")
        DataManager._create_fresh_data()
        logger.info("✅ Reset terminé !")

async def post_init(application):
    """Init tâches"""
    asyncio.create_task(auto_update_loop(application))
    asyncio.create_task(daily_reset_loop(application))


# ============================================================================
# 🚀 MAIN
# ============================================================================

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP logs

def main():
    """Point d'entrée"""
    logger.info("=" * 80)
    logger.info("🚀 VIPROW ULTIMATE PRO BOT")
    logger.info("=" * 80)
    
    # Start simple HTTP server on port (for Render)
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Port {port} bound")

    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    logger.info("")
    logger.info("✅ BOT DÉMARRÉ !")
    logger.info("")
    logger.info("📊 FONCTIONNALITÉS:")
    logger.info("   ✅ Scraping 16 sports VIPRow")
    logger.info("   ✅ Visionnage DIRECT Telegram")
    logger.info("   ✅ Extraction auto streams")
    logger.info("   ✅ Multi-qualité")
    logger.info("   ✅ Favoris utilisateur")
    logger.info("   ✅ MAJ auto 10 min")
    logger.info("   ✅ Reset quotidien minuit")
    logger.info("   ✅ Tracking utilisateurs")
    logger.info("   ✅ Panel admin complet")
    logger.info("")
    logger.info("🌐 SPORTS:")
    for key, config in SPORTS_CONFIGURATION.items():
        logger.info(f"   {config['icon']} {config['name']}")
    logger.info("")
    logger.info("=" * 80)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()