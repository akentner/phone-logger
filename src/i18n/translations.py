"""Translation strings for phone-logger i18n."""

from typing import Any

SUPPORTED_LANGUAGES = ["de", "en"]
DEFAULT_LANGUAGE = "de"

# Translation dictionaries
TRANSLATIONS: dict[str, dict[str, Any]] = {
    "de": {
        # Number types
        "number_type": {
            "private": "Privat",
            "business": "Geschäftlich",
            "mobile": "Mobil",
        },
        # Call directions
        "direction": {
            "inbound": "Eingehend",
            "outbound": "Ausgehend",
        },
        # Call event types
        "event_type": {
            "ring": "Klingeln",
            "call": "Anruf",
            "connect": "Verbunden",
            "disconnect": "Beendet",
        },
        # General UI labels
        "ui": {
            "contacts": "Kontakte",
            "calls": "Anrufe",
            "cache": "Cache",
            "config": "Einstellungen",
            "save": "Speichern",
            "cancel": "Abbrechen",
            "delete": "Löschen",
            "edit": "Bearbeiten",
            "add": "Hinzufügen",
            "search": "Suchen",
            "loading": "Lade...",
            "no_data": "Keine Daten vorhanden",
            "error": "Fehler",
            "success": "Erfolg",
        },
        # Contact form
        "contact": {
            "number": "Rufnummer",
            "name": "Name",
            "number_type": "Typ",
            "tags": "Tags",
            "notes": "Notizen",
            "spam_score": "Spam Score",
            "source": "Quelle",
            "last_seen": "Zuletzt gesehen",
            "new_contact": "Neuer Kontakt",
            "edit_contact": "Kontakt bearbeiten",
            "delete_confirm": "Kontakt wirklich löschen?",
        },
        # PBX device types
        "device_type": {
            "dect": "DECT",
            "voip": "VoIP",
            "analog": "Analog",
            "fax": "Fax",
            "voicebox": "Anrufbeantworter",
        },
        # PBX trunk types
        "trunk_type": {
            "sip": "SIP",
            "isdn": "ISDN",
            "analog": "Analog",
        },
        # PBX line states
        "line_status": {
            "idle": "Frei",
            "ring": "Klingelt",
            "call": "Wählt",
            "talking": "Gespräch",
            "finished": "Beendet",
            "missed": "Verpasst",
            "notReached": "Nicht erreicht",
        },
        # PBX UI labels
        "pbx": {
            "lines": "Leitungen",
            "trunks": "Amtsleitungen",
            "msns": "Rufnummern",
            "devices": "Endgeräte",
            "status": "Status",
            "internal_call": "Interner Anruf",
        },
    },
    "en": {
        # Number types
        "number_type": {
            "private": "Private",
            "business": "Business",
            "mobile": "Mobile",
        },
        # Call directions
        "direction": {
            "inbound": "Inbound",
            "outbound": "Outbound",
        },
        # Call event types
        "event_type": {
            "ring": "Ring",
            "call": "Call",
            "connect": "Connect",
            "disconnect": "Disconnect",
        },
        # General UI labels
        "ui": {
            "contacts": "Contacts",
            "calls": "Calls",
            "cache": "Cache",
            "config": "Settings",
            "save": "Save",
            "cancel": "Cancel",
            "delete": "Delete",
            "edit": "Edit",
            "add": "Add",
            "search": "Search",
            "loading": "Loading...",
            "no_data": "No data available",
            "error": "Error",
            "success": "Success",
        },
        # Contact form
        "contact": {
            "number": "Phone Number",
            "name": "Name",
            "number_type": "Type",
            "tags": "Tags",
            "notes": "Notes",
            "spam_score": "Spam Score",
            "source": "Source",
            "last_seen": "Last Seen",
            "new_contact": "New Contact",
            "edit_contact": "Edit Contact",
            "delete_confirm": "Really delete this contact?",
        },
        # PBX device types
        "device_type": {
            "dect": "DECT",
            "voip": "VoIP",
            "analog": "Analog",
            "fax": "Fax",
            "voicebox": "Voicebox",
        },
        # PBX trunk types
        "trunk_type": {
            "sip": "SIP",
            "isdn": "ISDN",
            "analog": "Analog",
        },
        # PBX line states
        "line_status": {
            "idle": "Idle",
            "ring": "Ringing",
            "call": "Dialing",
            "talking": "Talking",
            "finished": "Finished",
            "missed": "Missed",
            "notReached": "Not Reached",
        },
        # PBX UI labels
        "pbx": {
            "lines": "Lines",
            "trunks": "Trunks",
            "msns": "Numbers",
            "devices": "Devices",
            "status": "Status",
            "internal_call": "Internal Call",
        },
    },
}


def get_translation(key: str, lang: str = DEFAULT_LANGUAGE) -> str | dict:
    """
    Get a translation for a key.
    
    Args:
        key: Dot-separated key path, e.g. "number_type.private" or "ui.save"
        lang: Language code (de, en)
    
    Returns:
        Translated string or dict if key points to a group
    """
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE
    
    translations = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE])
    
    parts = key.split(".")
    result: Any = translations
    for part in parts:
        if isinstance(result, dict) and part in result:
            result = result[part]
        else:
            return key  # Return key as fallback
    
    return result


def get_translations(lang: str = DEFAULT_LANGUAGE) -> dict[str, Any]:
    """
    Get all translations for a language.
    
    Args:
        lang: Language code (de, en)
    
    Returns:
        Full translation dictionary for the language
    """
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE
    
    return TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE])
