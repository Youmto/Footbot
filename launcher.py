"""
LAUNCHER MULTI-BOTS v2.1 - Version Professionnelle
Gère plusieurs bots Telegram en parallèle avec:
- Restauration au démarrage
- Sauvegarde à l'arrêt/redéploiement
- Backup automatique périodique
- Support UptimeRobot
"""
import logging
import os
import sys
import signal
import asyncio
import atexit
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time
from datetime import datetime
from typing import Dict, Optional

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
        with self.lock:
            self.bots[name] = {
                "status": "starting",
                "started_at": None,
                "last_heartbeat": None,
                "errors": 0
            }
    
    def set_running(self, name: str):
        with self.lock:
            if name in self.bots:
                self.bots[name]["status"] = "running"
                self.bots[name]["started_at"] = datetime.now()
                self.bots[name]["last_heartbeat"] = datetime.now()
    
    def set_error(self, name: str, error: str = None):
        with self.lock:
            if name in self.bots:
                self.bots[name]["status"] = "error"
                self.bots[name]["errors"] += 1
    
    def heartbeat(self, name: str):
        with self.lock:
            if name in self.bots:
                self.bots[name]["last_heartbeat"] = datetime.now()
    
    def get_status(self) -> dict:
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
# 🌐 SERVEUR HTTP (HEALTH CHECK + UPTIMEROBOT)
# ============================================================================

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Gestionnaire HTTP pour health check et UptimeRobot"""
    
    def do_GET(self):
        if self.path in ['/', '/health', '/ping', '/status']:
            self._send_health_response()
        elif self.path == '/stats':
            self._send_stats_response()
        elif self.path == '/backup':
            self._trigger_backup()
        else:
            self._send_404()
    
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
    
    def _send_health_response(self):
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
        import json
        status = bot_status.get_status()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(status, indent=2).encode('utf-8'))
    
    def _trigger_backup(self):
        """Endpoint pour déclencher un backup manuel"""
        try:
            from backup_manager import backup_manager
            success = backup_manager.backup_all_bots()
            
            if success:
                response = "✅ Backup effectué avec succès"
                self.send_response(200)
            else:
                response = "⚠️ Backup échoué ou désactivé"
                self.send_response(500)
        except Exception as e:
            response = f"❌ Erreur: {str(e)}"
            self.send_response(500)
        
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))
    
    def _send_404(self):
        self.send_response(404)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Not Found')
    
    def log_message(self, format, *args):
        pass


class HTTPServerThread(threading.Thread):
    """Thread pour le serveur HTTP"""
    
    def __init__(self, port: int = 8080):
        super().__init__(name="HTTPServer", daemon=True)
        self.port = port
        self.server: Optional[HTTPServer] = None
        self._stop_event = threading.Event()
    
    def run(self):
        try:
            self.server = HTTPServer(('0.0.0.0', self.port), HealthCheckHandler)
            self.server.timeout = 1
            logger.info(f"🌐 Serveur HTTP démarré sur le port {self.port}")
            logger.info(f"   📍 Endpoints: /health, /ping, /status, /stats, /backup")
            
            while not self._stop_event.is_set():
                self.server.handle_request()
                
        except Exception as e:
            logger.error(f"❌ Erreur serveur HTTP: {e}")
    
    def stop(self):
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
        try:
            logger.info(f"🚀 Démarrage de {self.bot_name}...")
            bot_status.register_bot(self.bot_name)
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                module = __import__(self.module_name)
                
                if hasattr(module, 'main_async'):
                    loop.run_until_complete(module.main_async())
                elif hasattr(module, 'main'):
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
        self._stop_event.set()

# ============================================================================
# 🔄 AUTO-PING INTERNE
# ============================================================================

class SelfPinger(threading.Thread):
    """Thread qui ping le serveur local pour le garder actif"""
    
    def __init__(self, port: int = 8080, interval: int = 300):
        super().__init__(name="SelfPinger", daemon=True)
        self.port = port
        self.interval = interval
        self._stop_event = threading.Event()
    
    def run(self):
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
            
            self._stop_event.wait(self.interval)
    
    def stop(self):
        self._stop_event.set()

# ============================================================================
# 💾 BACKUP AUTOMATIQUE PÉRIODIQUE
# ============================================================================

class AutoBackupThread(threading.Thread):
    """Thread pour backup automatique périodique"""
    
    def __init__(self, interval: int = 300):
        super().__init__(name="AutoBackup", daemon=True)
        self.interval = interval
        self._stop_event = threading.Event()
    
    def run(self):
        logger.info(f"💾 Auto-backup activé (interval: {self.interval}s)")
        
        self._stop_event.wait(60)
        
        while not self._stop_event.is_set():
            try:
                from backup_manager import backup_manager
                
                if backup_manager.enabled:
                    logger.info("💾 Backup automatique en cours...")
                    if backup_manager.backup_all_bots():
                        logger.info("✅ Backup automatique réussi")
                    else:
                        logger.debug("ℹ️ Backup: rien à sauvegarder")
                        
            except Exception as e:
                logger.error(f"❌ Erreur backup automatique: {e}")
            
            self._stop_event.wait(self.interval)
    
    def stop(self):
        self._stop_event.set()

# ============================================================================
# 📦 GESTIONNAIRE DE BACKUP
# ============================================================================

def init_backup():
    """Initialise et restaure les données depuis le backup AU DÉMARRAGE"""
    try:
        from backup_manager import backup_manager
        
        if not backup_manager.enabled:
            logger.warning("⚠️ Backup désactivé - Variables manquantes")
            logger.warning("   → GITHUB_BACKUP_TOKEN")
            logger.warning("   → GIST_BACKUP_ID")
            return False
        
        logger.info("")
        logger.info("=" * 50)
        logger.info("📦 RESTAURATION DES DONNÉES AU DÉMARRAGE")
        logger.info("=" * 50)
        
        if backup_manager.restore_all_bots():
            logger.info("✅ Données restaurées avec succès depuis GitHub Gist")
            return True
        else:
            logger.info("ℹ️ Aucune donnée à restaurer - Démarrage frais")
            return False
            
    except ImportError:
        logger.warning("⚠️ Module backup_manager non trouvé")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur restauration: {e}")
        return False


def save_backup():
    """Sauvegarde les données vers le backup À L'ARRÊT"""
    try:
        from backup_manager import backup_manager
        
        if not backup_manager.enabled:
            logger.warning("⚠️ Backup désactivé - Données NON sauvegardées!")
            return False
        
        logger.info("")
        logger.info("=" * 50)
        logger.info("💾 SAUVEGARDE DES DONNÉES AVANT ARRÊT")
        logger.info("=" * 50)
        
        if backup_manager.backup_all_bots():
            logger.info("✅ Données sauvegardées avec succès vers GitHub Gist")
            return True
        else:
            logger.warning("⚠️ Aucune donnée à sauvegarder")
            return False
            
    except Exception as e:
        logger.error(f"❌ ERREUR CRITIQUE - Données non sauvegardées: {e}")
        return False

# ============================================================================
# 🚦 SIGNAL HANDLERS - CRITIQUE POUR RENDER
# ============================================================================

shutdown_event = threading.Event()
shutdown_in_progress = False

def signal_handler(signum, frame):
    """Gestionnaire de signaux - Capture SIGTERM de Render"""
    global shutdown_in_progress
    
    if shutdown_in_progress:
        logger.warning("⚠️ Arrêt déjà en cours...")
        return
    
    shutdown_in_progress = True
    
    signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
    logger.info("")
    logger.info("=" * 50)
    logger.info(f"🚨 SIGNAL {signal_name} REÇU - ARRÊT EN COURS")
    logger.info("=" * 50)
    
    # ⭐ SAUVEGARDER IMMÉDIATEMENT AVANT TOUT
    save_backup()
    
    # Signaler l'arrêt
    shutdown_event.set()


def exit_handler():
    """Gestionnaire de sortie - Appelé par atexit"""
    global shutdown_in_progress
    
    if not shutdown_in_progress:
        logger.info("🔄 Exit handler - Sauvegarde finale...")
        save_backup()

# ============================================================================
# 🚀 MAIN LAUNCHER
# ============================================================================

def main():
    """Lance tous les bots en parallèle"""
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("🚀 MULTI-BOT LAUNCHER v2.1 - DÉMARRAGE")
    logger.info("=" * 70)
    logger.info("")
    
    # Créer les dossiers de données
    os.makedirs("data/footbot", exist_ok=True)
    os.makedirs("data/sexbot", exist_ok=True)
    os.makedirs("data/shared", exist_ok=True)
    logger.info("📁 Dossiers de données créés")
    
    # ⭐ RESTAURER LES DONNÉES AU DÉMARRAGE
    init_backup()
    
    # Configuration des bots
    bots_config = []
    
    footbot_token = os.environ.get("FOOTBOT_TOKEN", "").strip()
    if footbot_token and len(footbot_token) > 20:
        logger.info("✅ Bot #1: ⚽ FootBot - Token OK")
        bots_config.append(("FootBot", "footbot"))
    else:
        logger.warning("⚠️ FOOTBOT_TOKEN manquant ou invalide")
    
    sexbot_token = os.environ.get("SEXBOT_TOKEN", "").strip()
    if sexbot_token and len(sexbot_token) > 20:
        logger.info("✅ Bot #2: 🔞 SexBot - Token OK")
        bots_config.append(("SexBot", "sexbot"))
    else:
        logger.warning("⚠️ SEXBOT_TOKEN manquant ou invalide")
    
    if not bots_config:
        logger.error("❌ Aucun token configuré!")
        logger.error("💡 Ajoutez FOOTBOT_TOKEN et/ou SEXBOT_TOKEN")
        sys.exit(1)
    
    logger.info("")
    logger.info(f"🤖 {len(bots_config)} bot(s) à démarrer")
    logger.info("=" * 70)
    
    # Démarrer le serveur HTTP
    port = int(os.environ.get('PORT', 8080))
    http_server = HTTPServerThread(port=port)
    http_server.start()
    
    # Démarrer l'auto-pinger
    ping_interval = int(os.environ.get('PING_INTERVAL', 300))
    self_pinger = SelfPinger(port=port, interval=ping_interval)
    self_pinger.start()
    
    # Démarrer le backup automatique (toutes les 5 minutes)
    backup_interval = int(os.environ.get('BACKUP_INTERVAL', 300))
    auto_backup = AutoBackupThread(interval=backup_interval)
    auto_backup.start()
    
    # Lancer les bots
    bot_threads = []
    for bot_name, module_name in bots_config:
        runner = BotRunner(bot_name, module_name)
        runner.start()
        bot_threads.append(runner)
        time.sleep(2)
    
    logger.info("")
    logger.info("✅ TOUS LES SERVICES DÉMARRÉS")
    logger.info("=" * 70)
    logger.info("")
    logger.info("📡 Configuration:")
    logger.info(f"   🌐 Health Check: http://localhost:{port}/health")
    logger.info(f"   💾 Backup auto: toutes les {backup_interval}s (5 min)")
    logger.info(f"   🔄 Auto-ping: toutes les {ping_interval}s")
    logger.info("")
    logger.info("💾 Points de sauvegarde:")
    logger.info("   ✅ Au démarrage: Restauration automatique")
    logger.info("   ✅ Toutes les 5 min: Backup automatique")
    logger.info("   ✅ À l'arrêt/redéploiement: Backup final")
    logger.info("   ✅ Endpoint manuel: /backup")
    logger.info("")
    logger.info("=" * 70)
    logger.info("🟢 SYSTÈME PRÊT")
    logger.info("=" * 70)
    
    try:
        while not shutdown_event.is_set():
            alive_bots = [t for t in bot_threads if t.is_alive()]
            
            if not alive_bots:
                logger.warning("⚠️ Tous les bots se sont arrêtés!")
                break
            
            for t in alive_bots:
                bot_status.heartbeat(t.bot_name)
            
            shutdown_event.wait(timeout=30)
            
    except KeyboardInterrupt:
        logger.info("⚠️ Arrêt demandé (Ctrl+C)")
        shutdown_event.set()
        
    finally:
        logger.info("")
        logger.info("=" * 50)
        logger.info("🛑 ARRÊT EN COURS...")
        logger.info("=" * 50)
        
        # ⭐ SAUVEGARDER AVANT D'ARRÊTER (si pas déjà fait)
        if not shutdown_in_progress:
            save_backup()
        
        auto_backup.stop()
        self_pinger.stop()
        http_server.stop()
        
        for thread in bot_threads:
            thread.join(timeout=5)
        
        logger.info("")
        logger.info("✅ Tous les services arrêtés proprement")
        logger.info("👋 Launcher terminé")

# ============================================================================
# 🎯 POINT D'ENTRÉE
# ============================================================================

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    atexit.register(exit_handler)
    
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Arrêt propre du launcher")
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        save_backup()
        sys.exit(1)