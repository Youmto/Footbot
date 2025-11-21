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
import signal
import sys

# ============================================================================
# ⚙️ CONFIGURATION
# ============================================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8528649034:AAFCz7vV3-YDPq0UVlgkBws-5zG8EQ13vCs")
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

# Variables globales
background_tasks = set()
http_server = None
http_server_ready = threading.Event()
shutdown_event = asyncio.Event()
bot_initialized = False

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
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    @staticmethod
    def save_users(users: Dict):
        try:
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(users, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde users: {e}")
    
    @staticmethod
    def register_user(user_id: int, username: str = None, first_name: str = None):
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
# 🕷️ VIPROW SCRAPER
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
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
        self.stats['total_requests'] += 1
        
        for attempt in range(retries):
            try:
                await asyncio.sleep(REQUEST_DELAY)
                
                async with self.session.get(url, ssl=False, allow_redirects=True) as response:
                    if response.status == 200:
                        return await response.text()
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
        return re.sub(r'\s+', ' ', text.strip())
    
    @staticmethod
    def extract_match_info(title: str) -> Dict[str, str]:
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
                
                if match_url in seen or any(x in match_url.lower() for x in ['/sports-', 'schedule', 'contact', 'about']):
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
                
            except Exception:
                continue
        
        logger.info(f"✅ {sport_info['name']}: {len(matches)} événements")
        return matches
    
    async def extract_stream_urls(self, match_url: str, match_id: str) -> Tuple[Optional[str], List[str]]:
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
        if not url or len(url) < 10:
            return False
        
        blocked = ['facebook', 'twitter', 'ads', 'doubleclick', 'analytics']
        if any(block in url.lower() for block in blocked):
            return False
        
        valid = ['embed', 'player', 'stream', 'watch', 'live', '.m3u8', '.mp4']
        return any(v in url.lower() for v in valid)
    
    async def scrape_all_sports(self) -> int:
        logger.info("🚀 Scraping multi-sports VIPRow...")
        start = time.time()
        
        tasks = [self.scrape_sport(k, c['url']) for k, c in SPORTS_CONFIGURATION.items()]
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
        
        final_matches = list({m['id']: m for m in all_matches}.values())
        
        data = DataManager.load_data()
        data['matches'] = final_matches
        data['last_update'] = datetime.now().isoformat()
        data['total_scraped'] = len(final_matches)
        data['sports_count'] = sports_count
        DataManager.save_data(data)
        
        elapsed = time.time() - start
        logger.info(f"✅ SCRAPING TERMINÉ en {elapsed:.1f}s - {len(final_matches)} événements")
        
        return len(final_matches)
    
    async def scrape_sport(self, sport_key: str, url: str) -> List[Dict]:
        config = SPORTS_CONFIGURATION[sport_key]
        logger.info(f"📡 Scraping {config['name']}")
        
        html = await self.fetch_page(url)
        return await self.parse_sport_page(html, sport_key, url) if html else []

# ============================================================================
# 🤖 TELEGRAM HANDLERS (code identique, conservé pour la complétude)
# ============================================================================

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        await asyncio.sleep(0.3)
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except TelegramError as e:
        logger.error(f"❌ Check subscription: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
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
            msg, parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = DataManager.load_data()
    sports_count = data.get('sports_count', {})
    total = len(data.get('matches', []))
    user_id = update.effective_user.id
    
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
        
        text = f"{icon} {match['team1']} vs {match['team2']}" if match['team2'] else f"{icon} {match['title'][:50]}"
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
        text = f"⭐ {match['team1']} vs {match['team2']}" if match['team2'] else f"⭐ {match['title'][:45]}"
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
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    if user_id not in ADMIN_IDS:
        if data != "check_sub":
            is_sub = await check_subscription(user_id, context)
            if not is_sub:
                await query.answer("⚠️ Rejoignez le canal !", show_alert=True)
                return
    
    if data == "check_sub":
        is_sub = await check_subscription(user_id, context)
        if is_sub:
            await query.answer("✅ Accès autorisé !")
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
# 🔄 TÂCHES AUTO AVEC GESTION ROBUSTE
# ============================================================================

async def auto_update_loop(application):
    """MAJ auto toutes les 10 min avec gestion d'erreurs"""
    await asyncio.sleep(60)
    
    while not shutdown_event.is_set():
        try:
            logger.info("🔄 MAJ auto programmée...")
            async with VIPRowUltraScraper() as scraper:
                count = await scraper.scrape_all_sports()
            logger.info(f"✅ MAJ terminée: {count} événements")
        except asyncio.CancelledError:
            logger.info("⏹️ Tâche auto_update annulée")
            break
        except Exception as e:
            logger.error(f"❌ Erreur MAJ auto: {e}")
        
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=600)
            break
        except asyncio.TimeoutError:
            continue

async def daily_reset_loop(application):
    """Reset quotidien à minuit"""
    while not shutdown_event.is_set():
        try:
            now = datetime.now()
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            seconds = (tomorrow - now).total_seconds()
            
            logger.info(f"⏰ Prochain reset dans {seconds/3600:.1f}h")
            
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=seconds)
                break
            except asyncio.TimeoutError:
                logger.info("🌙 Exécution reset quotidien...")
                DataManager._create_fresh_data()
                logger.info("✅ Reset terminé !")
        except asyncio.CancelledError:
            logger.info("⏹️ Tâche daily_reset annulée")
            break
        except Exception as e:
            logger.error(f"❌ Erreur reset: {e}")
            await asyncio.sleep(3600)

async def post_init(application: Application):
    """Initialisation avec gestion propre des tâches"""
    global bot_initialized
    
    logger.info("🚀 Initialisation des tâches de fond...")
    
    task1 = asyncio.create_task(auto_update_loop(application), name="auto_update")
    task2 = asyncio.create_task(daily_reset_loop(application), name="daily_reset")
    
    background_tasks.add(task1)
    background_tasks.add(task2)
    
    task1.add_done_callback(background_tasks.discard)
    task2.add_done_callback(background_tasks.discard)
    
    bot_initialized = True
    logger.info("✅ Tâches de fond démarrées")

async def post_shutdown(application: Application):
    """Arrêt propre de toutes les tâches"""
    logger.info("🛑 Arrêt des tâches de fond...")
    
    shutdown_event.set()
    
    for task in background_tasks:
        if not task.done():
            task.cancel()
    
    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)
    
    logger.info("✅ Toutes les tâches arrêtées proprement")

# ============================================================================
# 🌐 SERVEUR HTTP ROBUSTE POUR RENDER
# ============================================================================

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Handler HTTP avec health check avancé"""
    
    def do_GET(self):
        try:
            if self.path == '/health':
                self.send_health_response()
            else:
                self.send_ok_response()
        except Exception as e:
            logger.error(f"❌ Erreur HTTP handler: {e}")
            self.send_error_response()
    
    def do_HEAD(self):
        try:
            self.send_ok_response()
        except Exception as e:
            logger.error(f"❌ Erreur HTTP HEAD: {e}")
    
    def send_ok_response(self):
        response = b'Bot Running OK'
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.send_header('Content-Length', str(len(response)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(response)
    
    def send_health_response(self):
        health_data = {
            'status': 'healthy',
            'bot_initialized': bot_initialized,
            'timestamp': datetime.now().isoformat(),
            'uptime': 'running'
        }
        response = json.dumps(health_data).encode('utf-8')
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(response)
    
    def send_error_response(self):
        response = b'Error'
        self.send_response(500)
        self.send_header('Content-type', 'text/plain')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response)
    
    def log_message(self, format, *args):
        pass

def start_http_server():
    """Démarre le serveur HTTP avec retry logic"""
    global http_server
    port = int(os.environ.get('PORT', 8080))
    max_retries = 5
    
    for attempt in range(max_retries):
        try:
            http_server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
            logger.info(f"🌐 Serveur HTTP démarré sur port {port}")
            http_server_ready.set()
            http_server.serve_forever()
            break
        except OSError as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Tentative {attempt+1}/{max_retries}: {e}")
                time.sleep(2 ** attempt)
            else:
                logger.error(f"❌ Impossible de démarrer le serveur HTTP: {e}")
                raise
        except Exception as e:
            logger.error(f"❌ Erreur serveur HTTP: {e}")
            raise

def stop_http_server():
    """Arrête le serveur HTTP proprement"""
    global http_server
    if http_server:
        logger.info("🛑 Arrêt du serveur HTTP...")
        try:
            http_server.shutdown()
            http_server.server_close()
            logger.info("✅ Serveur HTTP arrêté")
        except Exception as e:
            logger.error(f"❌ Erreur arrêt serveur: {e}")

# ============================================================================
# 🚀 MAIN AVEC GESTION COMPLÈTE ET ROBUSTE
# ============================================================================

def signal_handler(signum, frame):
    """Gestionnaire de signaux pour arrêt propre"""
    logger.info(f"⚠️ Signal {signum} reçu, arrêt en cours...")
    stop_http_server()
    sys.exit(0)

def main():
    """Point d'entrée principal avec gestion complète"""
    logger.info("=" * 80)
    logger.info("🚀 VIPROW ULTIMATE PRO BOT - PRODUCTION READY V2")
    logger.info("=" * 80)
    
    # Validation du token
    if not BOT_TOKEN or len(BOT_TOKEN) < 20:
        logger.error("❌ BOT_TOKEN invalide ou manquant!")
        logger.error("💡 Définissez la variable d'environnement BOT_TOKEN")
        sys.exit(1)
    
    # Configuration des signaux
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Démarrer le serveur HTTP en premier (NON daemon)
    http_thread = threading.Thread(target=start_http_server, daemon=False, name="HTTPServer")
    http_thread.start()
    
    # Attendre que le serveur soit prêt
    if not http_server_ready.wait(timeout=10):
        logger.error("❌ Timeout: serveur HTTP non démarré")
        sys.exit(1)
    
    logger.info("✅ Serveur HTTP opérationnel")
    
    # Construction de l'application
    try:
        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .post_init(post_init)
            .post_shutdown(post_shutdown)
            .connect_timeout(30)
            .read_timeout(30)
            .write_timeout(30)
            .build()
        )
    except Exception as e:
        logger.error(f"❌ Erreur construction application: {e}")
        stop_http_server()
        sys.exit(1)
    
    # Enregistrement des handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    logger.info("")
    logger.info("✅ BOT CONFIGURÉ AVEC SUCCÈS")
    logger.info("")
    logger.info("📊 FONCTIONNALITÉS:")
    logger.info("   ✅ Scraping 16 sports VIPRow")
    logger.info("   ✅ Visionnage DIRECT Telegram")
    logger.info("   ✅ Extraction auto streams")
    logger.info("   ✅ Multi-qualité HD")
    logger.info("   ✅ Favoris utilisateurs")
    logger.info("   ✅ MAJ auto 10 min")
    logger.info("   ✅ Reset quotidien minuit")
    logger.info("   ✅ Tracking utilisateurs")
    logger.info("   ✅ Panel admin complet")
    logger.info("   ✅ Serveur HTTP robuste")
    logger.info("   ✅ Health checks /health")
    logger.info("")
    logger.info("🌐 SPORTS DISPONIBLES:")
    for key, config in SPORTS_CONFIGURATION.items():
        logger.info(f"   {config['icon']} {config['name']}")
    logger.info("")
    logger.info("=" * 80)
    logger.info("🎯 Démarrage du polling...")
    logger.info("=" * 80)
    
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            close_loop=False,
            stop_signals=None
        )
    except KeyboardInterrupt:
        logger.info("⚠️ Arrêt demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
    finally:
        stop_http_server()
        logger.info("👋 Bot arrêté proprement")

if __name__ == '__main__':
    main()