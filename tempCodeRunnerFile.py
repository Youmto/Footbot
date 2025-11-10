import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import TelegramError
import json
import os
from datetime import datetime, timedelta
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re

# Configuration
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ⚠️ CONFIGURATION À REMPLIR
BOT_TOKEN = "8528649034:AAFCz7vV3-YDPq0UVlgkBws-5zG8EQ13vCs"
ADMIN_IDS = [5854095196]
CHANNEL_USERNAME = "@BetSmart Community FR 📊"
CHANNEL_ID = -1002415523895
REQUIRED_CHANNEL = "https://t.me/+mh1Ps_HZdQkzYjk0"

# Configuration du scraping automatique
STREAM_SOURCES = [
    # Ajoutez vos sources ici - le bot les scrapera automatiquement
    # Format: {"url": "https://site.com", "type": "iframe", "update_interval": 300}
]

# Stockage
DATA_FILE = "matches_data.json"
FAVORITES_FILE = "favorites_data.json"
NOTIFICATIONS_FILE = "notifications_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"matches": [], "sources": [], "last_update": None}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_favorites(favorites):
    with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
        json.dump(favorites, f, indent=2)

def load_notifications():
    if os.path.exists(NOTIFICATIONS_FILE):
        with open(NOTIFICATIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_notifications(notifications):
    with open(NOTIFICATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(notifications, f, indent=2)

class StreamScraper:
    """Classe pour scraper automatiquement les sites de streaming"""
    
    @staticmethod
    async def fetch_page(url):
        """Récupère le contenu d'une page"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    return await response.text()
        except Exception as e:
            logger.error(f"Erreur fetch {url}: {e}")
            return None
    
    @staticmethod
    def extract_matches_generic(html, source_url):
        """Extraction générique des matchs depuis HTML"""
        matches = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Patterns communs pour détecter les matchs
        patterns = [
            r'(\w+)\s+vs\s+(\w+)',
            r'(\w+)\s+-\s+(\w+)',
            r'(\w+)\s+x\s+(\w+)',
        ]
        
        # Chercher les iframes (lecteurs vidéo)
        iframes = soup.find_all('iframe')
        links = soup.find_all('a', href=True)
        
        # Extraire les matchs depuis les liens
        for link in links:
            text = link.get_text(strip=True)
            href = link['href']
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    team1, team2 = match.groups()
                    
                    # Construire l'URL complète
                    if not href.startswith('http'):
                        from urllib.parse import urljoin
                        href = urljoin(source_url, href)
                    
                    match_data = {
                        'id': f"{team1}_{team2}_{datetime.now().timestamp()}",
                        'team1': team1.strip(),
                        'team2': team2.strip(),
                        'status': 'live',
                        'stream_url': href,
                        'source': source_url,
                        'competition': 'À déterminer',
                        'quality': ['HD', 'SD'],
                        'extracted_at': datetime.now().isoformat()
                    }
                    matches.append(match_data)
        
        # Chercher dans les iframes
        for iframe in iframes:
            src = iframe.get('src', '')
            if src and ('stream' in src.lower() or 'player' in src.lower()):
                # Essayer de trouver le titre du match dans les éléments parents
                parent_text = iframe.find_parent().get_text(strip=True) if iframe.find_parent() else ''
                
                for pattern in patterns:
                    match = re.search(pattern, parent_text, re.IGNORECASE)
                    if match:
                        team1, team2 = match.groups()
                        
                        if not src.startswith('http'):
                            from urllib.parse import urljoin
                            src = urljoin(source_url, src)
                        
                        match_data = {
                            'id': f"{team1}_{team2}_{datetime.now().timestamp()}",
                            'team1': team1.strip(),
                            'team2': team2.strip(),
                            'status': 'live',
                            'stream_url': src,
                            'source': source_url,
                            'competition': 'À déterminer',
                            'quality': ['HD', 'SD'],
                            'extracted_at': datetime.now().isoformat()
                        }
                        matches.append(match_data)
        
        return matches
    
    @staticmethod
    async def scrape_source(source):
        """Scrape une source spécifique"""
        url = source['url']
        logger.info(f"🔄 Scraping: {url}")
        
        html = await StreamScraper.fetch_page(url)
        if not html:
            return []
        
        matches = StreamScraper.extract_matches_generic(html, url)
        logger.info(f"✅ Trouvé {len(matches)} matchs sur {url}")
        
        return matches
    
    @staticmethod
    async def auto_update_matches():
        """Met à jour automatiquement les matchs depuis toutes les sources"""
        data = load_data()
        all_matches = []
        
        for source in data['sources']:
            try:
                matches = await StreamScraper.scrape_source(source)
                all_matches.extend(matches)
            except Exception as e:
                logger.error(f"Erreur scraping {source['url']}: {e}")
        
        # Supprimer les doublons basés sur les équipes
        unique_matches = []
        seen = set()
        
        for match in all_matches:
            key = f"{match['team1']}_{match['team2']}"
            if key not in seen:
                seen.add(key)
                unique_matches.append(match)
        
        # Mettre à jour les données
        data['matches'] = unique_matches
        data['last_update'] = datetime.now().isoformat()
        save_data(data)
        
        logger.info(f"📊 Mise à jour terminée: {len(unique_matches)} matchs uniques")
        return len(unique_matches)

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except TelegramError:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    is_subscribed = await check_subscription(user_id, context)
    
    if not is_subscribed:
        keyboard = [
            [InlineKeyboardButton("⚽ Rejoindre le Canal", url=REQUIRED_CHANNEL)],
            [InlineKeyboardButton("✅ J'ai rejoint", callback_data="check_subscription")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            f"⚽ <b>Bienvenue sur Football Stream Pro</b> ⚽\n\n"
            f"👋 Salut {user.first_name}!\n\n"
            f"🔒 Pour accéder aux matchs en streaming HD, rejoignez notre canal:\n\n"
            f"🎯 <b>Fonctionnalités:</b>\n"
            f"• 📺 Matchs en direct automatiques\n"
            f"• 🔔 Notifications avant les matchs\n"
            f"• ⭐ Système de favoris\n"
            f"• 📊 Statistiques en temps réel\n"
            f"• 🎬 Qualité vidéo multiple (HD/SD)\n\n"
            f"👇 Cliquez ci-dessous:"
        )
        
        await update.message.reply_text(welcome_text, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Charger les stats
    data = load_data()
    live_count = len([m for m in data['matches'] if m.get('status') == 'live'])
    
    keyboard = [
        [InlineKeyboardButton(f"🔴 Matchs en Direct ({live_count})", callback_data="live_matches")],
        [InlineKeyboardButton("📅 Matchs à Venir", callback_data="upcoming_matches")],
        [
            InlineKeyboardButton("⭐ Mes Favoris", callback_data="my_favorites"),
            InlineKeyboardButton("🔔 Notifications", callback_data="notifications_menu")
        ],
        [InlineKeyboardButton("🏆 Compétitions", callback_data="competitions")],
        [InlineKeyboardButton("📊 Statistiques", callback_data="user_stats")]
    ]
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ Panel Admin", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    last_update = data.get('last_update')
    update_time = "Jamais" if not last_update else datetime.fromisoformat(last_update).strftime("%H:%M")
    
    menu_text = (
        "⚽ <b>FOOTBALL STREAM PRO</b> ⚽\n\n"
        f"🎯 <b>{live_count} matchs en direct</b>\n"
        f"🔄 Dernière MAJ: {update_time}\n\n"
        f"📺 Choisissez une option:\n"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(menu_text, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await update.message.reply_text(menu_text, parse_mode='HTML', reply_markup=reply_markup)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    sources_count = len(data['sources'])
    matches_count = len(data['matches'])
    
    keyboard = [
        [InlineKeyboardButton("🔗 Ajouter Source Auto", callback_data="admin_add_source")],
        [InlineKeyboardButton("📋 Gérer Sources", callback_data="admin_manage_sources")],
        [InlineKeyboardButton("🔄 Forcer Mise à Jour", callback_data="admin_force_update")],
        [InlineKeyboardButton("➕ Ajouter Match Manuel", callback_data="admin_add_match")],
        [InlineKeyboardButton("📊 Statistiques Admin", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Retour", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    admin_text = (
        "⚙️ <b>PANEL ADMINISTRATEUR</b>\n\n"
        f"📊 <b>État actuel:</b>\n"
        f"• Sources actives: {sources_count}\n"
        f"• Matchs détectés: {matches_count}\n\n"
        f"🎮 <b>Actions disponibles:</b>\n"
        f"• Ajouter des sources de streaming\n"
        f"• Gérer les sources existantes\n"
        f"• Forcer une mise à jour manuelle\n"
        f"• Ajouter des matchs manuellement\n"
    )
    
    await query.edit_message_text(admin_text, parse_mode='HTML', reply_markup=reply_markup)

async def admin_add_source_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔗 <b>Ajouter Source Automatique</b>\n\n"
        "📡 Envoyez simplement l'URL du site de streaming:\n\n"
        "<b>Exemple:</b>\n"
        "<code>https://votresite-stream.com</code>\n\n"
        "Le bot va automatiquement:\n"
        "✅ Détecter tous les matchs disponibles\n"
        "✅ Extraire les liens de streaming\n"
        "✅ Mettre à jour toutes les 5 minutes\n"
        "✅ Ajouter les matchs au bot\n\n"
        "<i>Compatible avec la plupart des sites de streaming populaires!</i>\n\n"
        "Ou tapez /cancel pour annuler",
        parse_mode='HTML'
    )
    
    context.user_data['adding_source'] = True

async def admin_manage_sources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    sources = data['sources']
    
    if not sources:
        keyboard = [
            [InlineKeyboardButton("🔗 Ajouter une Source", callback_data="admin_add_source")],
            [InlineKeyboardButton("🔙 Retour", callback_data="admin_panel")]
        ]
        await query.edit_message_text(
            "📋 <b>Gestion des Sources</b>\n\n"
            "❌ Aucune source configurée.\n\n"
            "Ajoutez votre première source de streaming!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    keyboard = []
    for i, source in enumerate(sources):
        url_short = source['url'][:30] + "..." if len(source['url']) > 30 else source['url']
        keyboard.append([
            InlineKeyboardButton(f"🔗 {url_short}", callback_data=f"view_source_{i}"),
            InlineKeyboardButton("🗑️", callback_data=f"delete_source_{i}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Retour", callback_data="admin_panel")])
    
    sources_text = (
        "📋 <b>Sources Actives</b>\n\n"
        f"📊 Total: {len(sources)} source(s)\n\n"
        "Cliquez sur une source pour voir les détails\n"
        "ou sur 🗑️ pour la supprimer:"
    )
    
    await query.edit_message_text(sources_text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_force_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔄 Mise à jour en cours...")
    
    await query.edit_message_text("⏳ <b>Mise à jour en cours...</b>\n\nVeuillez patienter...", parse_mode='HTML')
    
    try:
        matches_count = await StreamScraper.auto_update_matches()
        
        keyboard = [[InlineKeyboardButton("🔙 Retour Admin", callback_data="admin_panel")]]
        
        await query.edit_message_text(
            f"✅ <b>Mise à jour terminée!</b>\n\n"
            f"📊 <b>Résultat:</b>\n"
            f"• Matchs détectés: {matches_count}\n"
            f"• Heure: {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"Les matchs sont maintenant visibles dans le bot!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        await query.edit_message_text(
            f"❌ <b>Erreur lors de la mise à jour</b>\n\n{str(e)}",
            parse_mode='HTML'
        )

async def show_live_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    live_matches = [m for m in data['matches'] if m.get('status') == 'live']
    
    if not live_matches:
        keyboard = [
            [InlineKeyboardButton("🔄 Actualiser", callback_data="live_matches")],
            [InlineKeyboardButton("🔙 Retour", callback_data="main_menu")]
        ]
        await query.edit_message_text(
            "📺 <b>Matchs en Direct</b>\n\n"
            "❌ Aucun match en direct pour le moment.\n\n"
            "💡 Les matchs sont détectés automatiquement.\n"
            "Revenez dans quelques minutes!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Charger les favoris de l'utilisateur
    favorites = load_favorites()
    user_favs = favorites.get(str(query.from_user.id), [])
    
    keyboard = []
    for match in live_matches[:15]:  # Limiter à 15 matchs
        is_fav = match['id'] in user_favs
        fav_icon = "⭐" if is_fav else "⚽"
        match_text = f"{fav_icon} {match['team1']} vs {match['team2']}"
        keyboard.append([InlineKeyboardButton(match_text, callback_data=f"watch_{match['id']}")])
    
    keyboard.append([
        InlineKeyboardButton("🔄 Actualiser", callback_data="live_matches"),
        InlineKeyboardButton("🔙 Menu", callback_data="main_menu")
    ])
    
    await query.edit_message_text(
        f"📺 <b>Matchs en Direct</b> 🔴\n\n"
        f"🎯 {len(live_matches)} match(s) disponible(s)\n"
        f"⭐ = Dans vos favoris\n\n"
        f"Cliquez sur un match pour le regarder:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def watch_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    match_id = query.data.split('_', 1)[1]
    data = load_data()
    
    match = next((m for m in data['matches'] if m['id'] == match_id), None)
    
    if not match:
        await query.edit_message_text("❌ Match non trouvé!")
        return
    
    # Vérifier si c'est un favori
    favorites = load_favorites()
    user_id = str(query.from_user.id)
    user_favs = favorites.get(user_id, [])
    is_favorite = match_id in user_favs
    
    # Boutons de qualité
    quality_buttons = []
    for quality in match.get('quality', ['HD']):
        quality_buttons.append(InlineKeyboardButton(f"📺 {quality}", callback_data=f"quality_{match_id}_{quality}"))
    
    keyboard = [
        quality_buttons,
        [InlineKeyboardButton("🌐 Ouvrir dans le navigateur", url=match['stream_url'])],
        [
            InlineKeyboardButton("⭐ Retirer des favoris" if is_favorite else "⭐ Ajouter aux favoris", 
                               callback_data=f"toggle_fav_{match_id}"),
            InlineKeyboardButton("🔔 Notif", callback_data=f"notify_{match_id}")
        ],
        [InlineKeyboardButton("🔙 Retour aux matchs", callback_data="live_matches")]
    ]
    
    match_text = (
        f"⚽ <b>{match['team1']} vs {match['team2']}</b>\n\n"
        f"🏆 {match.get('competition', 'Match en direct')}\n"
        f"🔴 <b>EN DIRECT</b>\n"
        f"📡 Source: {match.get('source', 'N/A')[:30]}...\n\n"
        f"🎬 <b>Qualités disponibles:</b>\n"
        f"{'• ' + ' • '.join(match.get('quality', ['HD']))}\n\n"
        f"👇 Choisissez une option pour regarder:"
    )
    
    await query.edit_message_text(
        match_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def toggle_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    match_id = query.data.split('_', 2)[2]
    user_id = str(query.from_user.id)
    
    favorites = load_favorites()
    user_favs = favorites.get(user_id, [])
    
    if match_id in user_favs:
        user_favs.remove(match_id)
        await query.answer("❌ Retiré des favoris")
    else:
        user_favs.append(match_id)
        await query.answer("⭐ Ajouté aux favoris!")
    
    favorites[user_id] = user_favs
    save_favorites(favorites)
    
    # Rafraîchir l'affichage
    context.match_data = {'data': f"watch_{match_id}"}
    await watch_match(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        return
    
    if context.user_data.get('adding_source'):
        url = update.message.text.strip()
        
        if not url.startswith('http'):
            await update.message.reply_text("❌ URL invalide. Elle doit commencer par http:// ou https://")
            return
        
        data = load_data()
        
        # Ajouter la source
        new_source = {
            'url': url,
            'added_at': datetime.now().isoformat(),
            'update_interval': 300  # 5 minutes
        }
        
        data['sources'].append(new_source)
        save_data(data)
        
        context.user_data['adding_source'] = False
        
        # Lancer immédiatement un scan
        await update.message.reply_text("⏳ <b>Analyse de la source...</b>", parse_mode='HTML')
        
        try:
            matches = await StreamScraper.scrape_source(new_source)
            
            # Ajouter les matchs trouvés
            data['matches'].extend(matches)
            save_data(data)
            
            await update.message.reply_text(
                f"✅ <b>Source ajoutée avec succès!</b>\n\n"
                f"🔗 {url}\n\n"
                f"📊 <b>Résultats:</b>\n"
                f"• Matchs détectés: {len(matches)}\n\n"
                f"🔄 La source sera scannée automatiquement toutes les 5 minutes.",
                parse_mode='HTML'
            )
        except Exception as e:
            await update.message.reply_text(
                f"⚠️ <b>Source ajoutée</b>\n\n"
                f"Mais erreur lors du premier scan: {str(e)}\n\n"
                f"La source sera retentée lors du prochain scan automatique.",
                parse_mode='HTML'
            )

async def auto_update_task(application):
    """Tâche de mise à jour automatique en arrière-plan"""
    while True:
        try:
            logger.info("🔄 Début de la mise à jour automatique...")
            await StreamScraper.auto_update_matches()
            logger.info("✅ Mise à jour automatique terminée")
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour auto: {e}")
        
        # Attendre 5 minutes
        await asyncio.sleep(300)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data != "check_subscription":
        is_subscribed = await check_subscription(query.from_user.id, context)
        if not is_subscribed:
            await query.answer("❌ Vous devez rejoindre le canal!", show_alert=True)
            return
    
    if data == "check_subscription":
        is_subscribed = await check_subscription(query.from_user.id, context)
        if is_subscribed:
            await query.answer("✅ Vérification réussie!")
            await show_main_menu(update, context)
        else:
            await query.answer("❌ Pas encore rejoint!", show_alert=True)
    
    elif data == "main_menu":
        await show_main_menu(update, context)
    
    elif data == "live_matches":
        await show_live_matches(update, context)
    
    elif data == "admin_panel":
        if query.from_user.id in ADMIN_IDS:
            await admin_panel(update, context)
    
    elif data == "admin_add_source":
        await admin_add_source_start(update, context)
    
    elif data == "admin_manage_sources":
        await admin_manage_sources(update, context)
    
    elif data == "admin_force_update":
        await admin_force_update(update, context)
    
    elif data.startswith("watch_"):
        await watch_match(update, context)
    
    elif data.startswith("toggle_fav_"):
        await toggle_favorite(update, context)
    
    elif data.startswith("delete_source_"):
        source_idx = int(data.split('_')[2])
        file_data = load_data()
        if 0 <= source_idx < len(file_data['sources']):
            removed = file_data['sources'].pop(source_idx)
            save_data(file_data)
            await query.answer(f"✅ Source supprimée!")
            await admin_manage_sources(update, context)

async def post_init(application):
    """Démarre les tâches en arrière-plan"""
    asyncio.create_task(auto_update_task(application))

def main():
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 Bot démarré avec scraping automatique!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()