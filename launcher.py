"""
LAUNCHER MULTI-BOTS - Version Professionnelle
Gère plusieurs bots Telegram en parallèle avec support UptimeRobot
"""
import logging
import os
import sys
import signal
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time
from datetime import datetime
from typing import Dict, Optional, Callable

# ============================================================================
# ⚙️ CONFIGURATION LOGGING
# ============================================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("launcher")

# ============================================================================
# 📊 ÉTAT GLOBAL DES BOTS
# ============================================================================

class BotStatus:
    """Classe pour suivre l'état des bots"""
    
    def __init__(self):
        self.bots: Dict[str, dict] = {}
        self.start_time: datetime = datetime.now()
        self.lock = threading.Lock()
    
    def register_bot(self, name: str):
        """Enregistre un bot"""
        with self.lock:
            self.bots[name] = {
                "status": "starting",
                "started_at": None,
                "last_heartbeat": None,
                "errors": 0
            }
    
    def set_running(self, name: str):
        """Marque un bot comme actif"""
        with self.lock:
            if name in self.bots:
                self.bots[name]["status"] = "running"
                self.bots[name]["started_at"] = datetime.now()
                self.bots[name]["last_heartbeat"] = datetime.now()
    
    def set_error(self, name: str, error: str = None):
        """Marque un bot en erreur"""
        with self.lock:
            if name in self.bots:
                self.bots[name]["status"] = "error"
                self.bots[name]["errors"] += 1
    
    def heartbeat(self, name: str):
        """Met à jour le heartbeat d'un bot"""
        with self.lock:
            if name in self.bots:
                self.bots[name]["last_heartbeat"] = datetime.now()
    
    def get_status(self) -> dict:
        """Retourne l'état complet"""
        with self.lock:
            uptime = (datetime.now() - self.start_time).total_seconds()
            return {
                "status": "healthy",
                "uptime_seconds": int(uptime),
                "uptime_human": self._format_uptime(uptime),
                "bots": {
                    name: {
                        "status": info["status"],
                        "uptime": self._format_uptime(
                            (datetime.now() - info["started_at"]).total_seconds()
                        ) if info["started_at"] else "N/A",
                        "errors": info["errors"]
                    }
                    for name, info in self.bots.items()
                }
            }
    
    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """Formate l'uptime en string lisible"""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

# Instance globale
bot_status = BotStatus()

# ============================================================================
# 🌐 SERVEUR HTTP (HEALTH CHECK POUR RENDER + UPTIMEROBOT)
# ============================================================================

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Gestionnaire HTTP pour health check et UptimeRobot"""
    
    def do_GET(self):
        """Gère les requêtes GET"""
        if self.path in ['/', '/health', '/ping', '/status']:
            self._send_health_response()
        elif self.path == '/stats':
            self._send_stats_response()
        else:
            self._send_404()
    
    def do_HEAD(self):
        """Gère les requêtes HEAD (utilisé par certains moniteurs)"""
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
    
    def _send_health_response(self):
        """Envoie la réponse de health check"""
        status = bot_status.get_status()
        
        response = (
            f"✅ Multi-Bot Server Running\n"
            f"⏱️ Uptime: {status['uptime_human']}\n"
            f"🤖 Bots: {len(status['bots'])}\n"
        )
        
        for name, info in status['bots'].items():
            emoji = "🟢" if info['status'] == "running" else "🔴"
            response += f"   {emoji} {name}: {info['status']}\n"
        
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.send_header('X-Bot-Status', 'healthy')
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))
    
    def _send_stats_response(self):
        """Envoie les statistiques en JSON"""
        import json
        status = bot_status.get_status()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(status, indent=2).encode('utf-8'))
    
    def _send_404(self):
        """Envoie une erreur 404"""
        self.send_response(404)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Not Found')
    
    def log_message(self, format, *args):
        """Désactive les logs HTTP sauf erreurs"""
        if args and '200' not in str(args[0]):
            logger.debug(f"HTTP: {args}")


class HTTPServerThread(threading.Thread):
    """Thread pour le serveur HTTP"""
    
    def __init__(self, port: int = 8080):
        super().__init__(name="HTTPServer", daemon=True)
        self.port = port
        self.server: Optional[HTTPServer] = None
        self._stop_event = threading.Event()
    
    def run(self):
        """Démarre le serveur HTTP"""
        try:
            self.server = HTTPServer(('0.0.0.0', self.port), HealthCheckHandler)
            self.server.timeout = 1  # Timeout pour pouvoir arrêter proprement
            logger.info(f"🌐 Serveur HTTP démarré sur le port {self.port}")
            logger.info(f"   📍 Endpoints: /health, /ping, /status, /stats")
            
            while not self._stop_event.is_set():
                self.server.handle_request()
                
        except Exception as e:
            logger.error(f"❌ Erreur serveur HTTP: {e}")
    
    def stop(self):
        """Arrête le serveur HTTP"""
        self._stop_event.set()
        if self.server:
            try:
                self.server.server_close()
                logger.info("✅ Serveur HTTP arrêté")
            except Exception as e:
                logger.error(f"❌ Erreur arrêt serveur HTTP: {e}")

# ============================================================================
# 🤖 GESTIONNAIRE DE BOTS
# ============================================================================

class BotRunner(threading.Thread):
    """Thread pour exécuter un bot Telegram"""
    
    def __init__(self, name: str, module_name: str):
        super().__init__(name=name, daemon=False)
        self.bot_name = name
        self.module_name = module_name
        self._stop_event = threading.Event()
    
    def run(self):
        """Exécute le bot dans son propre thread avec sa propre boucle asyncio"""
        try:
            logger.info(f"🚀 Démarrage de {self.bot_name}...")
            bot_status.register_bot(self.bot_name)
            
            # IMPORTANT: Créer une nouvelle boucle d'événements pour ce thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Import dynamique du module
                module = __import__(self.module_name)
                
                # Vérifier si le module a une fonction main_async
                if hasattr(module, 'main_async'):
                    # Version async (préférée)
                    loop.run_until_complete(module.main_async())
                elif hasattr(module, 'main'):
                    # Version sync (sera convertie en async)
                    module.main()
                else:
                    logger.error(f"❌ {self.bot_name}: Pas de fonction main() trouvée")
                    bot_status.set_error(self.bot_name)
                    return
                
                bot_status.set_running(self.bot_name)
                
            except Exception as e:
                logger.error(f"❌ Erreur {self.bot_name}: {e}")
                import traceback
                traceback.print_exc()
                bot_status.set_error(self.bot_name, str(e))
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"❌ Erreur fatale {self.bot_name}: {e}")
            bot_status.set_error(self.bot_name, str(e))
    
    def stop(self):
        """Demande l'arrêt du bot"""
        self._stop_event.set()

# ============================================================================
# 🔄 AUTO-PING INTERNE (BACKUP UPTIMEROBOT)
# ============================================================================

class SelfPinger(threading.Thread):
    """Thread qui ping le serveur local pour le garder actif"""
    
    def __init__(self, port: int = 8080, interval: int = 300):
        super().__init__(name="SelfPinger", daemon=True)
        self.port = port
        self.interval = interval  # 5 minutes par défaut
        self._stop_event = threading.Event()
    
    def run(self):
        """Ping périodique du serveur local"""
        import urllib.request
        
        logger.info(f"🔄 Auto-ping activé (interval: {self.interval}s)")
        
        while not self._stop_event.is_set():
            try:
                url = f"http://localhost:{self.port}/health"
                with urllib.request.urlopen(url, timeout=10) as response:
                    if response.status == 200:
                        logger.debug("🔄 Auto-ping OK")
            except Exception as e:
                logger.warning(f"⚠️ Auto-ping échoué: {e}")
            
            # Attendre avant le prochain ping
            self._stop_event.wait(self.interval)
    
    def stop(self):
        """Arrête le pinger"""
        self._stop_event.set()

# ============================================================================
# 📦 GESTIONNAIRE DE BACKUP
# ============================================================================

def init_backup():
    """Initialise et restaure les données depuis le backup"""
    try:
        from backup_manager import backup_manager
        logger.info("📦 Restauration des données depuis le backup...")
        if backup_manager.restore_all_bots():
            logger.info("✅ Données restaurées avec succès")
            return True
        else:
            logger.info("ℹ️ Démarrage avec des données vides")
            return False
    except ImportError:
        logger.warning("⚠️ Module backup_manager non trouvé")
        return False
    except Exception as e:
        logger.warning(f"⚠️ Impossible de restaurer le backup: {e}")
        return False


def save_backup():
    """Sauvegarde les données vers le backup"""
    try:
        from backup_manager import backup_manager
        logger.info("💾 Sauvegarde des données...")
        if backup_manager.backup_all_bots():
            logger.info("✅ Données sauvegardées")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde: {e}")
        return False

# ============================================================================
# 🚦 SIGNAL HANDLER
# ============================================================================

shutdown_event = threading.Event()

def signal_handler(signum, frame):
    """Gère les signaux d'arrêt proprement"""
    signal_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else signum
    logger.info(f"⚠️ Signal {signal_name} reçu - Arrêt en cours...")
    shutdown_event.set()

# ============================================================================
# 🚀 MAIN LAUNCHER
# ============================================================================

def main():
    """Lance tous les bots en parallèle"""
    
    logger.info("=" * 70)
    logger.info("🚀 MULTI-BOT LAUNCHER v2.0 - DÉMARRAGE")
    logger.info("=" * 70)
    logger.info("")
    
    # Créer les dossiers de données
    os.makedirs("data/footbot", exist_ok=True)
    os.makedirs("data/sexbot", exist_ok=True)
    os.makedirs("data/shared", exist_ok=True)
    logger.info("📁 Dossiers de données créés")
    
    # Restaurer les données depuis le backup
    init_backup()
    
    # Configuration des bots
    bots_config = []
    
    # Vérifier FootBot
    footbot_token = os.environ.get("FOOTBOT_TOKEN", "").strip()
    if footbot_token and len(footbot_token) > 20:
        logger.info("📋 Bot #1: ⚽ FootBot - Token OK")
        bots_config.append(("FootBot", "footbot"))
    else:
        logger.warning("⚠️ FOOTBOT_TOKEN manquant ou invalide - FootBot désactivé")
    
    # Vérifier SexBot
    sexbot_token = os.environ.get("SEXBOT_TOKEN", "").strip()
    if sexbot_token and len(sexbot_token) > 20:
        logger.info("📋 Bot #2: 🔞 SexBot - Token OK")
        bots_config.append(("SexBot", "sexbot"))
    else:
        logger.warning("⚠️ SEXBOT_TOKEN manquant ou invalide - SexBot désactivé")
    
    # Vérifier qu'au moins un bot est configuré
    if not bots_config:
        logger.error("❌ Aucun token configuré!")
        logger.error("💡 Ajoutez FOOTBOT_TOKEN et/ou SEXBOT_TOKEN")
        sys.exit(1)
    
    logger.info("")
    logger.info(f"🤖 {len(bots_config)} bot(s) à démarrer")
    logger.info("=" * 70)
    logger.info("")
    
    # Démarrer le serveur HTTP
    port = int(os.environ.get('PORT', 8080))
    http_server = HTTPServerThread(port=port)
    http_server.start()
    
    # Démarrer l'auto-pinger (backup pour UptimeRobot)
    ping_interval = int(os.environ.get('PING_INTERVAL', 300))
    self_pinger = SelfPinger(port=port, interval=ping_interval)
    self_pinger.start()
    
    # Lancer les bots
    bot_threads = []
    for bot_name, module_name in bots_config:
        runner = BotRunner(bot_name, module_name)
        runner.start()
        bot_threads.append(runner)
        time.sleep(2)  # Délai entre chaque bot pour éviter les conflits
    
    logger.info("")
    logger.info("✅ Tous les bots démarrés")
    logger.info("=" * 70)
    logger.info("")
    logger.info("📡 UptimeRobot Configuration:")
    logger.info(f"   URL: https://votre-app.onrender.com/health")
    logger.info(f"   Interval: 5 minutes recommandé")
    logger.info("")
    
    try:
        # Attendre que tous les threads se terminent ou signal d'arrêt
        while not shutdown_event.is_set():
            # Vérifier si tous les bots sont encore actifs
            alive_bots = [t for t in bot_threads if t.is_alive()]
            
            if not alive_bots:
                logger.warning("⚠️ Tous les bots se sont arrêtés!")
                break
            
            # Heartbeat
            for t in alive_bots:
                bot_status.heartbeat(t.bot_name)
            
            shutdown_event.wait(timeout=30)
            
    except KeyboardInterrupt:
        logger.info("⚠️ Arrêt demandé (Ctrl+C)")
        shutdown_event.set()
        
    finally:
        logger.info("")
        logger.info("🛑 Arrêt en cours...")
        
        # Sauvegarder les données
        save_backup()
        
        # Arrêter le pinger
        self_pinger.stop()
        
        # Arrêter le serveur HTTP
        http_server.stop()
        
        # Attendre l'arrêt des bots
        for thread in bot_threads:
            thread.join(timeout=5)
        
        logger.info("✅ Tous les services arrêtés proprement")
        logger.info("👋 Launcher terminé")

# ============================================================================
# 🎯 POINT D'ENTRÉE
# ============================================================================

if __name__ == '__main__':
    # Configurer les gestionnaires de signaux
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Arrêt propre du launcher")
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)