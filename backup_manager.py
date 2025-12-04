"""
BACKUP MANAGER
Sauvegarde automatique des données vers GitHub Gist
"""
import json
import os
import logging
import requests
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class BackupManager:
    """Gestionnaire de backup vers GitHub Gist"""
    
    def __init__(self):
        # Nettoyer les tokens (supprimer espaces, retours à la ligne, etc.)
        self.github_token = os.environ.get("GITHUB_BACKUP_TOKEN", "").strip().replace("\n", "").replace("\r", "")
        self.gist_id = os.environ.get("GIST_BACKUP_ID", "").strip().replace("\n", "").replace("\r", "")
        self.enabled = bool(self.github_token and self.gist_id)
        
        if not self.enabled:
            logger.warning("⚠️ Backup désactivé - GITHUB_BACKUP_TOKEN ou GIST_BACKUP_ID manquant")
        else:
            logger.info("✅ Backup automatique activé")
    
    def save_to_gist(self, data_dict: dict):
        """Sauvegarde les données vers GitHub Gist"""
        if not self.enabled:
            return False
        
        try:
            # Préparer les fichiers pour Gist
            files = {}
            for filename, content in data_dict.items():
                files[filename] = {
                    "content": json.dumps(content, indent=2, ensure_ascii=False)
                }
            
            # Ajouter timestamp
            files["last_backup.txt"] = {
                "content": f"Last backup: {datetime.now().isoformat()}"
            }
            
            # Mise à jour du Gist
            url = f"https://api.github.com/gists/{self.gist_id}"
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            payload = {
                "description": f"Bot Data Backup - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "files": files
            }
            
            response = requests.patch(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                logger.info("✅ Backup sauvegardé sur GitHub Gist")
                return True
            else:
                logger.error(f"❌ Erreur backup: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur backup: {e}")
            return False
    
    def restore_from_gist(self) -> dict:
        """Restaure les données depuis GitHub Gist"""
        if not self.enabled:
            return {}
        
        try:
            url = f"https://api.github.com/gists/{self.gist_id}"
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                gist_data = response.json()
                files = gist_data.get("files", {})
                
                restored = {}
                for filename, file_data in files.items():
                    if filename.endswith('.json'):
                        content = file_data.get("content", "{}")
                        try:
                            restored[filename] = json.loads(content)
                        except:
                            restored[filename] = {}
                
                logger.info(f"✅ {len(restored)} fichier(s) restauré(s) depuis GitHub Gist")
                return restored
            else:
                logger.error(f"❌ Erreur restauration: {response.status_code}")
                return {}
                
        except Exception as e:
            logger.error(f"❌ Erreur restauration: {e}")
            return {}
    
    def backup_all_bots(self):
        """Sauvegarde toutes les données des bots"""
        if not self.enabled:
            return False
        
        data_to_backup = {}
        
        # FootBot
        footbot_dir = Path("data/footbot")
        if footbot_dir.exists():
            for json_file in footbot_dir.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data_to_backup[f"footbot_{json_file.name}"] = json.load(f)
                except:
                    pass
        
        # SexBot
        sexbot_dir = Path("data/sexbot")
        if sexbot_dir.exists():
            for json_file in sexbot_dir.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data_to_backup[f"sexbot_{json_file.name}"] = json.load(f)
                except:
                    pass
        
        if data_to_backup:
            return self.save_to_gist(data_to_backup)
        
        return False
    
    def restore_all_bots(self):
        """Restaure toutes les données des bots"""
        if not self.enabled:
            return False
        
        restored_data = self.restore_from_gist()
        
        if not restored_data:
            logger.info("ℹ️ Aucune donnée à restaurer")
            return False
        
        # Créer les dossiers
        os.makedirs("data/footbot", exist_ok=True)
        os.makedirs("data/sexbot", exist_ok=True)
        
        # Restaurer les fichiers
        for filename, content in restored_data.items():
            try:
                if filename.startswith("footbot_"):
                    actual_name = filename.replace("footbot_", "")
                    filepath = f"data/footbot/{actual_name}"
                elif filename.startswith("sexbot_"):
                    actual_name = filename.replace("sexbot_", "")
                    filepath = f"data/sexbot/{actual_name}"
                else:
                    continue
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(content, f, indent=2, ensure_ascii=False)
                
                logger.info(f"✅ Restauré: {filepath}")
                
            except Exception as e:
                logger.error(f"❌ Erreur restauration {filename}: {e}")
        
        return True


# Instance globale
backup_manager = BackupManager()