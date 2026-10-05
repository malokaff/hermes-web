# Hermes Agent Web Interface

Interface web pour accéder à Hermes CLI, containerisée avec Podman.

## Architecture

- **Backend**: FastAPI (Python) avec Server-Sent Events pour le streaming
- **Frontend**: HTML/CSS/JS vanilla, thème sombre style terminal
- **Container**: Podman (rootless)
- **Port**: 9119

## Fonctionnalités

- ⚡ **One-Shot** — Exécute une commande Hermes (`-z` flag) et affiche la réponse
- 📡 **Stream** — Streaming temps réel de la sortie via SSE
- ℹ️ **Info** — Affiche la version et les commandes disponibles de Hermes
- 🎨 Interface sombre style terminal avec stats de santé

## Démarrage rapide

```bash
cd /home/bmaze/hermes-web
chmod +x start.sh
./start.sh
```

Accédez à l'interface sur http://localhost:9119

## Structure

```
hermes-web/
├── Podmanfile              # Définition du container Podman
├── requirements.txt        # Dépendances Python
├── start.sh                # Script de démarrage
├── README.md
├── hermes_web/
│   ├── __init__.py
│   └── app.py              # Application FastAPI
├── templates/
│   └── index.html          # Interface web
└── static/
    ├── style.css           # Styles
    └── app.js              # Logique frontend
```

## API Endpoints

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/` | Interface web |
| GET | `/api/health` | Health check |
| POST | `/api/command` | Exécution one-shot (JSON body: `{"prompt": "..."}`) |
| POST | `/api/stream` | Streaming SSE (JSON body: `{"prompt": "..."}`) |
| GET | `/api/info` | Informations Hermes |
| GET | `/api/sessions` | Sessions actives |
| GET | `/api/sessions/kill/{id}` | Tuer une session |

## Commands Podman

```bash
# Voir les logs
podman logs -f hermes-web

# Arrêter
podman stop hermes-web

# Redémarrer
podman restart hermes-web

# Supprimer
podman rm hermes-web
```

## Environnement

- `HERMES_CMD` — Chemin vers le CLI Hermes (default: `hermes`)
- `HERMES_ARGS` — Args supplémentaires séparés par espace