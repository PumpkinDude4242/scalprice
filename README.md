# ScalPrice - RAM Price Scraper Engine

Moteur de scraping modulaire pour extraire les prix des barrettes de RAM (DDR4/DDR5) sur les sites e-commerce européens.

## 🎯 Caractéristiques

- **Architecture Strategy Pattern** : Ajoutez facilement de nouveaux sites
- **Anti-détection "maison"** : Aucune API payante (rotation User-Agent, délais aléatoires)
- **Robustesse** : Gestion des erreurs, le script ne crashe pas
- **Normalisation** : Données uniformisées quelque soit la source

## 📁 Structure du Projet

```
scalprice/
├── config/
│   ├── settings.py      # Configuration globale
│   └── products.py      # URLs et requêtes cibles
├── scrapers/
│   ├── base.py          # Classe abstraite BaseScraper
│   ├── amazon.py        # Scraper Amazon FR
│   ├── ldlc.py          # Scraper LDLC
│   └── factory.py       # Factory et Registry
├── utils/
│   ├── anti_detection.py # Anti-bot (User-Agent, délais)
│   ├── normalizer.py     # Normalisation des données
│   └── logger.py         # Système de logging
├── output/               # Fichiers JSON générés
├── main.py              # Point d'entrée
└── requirements.txt
```

## 🚀 Installation

```bash
# Cloner le repository
git clone <repo-url>
cd scalprice

# Créer l'environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt

# Installer Playwright (navigateurs)
playwright install chromium
```

## 💻 Utilisation

```bash
# Lancer tous les scrapers configurés
python main.py

# Lancer des scrapers spécifiques
python main.py --scrapers amazon_fr ldlc

# Lister les scrapers disponibles
python main.py --list

# Mode verbeux (debug)
python main.py -v

# Mode navigateur visible (debug)
python main.py --headless false
```

## 📤 Format de Sortie

Fichier JSON (`output/ram_prices_TIMESTAMP.json`) :

```json
[
  {
    "id_unique": "a1b2c3d4e5f6",
    "nom_produit": "Corsair Vengeance 32GB DDR5-5600",
    "type_ram": "DDR5",
    "capacite": "32Go",
    "prix_actuel": 145.99,
    "devise": "EUR",
    "source_site": "Amazon FR",
    "url_produit": "https://amazon.fr/...",
    "url_image": "https://...",
    "timestamp_scan": "2024-01-15T10:00:00Z",
    "disponible": true
  }
]
```

## 🔧 Ajouter un Nouveau Site

1. Créer `scrapers/nouveau_site.py` :

```python
from .base import BaseScraper

class NouveauSiteScraper(BaseScraper):
    @property
    def name(self) -> str:
        return "nouveau_site"

    @property
    def display_name(self) -> str:
        return "Nouveau Site"

    # Implémenter les méthodes abstraites...
```

2. Enregistrer dans `scrapers/factory.py` :

```python
scraper_registry.register("nouveau_site", NouveauSiteScraper)
```

3. Ajouter les URLs dans `config/products.py`

## 🛡️ Anti-Détection (Sans API Payante)

| Technique | Description |
|-----------|-------------|
| User-Agent Rotation | `fake-useragent` avec vrais UA de navigateurs |
| Délais Aléatoires | 2-5s entre requêtes + micro-variations |
| Fingerprint Browser | Viewport, timezone, locale aléatoires |
| Stealth Scripts | Suppression des flags d'automation |
| Session Management | Cookies et headers réalistes |

## ⚠️ Limitations

- **CAPTCHA** : Pas de résolution automatique (nécessiterait service payant)
- **Proxies** : Pas de rotation IP (utilise IP locale)
- **Rate Limiting** : Respecte les délais pour éviter les bans

## 📝 Configuration

Modifier `config/settings.py` :

```python
# Délais entre requêtes
MIN_DELAY = 2.0
MAX_DELAY = 5.0

# Scrapers activés par défaut
ENABLED_SCRAPERS = ["amazon_fr", "ldlc"]

# Mode headless
HEADLESS = True
```

## 📜 Licence

MIT License
