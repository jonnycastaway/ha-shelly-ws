# Shelly Dimmer WebSocket – Home Assistant Integration

Eine Home Assistant Custom Integration für den **Shelly Dimmer 0/1-10V PM Gen3**, die eine persistente WebSocket-Verbindung (RPC Push) nutzt statt Polling.

## Features

- **Echtzeit-Updates** via WebSocket (kein Polling)
- **Light Entity**: Dimmer ein/ausschalten + Helligkeit regeln (0–100%)
- **Sensoren**: Watt, Volt, Ampere, kWh (Gesamtenergie)
- **Button**: Gerät neu starten
- **Automatische Wiederverbindung** bei Verbindungsabbruch
- **Optionale Authentifizierung** (SHA-256 Digest)
- **Mehrere Geräte** gleichzeitig unterstützt
- **UI-Konfiguration** – keine YAML nötig

---

## Installation via HACS

1. HACS → Integrationen → ⋮ → **Benutzerdefinierte Repositories**
2. URL eintragen: `https://github.com/YOUR_GITHUB/shelly-dimmer-ws-ha`
3. Kategorie: **Integration**
4. **Hinzufügen** → Integration suchen: `Shelly Dimmer WebSocket` → Installieren
5. Home Assistant neu starten

## Manuelle Installation

1. Den Ordner `custom_components/shelly_dimmer_ws` in dein HA-Verzeichnis kopieren:
   ```
   /config/custom_components/shelly_dimmer_ws/
   ```
2. Home Assistant neu starten

---

## Konfiguration

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen**
2. `Shelly Dimmer WebSocket` suchen
3. Formular ausfüllen:

| Feld | Beschreibung |
|------|-------------|
| Gerätename | Anzeigename in HA (z.B. "Wohnzimmer Dimmer") |
| IP-Adresse | IP des Shelly im lokalen Netzwerk |
| Port | Standard: `80` |
| Benutzername | Optional – nur wenn Auth aktiviert |
| Passwort | Optional – nur wenn Auth aktiviert |

4. **Absenden** – HA testet die Verbindung und legt das Gerät an.

---

## Entitäten

Pro Gerät werden folgende Entitäten erstellt:

| Entität | Typ | Beschreibung |
|---------|-----|-------------|
| `light.{name}` | Light | Dimmer (Ein/Aus + Helligkeit) |
| `sensor.{name}_leistung` | Sensor | Aktuelle Leistung in W |
| `sensor.{name}_spannung` | Sensor | Spannung in V |
| `sensor.{name}_stromstarke` | Sensor | Stromstärke in A |
| `sensor.{name}_energie` | Sensor | Gesamtenergie in Wh |
| `button.{name}_neustart` | Button | Gerät neu starten |

---

## Funktionsweise

Die Integration hält eine **dauerhafte WebSocket-Verbindung** zu `ws://<IP>/rpc` offen.

- Nach dem Verbindungsaufbau sendet der Client eine erste RPC-Anfrage (`Shelly.GetStatus`), wodurch sich der Client beim Shelly registriert.
- Der Shelly sendet daraufhin automatisch **`NotifyStatus`-Nachrichten**, sobald sich Werte ändern (Licht an/aus, Helligkeit, Leistungswerte).
- Bei Verbindungsabbruch wird automatisch alle **10 Sekunden** ein Reconnect versucht.
- Steuerkommandos (Ein/Aus, Helligkeit, Neustart) werden ebenfalls über die WebSocket-Verbindung gesendet.

---

## Voraussetzungen

- Home Assistant **2024.1.0** oder neuer
- Shelly Dimmer 0/1-10V PM **Gen3** im lokalen Netzwerk
- Python-Abhängigkeit `aiohttp` (bereits in HA enthalten)

---

## GitHub Repository Struktur

```
shelly-dimmer-ws-ha/
├── hacs.json
├── README.md
└── custom_components/
    └── shelly_dimmer_ws/
        ├── __init__.py
        ├── manifest.json
        ├── config_flow.py
        ├── const.py
        ├── websocket_client.py
        ├── light.py
        ├── sensor.py
        ├── button.py
        ├── strings.json
        └── translations/
            └── de.json
```
