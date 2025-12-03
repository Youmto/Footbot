import asyncio
import logging
import sys
import os
from multiprocessing import Process
import signal
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import time

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Variables globales
footbot_process = None
sexbot_process = None
http_server = None
http_server_ready = threading.Event()

# ============================================================================
# 🌐 SERVEUR HTTP UNIQUE
# ============================================================================

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Handler HTTP pour Render et monitoring"""
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        # Status HTML
        status_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Multi-Bot Server</title>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial; background: #1a1a1a; color: #fff; padding: 20px; }
                .bot { background: #2a2a2a; padding: 20px; margin: 10px 0; border-radius: 10px; }
                .status { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 10px; }
                .active { background: #0f0; }
                .inactive { background: #f00; }
            </style>
        </head>
        <body>
            <h1>🤖 Multi-Bot Server Status</h1>
            <div class="bot">
                <h2><span class="status {footbot_status}"></span>⚽ FootBot</h2>
                <p>Status: {footbot_text}</p>
            </div>
            <div class="bot">
                <h2><span class="status {sexbot_status}"></span>🔞 SexBot</h2>
                <p>Status: {sexbot_text}</p>
            </div>
            <p><small>Server Time: {time}</small></p>
        </body>
        </html>
        """
        
        footbot_running = footbot_process and footbot_process.is_alive()
        sexbot_running = sexbot_process and sexbot_process.is_alive()
        
        html = status_html.format(
            footbot_status="active" if footbot_running else "inactive",
            footbot_text="Running ✅" if footbot_running else "Stopped ❌",
            sexbot_status="active" if sexbot_running else "inactive",
            sexbot_text="Running ✅" if sexbot_running else "Stopped ❌",
            time=time.strftime("%Y-%m-%d %H:%M:%S")
        )
        
        self.wfile.write(html.encode('utf-8'))
    
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Désactiver les logs HTTP verbeux

def start_http_server():
    """Démarre le serveur HTTP unique"""
    global http_server
    port = int(os.environ.get('PORT', 8080))
    
    try:
        http_server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        logger.info(f"🌐 Serveur HTTP démarré sur port {port}")
        logger.info(f"📊 Status: http://0.0.0.0:{port}/")
        http_server_ready.set()
        http_server.serve_forever()
    except Exception as e:
        logger.error(f"❌ Erreur serveur HTTP: {e}")

def stop_http_server():
    """Arrête le serveur HTTP"""
    global http_server
    if http_server:
        logger.info("🛑 Arrêt serveur HTTP...")
        http_server.shutdown()
        http_server.server_close()

# ============================================================================
# 🤖 GESTION DES BOTS
# ============================================================================

def run_footbot():
    """Lance le bot Football"""
    try:
        logger.info("⚽ Démarrage FootBot...")
        import footbot
        footbot.main()
    except Exception as e:
        logger.error(f"❌ Erreur FootBot: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def run_sexbot():
    """Lance le bot Adulte"""
    try:
        logger.info("🔞 Démarrage SexBot...")
        import sexbot
        sexbot.main()
    except Exception as e:
        logger.error(f"❌ Erreur SexBot: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def signal_handler(signum, frame):
    """Gestion de l'arrêt propre"""
    logger.info(f"⚠️ Signal {signum} reçu, arrêt des bots...")
    
    if footbot_process and footbot_process.is_alive():
        logger.info("🛑 Arrêt FootBot...")
        footbot_process.terminate()
        footbot_process.join(timeout=5)
        if footbot_process.is_alive():
            footbot_process.kill()
    
    if sexbot_process and sexbot_process.is_alive():
        logger.info("🛑 Arrêt SexBot...")
        sexbot_process.terminate()
        sexbot_process.join(timeout=5)
        if sexbot_process.is_alive():
            sexbot_process.kill()
    
    stop_http_server()
    logger.info("✅ Tous les bots arrêtés")
    sys.exit(0)

# ============================================================================
# 🚀 MAIN
# ============================================================================

def main():
    """Lance les deux bots en parallèle"""
    global footbot_process, sexbot_process
    
    logger.info("=" * 70)
    logger.info("🚀 MULTI-BOT LAUNCHER - RENDER DEPLOYMENT")
    logger.info("=" * 70)
    
    # Configuration des signaux
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Créer les dossiers de données
    os.makedirs("data/footbot", exist_ok=True)
    os.makedirs("data/sexbot", exist_ok=True)
    logger.info("✅ Dossiers de données créés")
    
    # Vérifier les tokens
    footbot_token = os.environ.get("FOOTBOT_TOKEN")
    sexbot_token = os.environ.get("SEXBOT_TOKEN")
    
    if not footbot_token:
        logger.warning("⚠️ FOOTBOT_TOKEN manquant - FootBot désactivé")
    if not sexbot_token:
        logger.warning("⚠️ SEXBOT_TOKEN manquant - SexBot désactivé")
    
    if not footbot_token and not sexbot_token:
        logger.error("❌ Aucun token configuré!")
        sys.exit(1)
    
    # Démarrer le serveur HTTP
    logger.info("🌐 Démarrage serveur HTTP...")
    http_thread = threading.Thread(target=start_http_server, daemon=False, name="HTTPServer")
    http_thread.start()
    
    if not http_server_ready.wait(timeout=10):
        logger.error("❌ Serveur HTTP non démarré")
        sys.exit(1)
    
    logger.info("✅ Serveur HTTP opérationnel")
    
    # Lancer les bots
    try:
        if footbot_token:
            logger.info("=" * 70)
            logger.info("🟢 Lancement FootBot...")
            footbot_process = Process(target=run_footbot, name="FootBot")
            footbot_process.start()
            logger.info(f"✅ FootBot démarré (PID: {footbot_process.pid})")
            time.sleep(2)  # Attendre un peu avant de lancer le suivant
        
        if sexbot_token:
            logger.info("=" * 70)
            logger.info("🟢 Lancement SexBot...")
            sexbot_process = Process(target=run_sexbot, name="SexBot")
            sexbot_process.start()
            logger.info(f"✅ SexBot démarré (PID: {sexbot_process.pid})")
        
        logger.info("=" * 70)
        logger.info("✅ TOUS LES BOTS SONT ACTIFS")
        logger.info("=" * 70)
        logger.info("")
        logger.info("📊 Monitoring:")
        if footbot_token:
            logger.info(f"   ⚽ FootBot: PID {footbot_process.pid}")
        if sexbot_token:
            logger.info(f"   🔞 SexBot: PID {sexbot_process.pid}")
        logger.info(f"   🌐 HTTP Server: Port {os.environ.get('PORT', 8080)}")
        logger.info("")
        logger.info("🔄 Auto-restart activé")
        logger.info("⏰ Vérification toutes les 10 secondes")
        logger.info("=" * 70)
        
        # Surveiller et redémarrer les processus si nécessaire
        restart_count = {'footbot': 0, 'sexbot': 0}
        max_restarts = 3
        
        while True:
            # Vérifier FootBot
            if footbot_token and footbot_process:
                if not footbot_process.is_alive():
                    restart_count['footbot'] += 1
                    if restart_count['footbot'] <= max_restarts:
                        logger.error(f"❌ FootBot s'est arrêté! (Tentative {restart_count['footbot']}/{max_restarts})")
                        logger.info("🔄 Redémarrage FootBot...")
                        footbot_process = Process(target=run_footbot, name="FootBot")
                        footbot_process.start()
                        logger.info(f"✅ FootBot redémarré (PID: {footbot_process.pid})")
                        time.sleep(5)
                    else:
                        logger.error("❌ FootBot: Trop de redémarrages, abandon")
            
            # Vérifier SexBot
            if sexbot_token and sexbot_process:
                if not sexbot_process.is_alive():
                    restart_count['sexbot'] += 1
                    if restart_count['sexbot'] <= max_restarts:
                        logger.error(f"❌ SexBot s'est arrêté! (Tentative {restart_count['sexbot']}/{max_restarts})")
                        logger.info("🔄 Redémarrage SexBot...")
                        sexbot_process = Process(target=run_sexbot, name="SexBot")
                        sexbot_process.start()
                        logger.info(f"✅ SexBot redémarré (PID: {sexbot_process.pid})")
                        time.sleep(5)
                    else:
                        logger.error("❌ SexBot: Trop de redémarrages, abandon")
            
            # Vérifier toutes les 10 secondes
            time.sleep(10)
            
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        signal_handler(signal.SIGTERM, None)

if __name__ == '__main__':
    main()