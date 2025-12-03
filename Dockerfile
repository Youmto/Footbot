FROM python:3.11-slim-bookworm AS base

# Variables d'environnement Python
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Répertoire de travail
WORKDIR /app

# Mise à jour pip
RUN pip install --no-cache-dir --upgrade pip

# Copier requirements.txt
COPY requirements.txt .

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copier tous les fichiers du projet
COPY . .

# Créer les répertoires de données pour chaque bot
RUN mkdir -p data/footbot data/sexbot data/shared

# Exposer le port pour le serveur HTTP (géré par launcher.py)
EXPOSE 8080

# Point d'entrée : lancer le launcher qui gère tous les bots
CMD ["python", "launcher.py"]