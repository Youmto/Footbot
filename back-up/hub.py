import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaVideo, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError
import json
import os
from datetime import datetime, timedelta
import asyncio
from typing import List, Dict, Optional
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import signal
import sys
import hashlib

# ============================================================================
# ⚙️ CONFIGURATION
# ============================================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8199257003:AAGmE2ny-3owDb9L_CKhtsZVkXDIhPPW1Y0")
ADMIN_IDS = [5854095196]  # Ajoutez vos IDs admin ici
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1002415523895")  # Canal obligatoire (optionnel)
REQUIRED_CHANNEL = os.environ.get("REQUIRED_CHANNEL", "https://t.me/+mh1Ps_HZdQkzYjk0")  # URL du canal (vide = pas de restriction)

# Files
VIDEOS_FILE = "videos_data.json"
USERS_FILE = "users_data.json"
STATS_FILE = "stats_data.json"

# Categories
CATEGORIES = {
    'nude': {'name': 'Nude 🔞', 'icon': '🔞'},
    'buzz': {'name': 'Vidéo Buzz 🔥', 'icon': '🔥'},
    'pornhub': {'name': 'Pornhub 🔴', 'icon': '🔴'},
    'onlyfans': {'name': 'OnlyFans 💎', 'icon': '💎'},
    'celebrity': {'name': 'Célébrité 🌟', 'icon': '🌟'},
    'leaked': {'name': 'Leaked 💣', 'icon': '💣'},
    'amateur': {'name': 'Amateur 🎬', 'icon': '🎬'},
    'trending': {'name': 'Trending 📈', 'icon': '📈'},
    'exclusive': {'name': 'Exclusif ⭐', 'icon': '⭐'},
    'other': {'name': 'Autre 📱', 'icon': '📱'}
}

# Variables globales
admin_states = {}
http_server = None
http_server_ready = threading.Event()
bot_initialized = False

# ============================================================================
# 📦 DATA MANAGER
# ============================================================================

class DataManager:
    """Gestionnaire de données centralisé"""
    
    @staticmethod
    def load_videos() -> List[Dict]:
        if os.path.exists(VIDEOS_FILE):
            try:
                with open(VIDEOS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    @staticmethod
    def save_videos(videos: List[Dict]):
        try:
            with open(VIDEOS_FILE, 'w', encoding='utf-8') as f:
                json.dump(videos, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde vidéos: {e}")
    
    @staticmethod
    def add_video(video_data: Dict) -> str:
        videos = DataManager.load_videos()
        
        video_id = hashlib.md5(
            f"{video_data['file_id']}_{datetime.now().timestamp()}".encode()
        ).hexdigest()[:12]
        
        video_data['id'] = video_id
        video_data['created_at'] = datetime.now().isoformat()
        video_data['views'] = 0
        video_data['likes'] = 0
        video_data['shares'] = 0
        
        videos.insert(0, video_data)
        DataManager.save_videos(videos)
        
        return video_id
    
    @staticmethod
    def delete_video(video_id: str) -> bool:
        videos = DataManager.load_videos()
        videos = [v for v in videos if v['id'] != video_id]
        DataManager.save_videos(videos)
        return True
    
    @staticmethod
    def get_video(video_id: str) -> Optional[Dict]:
        videos = DataManager.load_videos()
        return next((v for v in videos if v['id'] == video_id), None)
    
    @staticmethod
    def increment_view(video_id: str):
        videos = DataManager.load_videos()
        for video in videos:
            if video['id'] == video_id:
                video['views'] = video.get('views', 0) + 1
                DataManager.save_videos(videos)
                break
    
    @staticmethod
    def increment_like(video_id: str):
        videos = DataManager.load_videos()
        for video in videos:
            if video['id'] == video_id:
                video['likes'] = video.get('likes', 0) + 1
                DataManager.save_videos(videos)
                break
    
    @staticmethod
    def increment_share(video_id: str):
        videos = DataManager.load_videos()
        for video in videos:
            if video['id'] == video_id:
                video['shares'] = video.get('shares', 0) + 1
                DataManager.save_videos(videos)
                break
    
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
                'joined_at': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat(),
                'total_views': 0,
                'favorites': []
            }
            logger.info(f"👤 Nouvel utilisateur: {user_id} ({username or first_name})")
        else:
            users[user_key]['last_seen'] = datetime.now().isoformat()
            if username:
                users[user_key]['username'] = username
            if first_name:
                users[user_key]['first_name'] = first_name
        
        DataManager.save_users(users)
        return users[user_key]
    
    @staticmethod
    def get_stats() -> Dict:
        videos = DataManager.load_videos()
        users = DataManager.load_users()
        
        total_views = sum(v.get('views', 0) for v in videos)
        total_likes = sum(v.get('likes', 0) for v in videos)
        total_shares = sum(v.get('shares', 0) for v in videos)
        
        categories_count = {}
        for video in videos:
            cat = video.get('category', 'other')
            categories_count[cat] = categories_count.get(cat, 0) + 1
        
        return {
            'total_videos': len(videos),
            'total_users': len(users),
            'total_views': total_views,
            'total_likes': total_likes,
            'total_shares': total_shares,
            'categories': categories_count
        }

# ============================================================================
# 🔐 VÉRIFICATION ABONNEMENT (OPTIONNEL)
# ============================================================================

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Vérifie l'abonnement au canal (OBLIGATOIRE)"""
    if not REQUIRED_CHANNEL or not CHANNEL_ID:
        return False  # Pas de canal configuré = accès refusé
    
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False  # En cas d'erreur, on refuse l'accès

# ============================================================================
# 🤖 COMMANDES UTILISATEUR
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /start"""
    user = update.effective_user
    user_id = user.id
    
    DataManager.register_user(user_id, user.username, user.first_name)
    logger.info(f"👤 {user_id} ({user.username or user.first_name}) => /start")
    
    is_admin = user_id in ADMIN_IDS
    
    # Vérification abonnement OBLIGATOIRE (sauf pour les admins)
    if not is_admin:
        is_sub = await check_subscription(user_id, context)
        if not is_sub:
            keyboard = [
                [InlineKeyboardButton("🔥 REJOINDRE LE GROUPE VIP", url=REQUIRED_CHANNEL)],
                [InlineKeyboardButton("✅ J'ai rejoint !", callback_data="check_sub")]
            ]
            
            msg = (
                "🔞 <b>CONTENU EXCLUSIF +18</b> 🔞\n\n"
                f"👋 Salut <b>{user.first_name}</b> !\n\n"
                "🔥 <b>ACCÈS À :</b>\n\n"
                "🔞 Nude Premium\n"
                "🔥 Vidéos Buzz du moment\n"
                "🔴 Contenu Pornhub\n"
                "💎 OnlyFans Leaks\n"
                "🌟 Célébrités\n"
                "💣 Contenus Leaked\n"
                "🎬 Amateur exclusif\n"
                "📈 Trending viral\n\n"
                "⚡ <b>NOUVEAU CONTENU CHAQUE JOUR</b>\n"
                "🚫 100% GRATUIT\n"
                "🔐 ACCÈS IMMÉDIAT\n\n"
                "⚠️ <b>ATTENTION : Contenu +18 uniquement</b>\n\n"
                "👇 <b>REJOINS LE GROUPE POUR DÉBLOQUER:</b>"
            )
            
            await update.message.reply_text(
                msg, parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
    
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu principal"""
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS
    
    videos = DataManager.load_videos()
    stats = DataManager.get_stats()
    
    keyboard = [
        [InlineKeyboardButton("🔥 VIDÉOS BUZZ", callback_data="popular")],
        [InlineKeyboardButton("🔞 TOUTES LES CATÉGORIES", callback_data="categories")],
        [InlineKeyboardButton("🆕 Derniers Ajouts", callback_data="latest")],
        [InlineKeyboardButton("⭐ Mes Favoris", callback_data="favorites")],
    ]
    
    if is_admin:
        keyboard.append([InlineKeyboardButton("⚙️ ADMIN PANEL", callback_data="admin")])
    
    msg = (
        "🔞 <b>CONTENU EXCLUSIF +18</b> 🔞\n\n"
        f"📊 <b>{stats['total_videos']}</b> vidéos disponibles\n"
        f"👥 <b>{stats['total_users']}</b> membres\n"
        f"👁️ <b>{stats['total_views']}</b> vues totales\n"
        f"❤️ <b>{stats['total_likes']}</b> likes\n\n"
        "🔥 <b>CONTENU MIS À JOUR QUOTIDIENNEMENT</b>\n\n"
        "⚠️ <i>Réservé aux +18 ans</i>\n\n"
        "👇 <b>Que veux-tu regarder ?</b>"
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

async def show_categories(query):
    """Affiche les catégories"""
    await query.answer()
    
    stats = DataManager.get_stats()
    categories_count = stats.get('categories', {})
    
    keyboard = []
    
    # Catégories principales en premier
    priority_cats = ['nude', 'buzz', 'pornhub', 'onlyfans', 'celebrity', 'leaked']
    
    for cat_key in priority_cats:
        if cat_key in CATEGORIES:
            cat_info = CATEGORIES[cat_key]
            count = categories_count.get(cat_key, 0)
            if count > 0:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{cat_info['icon']} {cat_info['name']} ({count})",
                        callback_data=f"cat_{cat_key}"
                    )
                ])
    
    # Autres catégories
    for cat_key, cat_info in CATEGORIES.items():
        if cat_key not in priority_cats:
            count = categories_count.get(cat_key, 0)
            if count > 0:
                keyboard.append([
                    InlineKeyboardButton(
                        f"{cat_info['icon']} {cat_info['name']} ({count})",
                        callback_data=f"cat_{cat_key}"
                    )
                ])
    
    keyboard.append([InlineKeyboardButton("🔙 Menu Principal", callback_data="main_menu")])
    
    msg = (
        "🔞 <b>CATÉGORIES +18</b>\n\n"
        "📂 <b>Contenu exclusif par catégorie</b>\n\n"
        "⚠️ Tout le contenu est réservé aux adultes\n\n"
        "👇 <b>Choisis ta catégorie:</b>"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_videos_by_category(query, category: str):
    """Affiche les vidéos d'une catégorie"""
    await query.answer()
    
    videos = DataManager.load_videos()
    cat_videos = [v for v in videos if v.get('category') == category]
    
    if not cat_videos:
        keyboard = [[InlineKeyboardButton("🔙 Catégories", callback_data="categories")]]
        await query.edit_message_text(
            f"❌ Aucune vidéo dans cette catégorie",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    cat_info = CATEGORIES.get(category, {'name': 'Vidéos', 'icon': '📱'})
    
    keyboard = []
    for video in cat_videos[:20]:
        title = video.get('title', 'Sans titre')[:40]
        views = video.get('views', 0)
        keyboard.append([
            InlineKeyboardButton(
                f"{cat_info['icon']} {title} (👁️ {views})",
                callback_data=f"watch_{video['id']}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 Catégories", callback_data="categories"),
        InlineKeyboardButton("🏠 Menu", callback_data="main_menu")
    ])
    
    msg = (
        f"{cat_info['icon']} <b>{cat_info['name'].upper()}</b>\n\n"
        f"📱 <b>{len(cat_videos)}</b> vidéo(s)\n\n"
        "👇 Sélectionne une vidéo:"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_popular_videos(query):
    """Affiche les vidéos populaires"""
    await query.answer()
    
    videos = DataManager.load_videos()
    popular = sorted(videos, key=lambda x: x.get('views', 0), reverse=True)[:20]
    
    if not popular:
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]
        await query.edit_message_text(
            "❌ Aucune vidéo disponible",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    keyboard = []
    for video in popular:
        cat_info = CATEGORIES.get(video.get('category', 'other'), {'icon': '📱'})
        title = video.get('title', 'Sans titre')[:35]
        views = video.get('views', 0)
        likes = video.get('likes', 0)
        keyboard.append([
            InlineKeyboardButton(
                f"{cat_info['icon']} {title} (👁️ {views} ❤️ {likes})",
                callback_data=f"watch_{video['id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Menu", callback_data="main_menu")])
    
    msg = (
        "🔥 <b>VIDÉOS POPULAIRES</b>\n\n"
        f"📊 Top {len(popular)} vidéos\n\n"
        "👇 Sélectionne une vidéo:"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_latest_videos(query):
    """Affiche les dernières vidéos"""
    await query.answer()
    
    videos = DataManager.load_videos()[:20]
    
    if not videos:
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]
        await query.edit_message_text(
            "❌ Aucune vidéo disponible",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    keyboard = []
    for video in videos:
        cat_info = CATEGORIES.get(video.get('category', 'other'), {'icon': '📱'})
        title = video.get('title', 'Sans titre')[:40]
        keyboard.append([
            InlineKeyboardButton(
                f"🆕 {title}",
                callback_data=f"watch_{video['id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Menu", callback_data="main_menu")])
    
    msg = (
        "🆕 <b>DERNIÈRES VIDÉOS</b>\n\n"
        f"📱 {len(videos)} nouvelle(s) vidéo(s)\n\n"
        "👇 Sélectionne une vidéo:"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def watch_video(query, video_id: str):
    """Affiche une vidéo"""
    video = DataManager.get_video(video_id)
    
    if not video:
        await query.answer("❌ Vidéo introuvable", show_alert=True)
        return
    
    await query.answer()
    
    # Incrémenter les vues
    DataManager.increment_view(video_id)
    
    # Mettre à jour les stats utilisateur
    user_id = str(query.from_user.id)
    users = DataManager.load_users()
    if user_id in users:
        users[user_id]['total_views'] = users[user_id].get('total_views', 0) + 1
        DataManager.save_users(users)
    
    cat_info = CATEGORIES.get(video.get('category', 'other'), {'icon': '📱', 'name': 'Autre'})
    
    # Vérifier si dans les favoris
    users = DataManager.load_users()
    user_favs = users.get(user_id, {}).get('favorites', [])
    is_fav = video_id in user_favs
    
    keyboard = [
        [
            InlineKeyboardButton("❤️ J'aime", callback_data=f"like_{video_id}"),
            InlineKeyboardButton("💔 Dislike" if is_fav else "⭐ Favoris", callback_data=f"fav_{video_id}")
        ],
        [
            InlineKeyboardButton("📤 Partager", callback_data=f"share_{video_id}"),
            InlineKeyboardButton("📊 Stats", callback_data=f"stats_{video_id}")
        ],
        [InlineKeyboardButton("🔙 Retour", callback_data="main_menu")]
    ]
    
    caption = (
        f"{cat_info['icon']} <b>{video.get('title', 'Sans titre')}</b>\n\n"
        f"📂 {cat_info['name']}\n"
        f"👁️ {video.get('views', 0)} vues\n"
        f"❤️ {video.get('likes', 0)} j'aime\n"
        f"📤 {video.get('shares', 0)} partages\n"
    )
    
    if video.get('description'):
        caption += f"\n📝 {video['description']}"
    
    try:
        # Supprimer le message précédent
        await query.message.delete()
        
        # Envoyer la vidéo
        if video.get('type') == 'photo':
            await query.message.reply_photo(
                photo=video['file_id'],
                caption=caption,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.message.reply_video(
                video=video['file_id'],
                caption=caption,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        logger.error(f"❌ Erreur envoi vidéo: {e}")
        await query.message.reply_text(
            "❌ Erreur lors du chargement de la vidéo",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]])
        )

async def like_video(query, video_id: str):
    """Like une vidéo"""
    DataManager.increment_like(video_id)
    await query.answer("❤️ Merci pour ton like !")

async def toggle_favorite(query, video_id: str):
    """Toggle favori"""
    user_id = str(query.from_user.id)
    users = DataManager.load_users()
    
    if user_id not in users:
        users[user_id] = {'favorites': []}
    
    if 'favorites' not in users[user_id]:
        users[user_id]['favorites'] = []
    
    if video_id in users[user_id]['favorites']:
        users[user_id]['favorites'].remove(video_id)
        await query.answer("💔 Retiré des favoris")
    else:
        users[user_id]['favorites'].append(video_id)
        await query.answer("⭐ Ajouté aux favoris !")
    
    DataManager.save_users(users)

async def share_video(query, video_id: str):
    """Partager une vidéo"""
    DataManager.increment_share(video_id)
    
    video = DataManager.get_video(video_id)
    if video:
        bot_username = (await query.get_bot()).username
        share_url = f"https://t.me/{bot_username}?start=video_{video_id}"
        
        keyboard = [
            [InlineKeyboardButton("📤 Partager", url=f"https://t.me/share/url?url={share_url}")],
            [InlineKeyboardButton("🔙 Retour", callback_data=f"watch_{video_id}")]
        ]
        
        await query.edit_message_text(
            f"📤 <b>PARTAGER CETTE VIDÉO</b>\n\n"
            f"🔗 Lien: <code>{share_url}</code>\n\n"
            "👇 Clique pour partager:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def show_video_stats(query, video_id: str):
    """Statistiques vidéo"""
    video = DataManager.get_video(video_id)
    
    if not video:
        await query.answer("❌ Vidéo introuvable", show_alert=True)
        return
    
    cat_info = CATEGORIES.get(video.get('category', 'other'), {'icon': '📱', 'name': 'Autre'})
    created = datetime.fromisoformat(video['created_at']).strftime("%d/%m/%Y %H:%M")
    
    keyboard = [[InlineKeyboardButton("🔙 Retour", callback_data=f"watch_{video_id}")]]
    
    msg = (
        f"📊 <b>STATISTIQUES</b>\n\n"
        f"📝 <b>{video.get('title', 'Sans titre')}</b>\n\n"
        f"📂 Catégorie: {cat_info['name']}\n"
        f"📅 Ajoutée: {created}\n"
        f"👁️ Vues: <b>{video.get('views', 0)}</b>\n"
        f"❤️ J'aime: <b>{video.get('likes', 0)}</b>\n"
        f"📤 Partages: <b>{video.get('shares', 0)}</b>\n"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_favorites(query):
    """Affiche les favoris"""
    await query.answer()
    
    user_id = str(query.from_user.id)
    users = DataManager.load_users()
    user_favs = users.get(user_id, {}).get('favorites', [])
    
    if not user_favs:
        keyboard = [[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]
        await query.edit_message_text(
            "⭐ <b>MES FAVORIS</b>\n\n"
            "❌ Aucun favori\n\n"
            "💡 Ajoute tes vidéos préférées !",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    videos = DataManager.load_videos()
    fav_videos = [v for v in videos if v['id'] in user_favs]
    
    keyboard = []
    for video in fav_videos[:20]:
        cat_info = CATEGORIES.get(video.get('category', 'other'), {'icon': '📱'})
        title = video.get('title', 'Sans titre')[:40]
        keyboard.append([
            InlineKeyboardButton(
                f"⭐ {title}",
                callback_data=f"watch_{video['id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Menu", callback_data="main_menu")])
    
    msg = (
        "⭐ <b>MES FAVORIS</b>\n\n"
        f"📱 {len(fav_videos)} vidéo(s)\n\n"
        "👇 Sélectionne une vidéo:"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============================================================================
# 🔧 PANEL ADMIN
# ============================================================================

async def admin_panel(query):
    """Panel admin principal"""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Accès refusé", show_alert=True)
        return
    
    await query.answer()
    
    stats = DataManager.get_stats()
    
    keyboard = [
        [InlineKeyboardButton("➕ Ajouter Vidéo", callback_data="admin_add")],
        [InlineKeyboardButton("📋 Gérer Vidéos", callback_data="admin_manage")],
        [InlineKeyboardButton("📊 Statistiques", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Utilisateurs", callback_data="admin_users")],
        [InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]
    ]
    
    msg = (
        "⚙️ <b>PANEL ADMIN</b>\n\n"
        f"📱 Vidéos: <b>{stats['total_videos']}</b>\n"
        f"👥 Users: <b>{stats['total_users']}</b>\n"
        f"👁️ Vues: <b>{stats['total_views']}</b>\n"
        f"❤️ Likes: <b>{stats['total_likes']}</b>\n"
        f"📤 Partages: <b>{stats['total_shares']}</b>\n\n"
        "👇 Que veux-tu faire ?"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_add_video(query):
    """Démarrer l'ajout d'une vidéo"""
    if query.from_user.id not in ADMIN_IDS:
        return
    
    await query.answer()
    
    admin_states[query.from_user.id] = {'state': 'waiting_video'}
    
    keyboard = [[InlineKeyboardButton("❌ Annuler", callback_data="admin")]]
    
    msg = (
        "➕ <b>AJOUTER UNE VIDÉO</b>\n\n"
        "📹 Envoie-moi la vidéo ou photo\n\n"
        "💡 Tu pourras ensuite:\n"
        "• Ajouter un titre\n"
        "• Choisir une catégorie\n"
        "• Ajouter une description"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_video_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère l'upload de vidéo par l'admin"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        return
    
    if user_id not in admin_states or admin_states[user_id].get('state') != 'waiting_video':
        return
    
    # Récupérer la vidéo ou photo
    if update.message.video:
        file_id = update.message.video.file_id
        media_type = 'video'
    elif update.message.photo:
        file_id = update.message.photo[-1].file_id
        media_type = 'photo'
    else:
        await update.message.reply_text("❌ Envoie une vidéo ou photo")
        return
    
    admin_states[user_id] = {
        'state': 'waiting_title',
        'file_id': file_id,
        'type': media_type
    }
    
    keyboard = [[InlineKeyboardButton("❌ Annuler", callback_data="admin")]]
    
    await update.message.reply_text(
        "✅ <b>Vidéo reçue !</b>\n\n"
        "📝 Maintenant, envoie le <b>titre</b>:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les textes de l'admin"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS or user_id not in admin_states:
        return
    
    state_data = admin_states[user_id]
    state = state_data.get('state')
    
    if state == 'waiting_title':
        state_data['title'] = update.message.text
        state_data['state'] = 'waiting_category'
        
        keyboard = []
        for cat_key, cat_info in CATEGORIES.items():
            keyboard.append([
                InlineKeyboardButton(
                    f"{cat_info['icon']} {cat_info['name']}",
                    callback_data=f"addcat_{cat_key}"
                )
            ])
        keyboard.append([InlineKeyboardButton("❌ Annuler", callback_data="admin")])
        
        await update.message.reply_text(
            "✅ <b>Titre enregistré !</b>\n\n"
            "📂 Choisis une <b>catégorie</b>:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif state == 'waiting_description':
        state_data['description'] = update.message.text
        
        # Sauvegarder la vidéo
        video_data = {
            'file_id': state_data['file_id'],
            'type': state_data['type'],
            'title': state_data['title'],
            'category': state_data['category'],
            'description': state_data.get('description', '')
        }
        
        video_id = DataManager.add_video(video_data)
        
        del admin_states[user_id]
        
        keyboard = [
            [InlineKeyboardButton("👁️ Voir la vidéo", callback_data=f"watch_{video_id}")],
            [InlineKeyboardButton("➕ Ajouter une autre", callback_data="admin_add")],
            [InlineKeyboardButton("🔙 Admin", callback_data="admin")]
        ]
        
        await update.message.reply_text(
            "✅ <b>VIDÉO PUBLIÉE !</b>\n\n"
            "🎉 La vidéo est maintenant visible\n"
            "📊 Disponible dans le bot",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def admin_select_category(query, category: str):
    """Sélection de catégorie par l'admin"""
    user_id = query.from_user.id
    
    if user_id not in ADMIN_IDS or user_id not in admin_states:
        return
    
    await query.answer()
    
    admin_states[user_id]['category'] = category
    admin_states[user_id]['state'] = 'waiting_description'
    
    cat_info = CATEGORIES[category]
    
    keyboard = [
        [InlineKeyboardButton("⏭️ Passer", callback_data="admin_skip_desc")],
        [InlineKeyboardButton("❌ Annuler", callback_data="admin")]
    ]
    
    await query.edit_message_text(
        f"✅ <b>Catégorie: {cat_info['icon']} {cat_info['name']}</b>\n\n"
        "📝 Ajoute une <b>description</b> (optionnel):\n\n"
        "💡 Ou clique sur Passer",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_skip_description(query):
    """Passer la description"""
    user_id = query.from_user.id
    
    if user_id not in ADMIN_IDS or user_id not in admin_states:
        return
    
    await query.answer()
    
    state_data = admin_states[user_id]
    
    video_data = {
        'file_id': state_data['file_id'],
        'type': state_data['type'],
        'title': state_data['title'],
        'category': state_data['category'],
        'description': ''
    }
    
    video_id = DataManager.add_video(video_data)
    
    del admin_states[user_id]
    
    keyboard = [
        [InlineKeyboardButton("👁️ Voir la vidéo", callback_data=f"watch_{video_id}")],
        [InlineKeyboardButton("➕ Ajouter une autre", callback_data="admin_add")],
        [InlineKeyboardButton("🔙 Admin", callback_data="admin")]
    ]
    
    await query.edit_message_text(
        "✅ <b>VIDÉO PUBLIÉE !</b>\n\n"
        "🎉 La vidéo est maintenant visible\n"
        "📊 Disponible dans le bot",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_manage_videos(query):
    """Gérer les vidéos"""
    if query.from_user.id not in ADMIN_IDS:
        return
    
    await query.answer()
    
    videos = DataManager.load_videos()[:20]
    
    if not videos:
        keyboard = [[InlineKeyboardButton("🔙 Admin", callback_data="admin")]]
        await query.edit_message_text(
            "❌ Aucune vidéo à gérer",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    keyboard = []
    for video in videos:
        cat_info = CATEGORIES.get(video.get('category', 'other'), {'icon': '📱'})
        title = video.get('title', 'Sans titre')[:35]
        views = video.get('views', 0)
        keyboard.append([
            InlineKeyboardButton(
                f"{cat_info['icon']} {title} (👁️ {views})",
                callback_data=f"admin_edit_{video['id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Admin", callback_data="admin")])
    
    await query.edit_message_text(
        "📋 <b>GÉRER LES VIDÉOS</b>\n\n"
        "👇 Sélectionne une vidéo:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_edit_video(query, video_id: str):
    """Éditer une vidéo"""
    if query.from_user.id not in ADMIN_IDS:
        return
    
    await query.answer()
    
    video = DataManager.get_video(video_id)
    if not video:
        await query.answer("❌ Vidéo introuvable", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton("🗑️ Supprimer", callback_data=f"admin_del_{video_id}")],
        [InlineKeyboardButton("👁️ Voir", callback_data=f"watch_{video_id}")],
        [InlineKeyboardButton("🔙 Retour", callback_data="admin_manage")]
    ]
    
    cat_info = CATEGORIES.get(video.get('category', 'other'), {'name': 'Autre'})
    
    msg = (
        f"✏️ <b>ÉDITER VIDÉO</b>\n\n"
        f"📝 {video.get('title', 'Sans titre')}\n"
        f"📂 {cat_info['name']}\n"
        f"👁️ {video.get('views', 0)} vues\n"
        f"❤️ {video.get('likes', 0)} likes\n\n"
        "👇 Que veux-tu faire ?"
    )
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_delete_video(query, video_id: str):
    """Supprimer une vidéo"""
    if query.from_user.id not in ADMIN_IDS:
        return
    
    await query.answer("🗑️ Suppression...")
    
    DataManager.delete_video(video_id)
    
    keyboard = [
        [InlineKeyboardButton("📋 Gérer vidéos", callback_data="admin_manage")],
        [InlineKeyboardButton("🔙 Admin", callback_data="admin")]
    ]
    
    await query.edit_message_text(
        "✅ <b>VIDÉO SUPPRIMÉE</b>\n\n"
        "🗑️ La vidéo a été retirée",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_show_stats(query):
    """Statistiques détaillées"""
    if query.from_user.id not in ADMIN_IDS:
        return
    
    await query.answer()
    
    stats = DataManager.get_stats()
    videos = DataManager.load_videos()
    
    # Top 5 vidéos
    top_videos = sorted(videos, key=lambda x: x.get('views', 0), reverse=True)[:5]
    
    msg = "📊 <b>STATISTIQUES DÉTAILLÉES</b>\n\n"
    
    msg += "📂 <b>Par catégorie:</b>\n"
    for cat_key, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True):
        cat_info = CATEGORIES.get(cat_key, {'icon': '📱', 'name': cat_key})
        msg += f"• {cat_info['icon']} {cat_info['name']}: {count}\n"
    
    msg += f"\n🔥 <b>Top 5 vidéos:</b>\n"
    for i, video in enumerate(top_videos, 1):
        title = video.get('title', 'Sans titre')[:30]
        views = video.get('views', 0)
        msg += f"{i}. {title} ({views} 👁️)\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Admin", callback_data="admin")]]
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_show_users(query):
    """Liste des utilisateurs"""
    if query.from_user.id not in ADMIN_IDS:
        return
    
    await query.answer()
    
    users = DataManager.load_users()
    
    sorted_users = sorted(
        users.values(),
        key=lambda x: x.get('total_views', 0),
        reverse=True
    )[:10]
    
    msg = f"👥 <b>UTILISATEURS ({len(users)} total)</b>\n\n"
    msg += "🏆 <b>Top 10 actifs:</b>\n\n"
    
    for i, user in enumerate(sorted_users, 1):
        username = user.get('username', 'N/A')
        first_name = user.get('first_name', 'User')
        views = user.get('total_views', 0)
        favs = len(user.get('favorites', []))
        msg += f"{i}. @{username or first_name}\n   👁️ {views} vues • ⭐ {favs} favoris\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Admin", callback_data="admin")]]
    
    await query.edit_message_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ============================================================================
# 🎯 CALLBACK HANDLER
# ============================================================================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestionnaire de callbacks"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    # Vérification abonnement OBLIGATOIRE (sauf pour admin et check_sub)
    if user_id not in ADMIN_IDS and data != "check_sub":
        is_sub = await check_subscription(user_id, context)
        if not is_sub:
            await query.answer("🔒 Tu dois rejoindre le groupe pour accéder au contenu !", show_alert=True)
            
            keyboard = [
                [InlineKeyboardButton("🔥 REJOINDRE LE GROUPE VIP", url=REQUIRED_CHANNEL)],
                [InlineKeyboardButton("✅ J'ai rejoint !", callback_data="check_sub")]
            ]
            
            try:
                await query.edit_message_text(
                    "🔞 <b>ACCÈS REFUSÉ</b>\n\n"
                    "🔒 Tu dois rejoindre notre groupe VIP\n"
                    "pour accéder au contenu exclusif +18\n\n"
                    "👇 Clique ci-dessous:",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except:
                pass
            return
    
    if data == "check_sub":
        is_sub = await check_subscription(user_id, context)
        if is_sub:
            await query.answer("✅ Accès débloqué ! Bienvenue 🔥", show_alert=True)
            await show_main_menu(update, context)
        else:
            await query.answer("❌ Tu n'as pas encore rejoint le groupe !", show_alert=True)
    
    elif data == "main_menu":
        await show_main_menu(update, context)
    
    elif data == "categories":
        await show_categories(query)
    
    elif data == "popular":
        await show_popular_videos(query)
    
    elif data == "latest":
        await show_latest_videos(query)
    
    elif data == "favorites":
        await show_favorites(query)
    
    elif data.startswith("cat_"):
        category = data.split("_", 1)[1]
        await show_videos_by_category(query, category)
    
    elif data.startswith("watch_"):
        video_id = data.split("_", 1)[1]
        await watch_video(query, video_id)
    
    elif data.startswith("like_"):
        video_id = data.split("_", 1)[1]
        await like_video(query, video_id)
    
    elif data.startswith("fav_"):
        video_id = data.split("_", 1)[1]
        await toggle_favorite(query, video_id)
    
    elif data.startswith("share_"):
        video_id = data.split("_", 1)[1]
        await share_video(query, video_id)
    
    elif data.startswith("stats_"):
        video_id = data.split("_", 1)[1]
        await show_video_stats(query, video_id)
    
    # Admin callbacks
    elif data == "admin":
        await admin_panel(query)
    
    elif data == "admin_add":
        await admin_add_video(query)
    
    elif data == "admin_manage":
        await admin_manage_videos(query)
    
    elif data == "admin_stats":
        await admin_show_stats(query)
    
    elif data == "admin_users":
        await admin_show_users(query)
    
    elif data.startswith("addcat_"):
        category = data.split("_", 1)[1]
        await admin_select_category(query, category)
    
    elif data == "admin_skip_desc":
        await admin_skip_description(query)
    
    elif data.startswith("admin_edit_"):
        video_id = data.split("_", 2)[2]
        await admin_edit_video(query, video_id)
    
    elif data.startswith("admin_del_"):
        video_id = data.split("_", 2)[2]
        await admin_delete_video(query, video_id)

# ============================================================================
# 🌐 SERVEUR HTTP POUR RENDER
# ============================================================================

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        pass

def start_http_server():
    global http_server
    port = int(os.environ.get('PORT', 8080))
    
    try:
        http_server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        logger.info(f"🌐 Serveur HTTP sur port {port}")
        http_server_ready.set()
        http_server.serve_forever()
    except Exception as e:
        logger.error(f"❌ Erreur serveur: {e}")

def stop_http_server():
    global http_server
    if http_server:
        http_server.shutdown()
        http_server.server_close()

# ============================================================================
# 🚀 MAIN
# ============================================================================

def signal_handler(signum, frame):
    logger.info(f"⚠️ Signal {signum} reçu")
    stop_http_server()
    sys.exit(0)

def main():
    logger.info("=" * 60)
    logger.info("🔥 BOT CONTENU VIRAL - DÉMARRAGE")
    logger.info("=" * 60)
    
    if not BOT_TOKEN or len(BOT_TOKEN) < 20:
        logger.error("❌ BOT_TOKEN invalide!")
        sys.exit(1)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Démarrer serveur HTTP
    http_thread = threading.Thread(target=start_http_server, daemon=False)
    http_thread.start()
    
    if not http_server_ready.wait(timeout=10):
        logger.error("❌ Serveur HTTP non démarré")
        sys.exit(1)
    
    # Créer l'application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.VIDEO | filters.PHOTO, handle_video_upload))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))
    
    logger.info("✅ Bot configuré")
    logger.info("")
    logger.info("📱 FONCTIONNALITÉS:")
    logger.info("   ✅ Contenu exclusif +18")
    logger.info("   ✅ 10 catégories (Nude, Buzz, Pornhub, etc.)")
    logger.info("   ✅ Système de likes/favoris")
    logger.info("   ✅ Statistiques complètes")
    logger.info("   ✅ Panel admin complet")
    logger.info("   ✅ Upload vidéo/photo simple")
    logger.info("   ✅ Accès OBLIGATOIRE via groupe VIP")
    logger.info("")
    logger.info("🔞 CATÉGORIES:")
    for key, info in CATEGORIES.items():
        logger.info(f"   {info['icon']} {info['name']}")
    logger.info("")
    logger.info("🚀 Démarrage du polling...")
    
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        logger.info("⚠️ Arrêt demandé")
    finally:
        stop_http_server()
        logger.info("👋 Bot arrêté")

if __name__ == '__main__':
    main()