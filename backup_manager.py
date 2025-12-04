"""
BACKUP MANAGER v2.1 - Sauvegarde GitHub Gist
Sauvegarde automatique et restauration des données des bots
"""
import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, Optional
import threading

# ============================================================================
# ⚙️ CONFIGURATION
# ============================================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("backup")

# Configuration GitHub Gist
GITHUB_TOKEN = os.environ.get("GITHUB_BACKUP_TOKEN", "").strip()
GIST_ID = os.environ.get("GIST_BACKUP_ID", "").strip()

# Dossiers de données
DATA_DIRS = [
    "data/footbot",
    "data/sexbot",
    "data/shared"
]

# Fichiers à sauvegarder
BACKUP_FILES = [
    "data/footbot/matches_data.json",
    "data/footbot/favorites_data.json",
    "data/footbot/users_data.json",
    "data/sexbot/videos_data.json",
    "data/sexbot/users_data.json",
    "data/sexbot/stats_data.json"
]

# ============================================================================
# 💾 BACKUP MANAGER
# ============================================================================

class BackupManager:
    """Gestionnaire de backup vers GitHub Gist"""
    
    def __init__(self):
        self.token = GITHUB_TOKEN
        self.gist_id = GIST_ID
        self.enabled = bool(self.token and self.gist_id)
        self.last_backup = None
        self.backup_count = 0
        self._lock = threading.Lock()
        
        if self.enabled:
            logger.info("✅ Backup GitHub Gist activé")
            logger.info(f"   📍 Gist ID: {self.gist_id[:8]}...")
        else:
            if not self.token:
                logger.warning("⚠️ GITHUB_BACKUP_TOKEN manquant")
            if not self.gist_id:
                logger.warning("⚠️ GIST_BACKUP_ID manquant")
            logger.warning("⚠️ Backup désactivé - données non persistantes!")
    
    def _make_request(self, method: str, data: dict = None, timeout: int = 30) -> Optional[dict]:
        """Effectue une requête vers l'API GitHub"""
        import urllib.request
        import urllib.error
        
        url = f"https://api.github.com/gists/{self.gist_id}"
        
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "TelegramBot-Backup/2.1"
        }
        
        body = None
        if data:
            body = json.dumps(data).encode('utf-8')
            headers["Content-Type"] = "application/json"
        
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                logger.error("❌ Token GitHub invalide (401 Non autorisé)")
            elif e.code == 404:
                logger.error("❌ Gist non trouvé (404)")
            else:
                logger.error(f"❌ Erreur HTTP {e.code}: {e.reason}")
            return None
        except urllib.error.URLError as e:
            logger.error(f"❌ Erreur réseau: {e.reason}")
            return None
        except Exception as e:
            logger.error(f"❌ Erreur requête: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Teste la connexion au Gist"""
        if not self.enabled:
            return False
        
        result = self._make_request("GET", timeout=10)
        if result:
            logger.info("✅ Connexion GitHub Gist OK")
            return True
        return False
    
    def backup_all_bots(self) -> bool:
        """Sauvegarde toutes les données vers le Gist"""
        if not self.enabled:
            return False
        
        with self._lock:
            try:
                files = {}
                files_count = 0
                
                # Créer les dossiers si nécessaire
                for dir_path in DATA_DIRS:
                    os.makedirs(dir_path, exist_ok=True)
                
                # Collecter tous les fichiers JSON
                for file_path in BACKUP_FILES:
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            # Valider le JSON
                            json.loads(content)
                            
                            # Nom du fichier pour le Gist
                            gist_filename = file_path.replace("/", "_")
                            files[gist_filename] = {"content": content}
                            files_count += 1
                            
                        except json.JSONDecodeError:
                            logger.warning(f"⚠️ JSON invalide: {file_path}")
                        except Exception as e:
                            logger.warning(f"⚠️ Erreur lecture {file_path}: {e}")
                
                if not files:
                    logger.info("ℹ️ Aucun fichier à sauvegarder")
                    return False
                
                # Ajouter les métadonnées
                meta = {
                    "last_backup": datetime.now().isoformat(),
                    "files_count": files_count,
                    "version": "2.1",
                    "backup_number": self.backup_count + 1
                }
                files["_backup_meta.json"] = {"content": json.dumps(meta, indent=2)}
                
                # Envoyer au Gist
                result = self._make_request("PATCH", {"files": files})
                
                if result:
                    self.last_backup = datetime.now()
                    self.backup_count += 1
                    logger.info(f"✅ Backup #{self.backup_count} réussi ({files_count} fichiers)")
                    return True
                else:
                    logger.error("❌ Échec du backup")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Erreur backup: {e}")
                return False
    
    def restore_all_bots(self) -> bool:
        """Restaure toutes les données depuis le Gist"""
        if not self.enabled:
            return False
        
        with self._lock:
            try:
                result = self._make_request("GET")
                
                if not result:
                    return False
                
                gist_files = result.get("files", {})
                
                if not gist_files:
                    logger.info("ℹ️ Gist vide - démarrage avec données fraîches")
                    return False
                
                # Créer les dossiers
                for dir_path in DATA_DIRS:
                    os.makedirs(dir_path, exist_ok=True)
                
                restored_count = 0
                
                for gist_filename, file_data in gist_files.items():
                    # Ignorer les métadonnées
                    if gist_filename.startswith("_"):
                        continue
                    
                    # Reconstruire le chemin local
                    local_path = gist_filename.replace("_", "/", 2)  # data_footbot_file.json -> data/footbot/file.json
                    
                    # Correction du chemin
                    if local_path.startswith("data/footbot/"):
                        pass  # OK
                    elif local_path.startswith("data/sexbot/"):
                        pass  # OK
                    elif "footbot" in gist_filename:
                        local_path = f"data/footbot/{gist_filename.split('_')[-1]}"
                    elif "sexbot" in gist_filename:
                        local_path = f"data/sexbot/{gist_filename.split('_')[-1]}"
                    else:
                        continue
                    
                    content = file_data.get("content", "")
                    
                    if not content or content == "{}":
                        continue
                    
                    try:
                        # Valider le JSON
                        json.loads(content)
                        
                        # Écrire le fichier
                        with open(local_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        
                        restored_count += 1
                        logger.info(f"   📄 Restauré: {local_path}")
                        
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ JSON invalide ignoré: {gist_filename}")
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur restauration {local_path}: {e}")
                
                if restored_count > 0:
                    logger.info(f"✅ Restauration terminée ({restored_count} fichiers)")
                    return True
                else:
                    logger.info("ℹ️ Aucun fichier à restaurer")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Erreur restauration: {e}")
                return False
    
    def backup_file(self, file_path: str) -> bool:
        """Sauvegarde un fichier spécifique immédiatement"""
        if not self.enabled:
            return False
        
        if not os.path.exists(file_path):
            return False
        
        # Déclencher un backup complet (plus simple et fiable)
        return self.backup_all_bots()
    
    def get_status(self) -> dict:
        """Retourne le statut du backup"""
        return {
            "enabled": self.enabled,
            "gist_id": self.gist_id[:8] + "..." if self.gist_id else None,
            "last_backup": self.last_backup.isoformat() if self.last_backup else None,
            "backup_count": self.backup_count
        }


# Instance globale
backup_manager = BackupManager()


# ============================================================================
# 🔧 FONCTIONS UTILITAIRES
# ============================================================================

def trigger_backup():
    """Déclenche un backup immédiat (appelable depuis les autres modules)"""
    return backup_manager.backup_all_bots()


def restore_backup():
    """Restaure les données (appelable depuis les autres modules)"""
    return backup_manager.restore_all_bots()


# ============================================================================
# 🧪 TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("🧪 TEST BACKUP MANAGER")
    print("=" * 50)
    
    if backup_manager.enabled:
        print("\n1. Test connexion...")
        if backup_manager.test_connection():
            print("   ✅ Connexion OK")
        else:
            print("   ❌ Connexion échouée")
        
        print("\n2. Test backup...")
        if backup_manager.backup_all_bots():
            print("   ✅ Backup OK")
        else:
            print("   ⚠️ Backup échoué ou rien à sauvegarder")
        
        print("\n3. Status:")
        print(f"   {backup_manager.get_status()}")
    else:
        print("\n❌ Backup désactivé")
        print("   Configurez GITHUB_BACKUP_TOKEN et GIST_BACKUP_ID")