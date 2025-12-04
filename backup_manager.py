"""
BACKUP MANAGER - Version Professionnelle
Sauvegarde automatique des données vers GitHub Gist avec retry et validation
"""
import json
import os
import logging
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import time

logger = logging.getLogger("backup")

# ============================================================================
# 📦 GESTIONNAIRE DE BACKUP
# ============================================================================

class BackupManager:
    """Gestionnaire de backup vers GitHub Gist avec fonctionnalités avancées"""
    
    def __init__(self):
        # Nettoyer les tokens
        self.github_token = self._clean_token(os.environ.get("GITHUB_BACKUP_TOKEN", ""))
        self.gist_id = self._clean_token(os.environ.get("GIST_BACKUP_ID", ""))
        self.enabled = bool(self.github_token and self.gist_id)
        
        # Configuration
        self.max_retries = 3
        self.retry_delay = 2  # secondes
        self.api_timeout = 30  # secondes
        
        if not self.enabled:
            logger.warning("⚠️ Backup désactivé - GITHUB_BACKUP_TOKEN ou GIST_BACKUP_ID manquant")
        else:
            logger.info("✅ Backup automatique activé")
            logger.info(f"   📦 Gist ID: {self.gist_id[:8]}...")
    
    @staticmethod
    def _clean_token(token: str) -> str:
        """Nettoie un token des caractères parasites"""
        if not token:
            return ""
        return token.strip().replace("\n", "").replace("\r", "").replace(" ", "")
    
    def _make_request(
        self, 
        method: str, 
        url: str, 
        headers: Dict, 
        json_data: Optional[Dict] = None
    ) -> Optional[requests.Response]:
        """Effectue une requête HTTP avec retry"""
        for attempt in range(self.max_retries):
            try:
                if method == "GET":
                    response = requests.get(
                        url, 
                        headers=headers, 
                        timeout=self.api_timeout
                    )
                elif method == "PATCH":
                    response = requests.patch(
                        url, 
                        headers=headers, 
                        json=json_data, 
                        timeout=self.api_timeout
                    )
                else:
                    logger.error(f"Méthode HTTP non supportée: {method}")
                    return None
                
                if response.status_code in [200, 201]:
                    return response
                elif response.status_code == 401:
                    logger.error("❌ Token GitHub invalide (401 Unauthorized)")
                    return None
                elif response.status_code == 404:
                    logger.error("❌ Gist non trouvé (404)")
                    return None
                elif response.status_code == 403:
                    logger.warning(f"⚠️ Rate limit atteint, attente...")
                    time.sleep(60)  # Attendre 1 minute
                else:
                    logger.warning(f"⚠️ Erreur {response.status_code}, tentative {attempt + 1}/{self.max_retries}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ Timeout, tentative {attempt + 1}/{self.max_retries}")
            except requests.exceptions.ConnectionError:
                logger.warning(f"⚠️ Erreur connexion, tentative {attempt + 1}/{self.max_retries}")
            except Exception as e:
                logger.error(f"❌ Erreur inattendue: {e}")
                return None
            
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (attempt + 1))
        
        logger.error(f"❌ Échec après {self.max_retries} tentatives")
        return None
    
    def save_to_gist(self, data_dict: Dict) -> bool:
        """Sauvegarde les données vers GitHub Gist"""
        if not self.enabled:
            return False
        
        try:
            # Préparer les fichiers pour Gist
            files = {}
            for filename, content in data_dict.items():
                # Validation JSON
                try:
                    json_str = json.dumps(content, indent=2, ensure_ascii=False)
                    files[filename] = {"content": json_str}
                except (TypeError, ValueError) as e:
                    logger.warning(f"⚠️ Impossible de sérialiser {filename}: {e}")
                    continue
            
            if not files:
                logger.warning("⚠️ Aucun fichier à sauvegarder")
                return False
            
            # Ajouter métadonnées
            files["_backup_meta.json"] = {
                "content": json.dumps({
                    "last_backup": datetime.now().isoformat(),
                    "files_count": len(files),
                    "version": "2.0"
                }, indent=2)
            }
            
            # Mise à jour du Gist
            url = f"https://api.github.com/gists/{self.gist_id}"
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            payload = {
                "description": f"Bot Backup - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "files": files
            }
            
            response = self._make_request("PATCH", url, headers, payload)
            
            if response:
                logger.info(f"✅ Backup sauvegardé ({len(files)} fichiers)")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur backup: {e}")
            return False
    
    def restore_from_gist(self) -> Dict:
        """Restaure les données depuis GitHub Gist"""
        if not self.enabled:
            return {}
        
        try:
            url = f"https://api.github.com/gists/{self.gist_id}"
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            
            response = self._make_request("GET", url, headers)
            
            if not response:
                return {}
            
            gist_data = response.json()
            files = gist_data.get("files", {})
            
            restored = {}
            for filename, file_data in files.items():
                # Ignorer les métadonnées
                if filename.startswith("_"):
                    continue
                    
                if filename.endswith('.json'):
                    content = file_data.get("content", "{}")
                    try:
                        restored[filename] = json.loads(content)
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ JSON invalide: {filename}")
                        restored[filename] = {}
            
            logger.info(f"✅ {len(restored)} fichier(s) restauré(s) depuis Gist")
            return restored
            
        except Exception as e:
            logger.error(f"❌ Erreur restauration: {e}")
            return {}
    
    def backup_all_bots(self) -> bool:
        """Sauvegarde toutes les données des bots"""
        if not self.enabled:
            return False
        
        data_to_backup = {}
        
        # Parcourir les dossiers de données
        bot_dirs = [
            ("footbot", Path("data/footbot")),
            ("sexbot", Path("data/sexbot")),
        ]
        
        for prefix, bot_dir in bot_dirs:
            if bot_dir.exists():
                for json_file in bot_dir.glob("*.json"):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            content = json.load(f)
                            data_to_backup[f"{prefix}_{json_file.name}"] = content
                            logger.debug(f"📄 Chargé: {prefix}_{json_file.name}")
                    except (json.JSONDecodeError, IOError) as e:
                        logger.warning(f"⚠️ Impossible de lire {json_file}: {e}")
        
        if data_to_backup:
            logger.info(f"💾 Sauvegarde de {len(data_to_backup)} fichier(s)...")
            return self.save_to_gist(data_to_backup)
        
        logger.info("ℹ️ Aucune donnée à sauvegarder")
        return False
    
    def restore_all_bots(self) -> bool:
        """Restaure toutes les données des bots"""
        if not self.enabled:
            return False
        
        restored_data = self.restore_from_gist()
        
        if not restored_data:
            logger.info("ℹ️ Aucune donnée à restaurer")
            return False
        
        # Créer les dossiers
        Path("data/footbot").mkdir(parents=True, exist_ok=True)
        Path("data/sexbot").mkdir(parents=True, exist_ok=True)
        
        success_count = 0
        
        # Restaurer les fichiers
        for filename, content in restored_data.items():
            try:
                if filename.startswith("footbot_"):
                    actual_name = filename.replace("footbot_", "")
                    filepath = Path(f"data/footbot/{actual_name}")
                elif filename.startswith("sexbot_"):
                    actual_name = filename.replace("sexbot_", "")
                    filepath = Path(f"data/sexbot/{actual_name}")
                else:
                    logger.debug(f"⏭️ Ignoré: {filename}")
                    continue
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(content, f, indent=2, ensure_ascii=False)
                
                logger.info(f"✅ Restauré: {filepath}")
                success_count += 1
                
            except Exception as e:
                logger.error(f"❌ Erreur restauration {filename}: {e}")
        
        logger.info(f"📦 Restauration terminée: {success_count}/{len(restored_data)} fichiers")
        return success_count > 0
    
    def test_connection(self) -> bool:
        """Teste la connexion au Gist"""
        if not self.enabled:
            logger.error("❌ Backup non configuré")
            return False
        
        try:
            url = f"https://api.github.com/gists/{self.gist_id}"
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = self._make_request("GET", url, headers)
            
            if response:
                gist_data = response.json()
                logger.info(f"✅ Connexion OK - Gist: {gist_data.get('description', 'N/A')}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Test connexion échoué: {e}")
            return False


# ============================================================================
# 🌍 INSTANCE GLOBALE
# ============================================================================

backup_manager = BackupManager()


# ============================================================================
# 🧪 TEST
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 Test du BackupManager")
    print("=" * 40)
    
    if backup_manager.test_connection():
        print("\n📦 Test restauration...")
        backup_manager.restore_all_bots()
        
        print("\n💾 Test sauvegarde...")
        backup_manager.backup_all_bots()
    else:
        print("❌ Impossible de se connecter au Gist")