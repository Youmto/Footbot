"""
LAUNCHER MULTI-BOTS
Gère plusieurs bots Telegram en parallèle
"""
import asyncio
import logging
import os
import sys
import signal
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Variables globales
http_server = None
running_tasks = []
shutdown_event = asyncio.Event()

# ============================================================================
# SERVEUR HTTP (HEALTH CHECK POUR RENDER)
# ============================================================================

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Gestionnaire HTTP simple pour le health check"""
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Multi-Bot Server Running OK')
    
    def log_message(self, format, *args):
        """Désactive les logs HTTP"""
        pass

def start_http_server():
    """Démarre le serveur HTTP en arrière-plan"""
    global http_server
    port = int(os.environ.get('PORT', 8080))
    
    try:
        http_server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        logger.info(f"🌐 Serveur HTTP démarré sur le port {port}")
        http_server.serve_forever()
    except Exception as e:
        logger.error(f"❌ Erreur serveur HTTP: {e}")

def stop_http_server():
    """Arrête le serveur HTTP proprement"""
    global http_server
    if http_server:
        try:
            http_server.shutdown()
            http_server.server_close()
            logger.info("✅ Serveur HTTP arrêté")
        except Exception as e:
            logger.error(f"❌ Erreur arrêt serveur HTTP: {e}")

# ============================================================================
# GESTION DES BOTS
# ============================================================================

async def run_footbot():
    """Lance le bot Football"""
    try:
        logger.info("⚽ Démarrage de FootBot...")
        
        # Import du module
        import footbot
        
        # Créer une task pour exécuter le bot
        loop = asyncio.get_event_loop()
        
        # Exécuter le main dans un thread séparé pour éviter les conflits d'event loop
        await loop.run_in_executor(None, footbot.main)
        
    except asyncio.CancelledError:
        logger.info("⚽ FootBot arrêté (cancelled)")
        raise
    except Exception as e:
        logger.error(f"❌ Erreur FootBot: {e}")
        raise

async def run_sexbot():
    """Lance le bot Sexbot"""
    try:
        logger.info("🔞 Démarrage de SexBot...")
        
        # Import du module
        import sexbot
        
        # Créer une task pour exécuter le bot
        loop = asyncio.get_event_loop()
        
        # Exécuter le main dans un thread séparé pour éviter les conflits d'event loop
        await loop.run_in_executor(None, sexbot.main)
        
    except asyncio.CancelledError:
        logger.info("🔞 SexBot arrêté (cancelled)")
        raise
    except Exception as e:
        logger.error(f"❌ Erreur SexBot: {e}")
        raise

# ============================================================================
# SIGNAL HANDLER
# ============================================================================

def signal_handler(signum, frame):
    """Gère les signaux d'arrêt proprement"""
    logger.info(f"⚠️ Signal {signum} reçu - Arrêt en cours...")
    
    # Marquer l'arrêt
    shutdown_event.set()
    
    # Annuler toutes les tâches en cours
    for task in running_tasks:
        if not task.done():
            task.cancel()
    
    # Arrêter le serveur HTTP
    stop_http_server()

# ============================================================================
# MAIN LAUNCHER
# ============================================================================

async def main():
    """Lance tous les bots en parallèle"""
    global running_tasks
    
    logger.info("=" * 70)
    logger.info("🚀 MULTI-BOT LAUNCHER - DÉMARRAGE")
    logger.info("=" * 70)
    
    # Créer les dossiers de données
    os.makedirs("data/footbot", exist_ok=True)
    os.makedirs("data/sexbot", exist_ok=True)
    os.makedirs("data/shared", exist_ok=True)
    logger.info("✅ Dossiers de données créés")
    
    # Vérification des tokens
    footbot_token = os.environ.get("FOOTBOT_TOKEN", "")
    sexbot_token = os.environ.get("SEXBOT_TOKEN", "")
    
    bots_to_run = []
    
    # Vérifier FootBot
    if footbot_token and len(footbot_token) > 20:
        logger.info("📋 Bot #1: ⚽ FootBot - Activé")
        bots_to_run.append(("FootBot", run_footbot()))
    else:
        logger.warning("⚠️ FOOTBOT_TOKEN manquant - FootBot désactivé")
    
    # Vérifier SexBot
    if sexbot_token and len(sexbot_token) > 20:
        logger.info("📋 Bot #2: 🔞 SexBot - Activé")
        bots_to_run.append(("SexBot", run_sexbot()))
    else:
        logger.warning("⚠️ SEXBOT_TOKEN manquant - SexBot désactivé")
    
    # Vérifier qu'au moins un bot est configuré
    if not bots_to_run:
        logger.error("❌ Aucun token configuré!")
        logger.error("💡 Ajoutez FOOTBOT_TOKEN et/ou SEXBOT_TOKEN dans les variables d'environnement")
        return
    
    logger.info("")
    logger.info(f"🤖 {len(bots_to_run)} bot(s) configuré(s)")
    logger.info("=" * 70)
    logger.info("")
    
    # Démarrer le serveur HTTP en arrière-plan
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    logger.info("✅ Serveur HTTP lancé en arrière-plan")
    logger.info("")
    
    # Créer les tâches pour chaque bot
    for bot_name, bot_coro in bots_to_run:
        task = asyncio.create_task(bot_coro)
        running_tasks.append(task)
    
    try:
        # Attendre que toutes les tâches se terminent
        await asyncio.gather(*running_tasks, return_exceptions=True)
        
    except asyncio.CancelledError:
        logger.info("⚠️ Arrêt demandé")
        
    except Exception as e:
        logger.error(f"❌ Erreur critique: {e}")
        
    finally:
        # Annuler toutes les tâches restantes
        logger.info("🛑 Arrêt de tous les bots...")
        
        for task in running_tasks:
            if not task.done():
                task.cancel()
        
        # Attendre que toutes les tâches soient bien annulées
        await asyncio.gather(*running_tasks, return_exceptions=True)
        
        # Arrêter le serveur HTTP
        stop_http_server()
        
        logger.info("✅ Tous les bots arrêtés proprement")

# ============================================================================
# POINT D'ENTRÉE
# ============================================================================

if __name__ == '__main__':
    # Configurer les gestionnaires de signaux
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Lancer l'event loop asyncio
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("👋 Arrêt propre du launcher (Ctrl+C)")
        
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        sys.exit(1)
        
    finally:
        logger.info("👋 Launcher terminé")