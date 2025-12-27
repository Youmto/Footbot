# ============================================================================
# MULTI-BOT TELEGRAM - DOCKERFILE PRODUCTION
# Optimisé pour Render.com avec support UptimeRobot
# ============================================================================

# Image de base légère
FROM python:3.11-slim-bookworm AS base

# Métadonnées
LABEL maintainer="Multi-Bot Telegram"
LABEL version="2.0"
LABEL description="Multi-Bot Telegram avec support UptimeRobot"

# ============================================================================
# VARIABLES D'ENVIRONNEMENT
# ============================================================================

# Python optimisations
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1

# Locale (pour les caractères spéciaux)
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Application
ENV APP_HOME=/app
ENV DATA_DIR=/app/data

# ============================================================================
# CONFIGURATION SYSTÈME
# ============================================================================

# Créer un utilisateur non-root pour la sécurité
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Répertoire de travail
WORKDIR ${APP_HOME}

# Installer les dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Pour les requêtes HTTPS
    ca-certificates \
    # Pour le parsing HTML (lxml)
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ============================================================================
# INSTALLATION DES DÉPENDANCES PYTHON
# ============================================================================

# Mettre à jour pip
RUN pip install --no-cache-dir --upgrade pip wheel setuptools

# Copier et installer les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ============================================================================
# COPIE DE L'APPLICATION
# ============================================================================

# Copier tous les fichiers du projet
COPY launcher.py .
COPY backup_manager.py .
COPY footbot.py .
COPY sexbot.py .
COPY prediction_module.py .

# Créer les répertoires de données avec les bonnes permissions
RUN mkdir -p ${DATA_DIR}/footbot ${DATA_DIR}/sexbot ${DATA_DIR}/shared \
    && chown -R botuser:botuser ${APP_HOME}

# ============================================================================
# CONFIGURATION RÉSEAU
# ============================================================================

# Port pour le health check (Render + UptimeRobot)
EXPOSE 8080

# ============================================================================
# HEALTHCHECK DOCKER
# ============================================================================

# Vérification de santé interne Docker
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=5)" || exit 1

# ============================================================================
# EXÉCUTION
# ============================================================================

# Passer à l'utilisateur non-root
USER botuser

# Point d'entrée
CMD ["python", "-u", "launcher.py"]