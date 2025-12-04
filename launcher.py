"""
LAUNCHER MULTI-BOTS
Gère plusieurs bots Telegram en parallèle
"""
import logging
import os
import sys
import signal
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Variables globales
http_server = None
bot_threads = []
shutdown_flag = threading.Event()

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

def run_footbot():
    """Lance le bot Football dans un thread"""
    try:
        logger.info("⚽ Démarrage de FootBot...")
        
        # Import et lancement
        import footbot
        footbot.main()
        
    except KeyboardInterrupt:
        logger.info("⚽ FootBot arrêté (interrupt)")
    except Exception as e:
        logger.error(f"❌ Erreur FootBot: {e}")
        import traceback
        traceback.print_exc()

def run_sexbot():
    """Lance le bot Sexbot dans un thread"""
    try:
        logger.info("🔞 Démarrage de SexBot...")
        
        # Import et lancement
        import sexbot
        sexbot.main()
        
    except KeyboardInterrupt:
        logger.info("🔞 SexBot arrêté (interrupt)")
    except Exception as e:
        logger.error(f"❌ Erreur SexBot: {e}")
        import traceback
        traceback.print_exc()

# ============================================================================
# SIGNAL HANDLER
# ============================================================================

def signal_handler(signum, frame):
    """Gère les signaux d'arrêt proprement"""
    logger.info(f"⚠️ Signal {signum} reçu - Arrêt en cours...")
    shutdown_flag.set()
    stop_http_server()
    sys.exit(0)

# ============================================================================
# MAIN LAUNCHER
# ============================================================================

def main():
    """Lance tous les bots en parallèle"""
    global bot_threads
    
    logger.info("=" * 70)
    logger.info("🚀 MULTI-BOT LAUNCHER - DÉMARRAGE")
    logger.info("=" * 70)
    
    # Créer les dossiers de données
    os.makedirs("data/footbot", exist_ok=True)
    os.makedirs("data/sexbot", exist_ok=True)
    os.makedirs("data/shared", exist_ok=True)
    logger.info("✅ Dossiers de données créés")
    
    # Restaurer les données depuis le backup
    try:
        from backup_manager import backup_manager
        logger.info("📦 Restauration des données depuis le backup...")
        if backup_manager.restore_all_bots():
            logger.info("✅ Données restaurées avec succès")
        else:
            logger.info("ℹ️ Démarrage avec des données vides")
    except Exception as e:
        logger.warning(f"⚠️ Impossible de restaurer le backup: {e}")
    
    # Vérification des tokens
    footbot_token = os.environ.get("FOOTBOT_TOKEN", "")
    sexbot_token = os.environ.get("SEXBOT_TOKEN", "")
    
    bots_to_run = []
    
    # Vérifier FootBot
    if footbot_token and len(footbot_token) > 20:
        logger.info("📋 Bot #1: ⚽ FootBot - Activé")
        bots_to_run.append(("FootBot", run_footbot))
    else:
        logger.warning("⚠️ FOOTBOT_TOKEN manquant - FootBot désactivé")
    
    # Vérifier SexBot
    if sexbot_token and len(sexbot_token) > 20:
        logger.info("📋 Bot #2: 🔞 SexBot - Activé")
        bots_to_run.append(("SexBot", run_sexbot))
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
    http_thread = threading.Thread(target=start_http_server, daemon=True, name="HTTPServer")
    http_thread.start()
    logger.info("✅ Serveur HTTP lancé en arrière-plan")
    logger.info("")
    
    # Lancer chaque bot dans son propre thread
    for bot_name, bot_func in bots_to_run:
        thread = threading.Thread(target=bot_func, daemon=False, name=bot_name)
        thread.start()
        bot_threads.append(thread)
        time.sleep(2)  # Petit délai entre chaque bot
    
    try:
        # Attendre que tous les threads se terminent
        for thread in bot_threads:
            thread.join()
        
    except KeyboardInterrupt:
        logger.info("⚠️ Arrêt demandé (Ctrl+C)")
        
    finally:
        # Sauvegarder les données
        logger.info("💾 Sauvegarde des données...")
        try:
            from backup_manager import backup_manager
            if backup_manager.backup_all_bots():
                logger.info("✅ Données sauvegardées")
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde: {e}")
        
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
        main()
        
    except KeyboardInterrupt:
        logger.info("👋 Arrêt propre du launcher (Ctrl+C)")
        
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        logger.info("👋 Launcher terminé")