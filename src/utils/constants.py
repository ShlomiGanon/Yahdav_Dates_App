from enum import Enum
from pathlib import Path
import flet as ft

# Single source of truth for ALL visual/structural layout tokens. The classes
# below (TextSizes / UIConstants / ThemeColors) are now a thin BACK-COMPAT SHIM
# that re-exports the design-system values under their legacy names, so the ~50
# existing import sites keep working while the codebase migrates to reading `DS`
# directly. Edit `src/style/design_system.py` (not here) to change the look.
from style.design_system import DS


class TextSizes:
    H1 = DS.type.h1        # Main welcome titles
    H2 = DS.type.h2        # Card titles
    BUTTON = DS.type.button    # Button text
    BODY = DS.type.body      # Standard labels
    INPUT = DS.type.input     # Input text
    SMALL = DS.type.small     # Descriptions or error messages

class UIConstants:
    CARD_WIDTH = DS.sizing.card_w       # base hub-card width (before padding)
    # Hub-card responsive bounds. The centered hub card (Welcome/Login/Signup/
    # Menu) is width-CAPPED at CARD_MAX_WIDTH so it never stretches on a wide
    # window, and floored at CARD_MIN_WIDTH so it stays usable when narrow; the
    # engine clamps the live width to (window - 2*HUB_SIDE_MARGIN) between them.
    CARD_MAX_WIDTH = DS.sizing.card_max   # = CARD_WIDTH (400) + 2 * CARD_PADDING (30)
    CARD_MIN_WIDTH = DS.sizing.card_min
    HUB_SIDE_MARGIN = DS.sizing.hub_margin
    BUTTON_WIDTH = DS.sizing.button_w  # Buttons width
    BUTTON_HEIGHT = DS.sizing.button_h # Buttons height
    INPUT_WIDTH = DS.sizing.input_w    # Inputs width
    INPUT_HEIGHT = DS.sizing.input_h   # Inputs height
    CARD_PADDING = DS.pad.card
    ELEMENT_SPACING = DS.spacing.element
    CORNER_RADIUS = DS.radius.card
    # Shared implicit-animation duration (ms). Matches the 300ms button state
    # animation (components/buttons.py) so layout transitions feel of-a-piece.
    # Used by the action bar's animate= (BaseView).
    ANIM_MS = DS.motion.anim_ms

    # --- Content-screen frame geometry ---
    CONTENT_CARD_MARGIN       = DS.pad.content_margin
    CONTENT_CARD_PADDING      = DS.pad.content_card
    # A taller top padding for screens whose heading must clear the BG top logo
    # (the read-only peer profile and the peer photo album).
    CONTENT_CARD_PADDING_TALL = DS.pad.content_card_tall
    CONTENT_BODY_SPACING      = DS.spacing.body   # gap between body controls in the card
    ACTION_BAR_PADDING        = DS.pad.action_bar  # sticky bar outer padding
    ACTION_BAR_SPACING        = DS.spacing.bar   # gap between action rows

    # --- Inline status banner (components/feedback.py) ---
    STATUS_BANNER_PADDING = DS.pad.status_banner   # interior padding of the success/error banner

    # --- Chat bubble (components/chat.py) ---
    BUBBLE_PADDING = DS.pad.bubble   # interior padding of a chat bubble
    BUBBLE_RADIUS  = DS.radius.bubble   # corner radius of a chat bubble

    # --- List tile (components/cards.py — discover/matches member rows) ---
    LIST_TILE_PADDING = DS.pad.list_tile   # interior padding of a member card

    # --- My Profile view ---
    # Translucency of the form card floating over the full-screen BG image.
    FORM_OVERLAY_OPACITY = DS.opacity.form_overlay
    # Birth-date dropdown widths (day / month share one; year is a touch wider
    # for the 4-digit value). Their sum + row spacing stays within INPUT_WIDTH.
    DOB_PART_WIDTH = DS.sizing.dob_part_w   # day and month dropdowns
    DOB_YEAR_WIDTH = DS.sizing.dob_year_w   # year dropdown


class AssetPaths:
    """Bundled asset references — single source of truth for asset locations.

    Assets are served from the project-root `assets/` dir, wired via
    `assets_dir` in app.py. Image `src` values are relative to that dir, so
    they are bare filenames.
    """
    ASSETS_DIR_NAME = "assets"   # dir name under the project root
    BG_IMAGE        = "BG.png"   # My Profile full-screen background
    # Default/placeholder main profile picture. A bundled asset (served by
    # assets_dir as a bare filename), shown whenever a user's main picture is
    # missing/null and seeded as the main picture at registration. It is NOT a
    # data/uploads file, so the storage layer never deletes it.
    DEFAULT_PROFILE_IMAGE = "UNDEFINED_PROFILE.png"

class ThemeColors:
    """Back-compat shim — colours now live in `DS.palette` (design_system.py)."""

    # --- הליבה (The Core) ---
    PRIMARY = DS.palette.primary
    SECONDARY = DS.palette.secondary

    # --- מצבים (States) ---
    SUCCESS = DS.palette.success
    DANGER = DS.palette.danger
    WARNING = DS.palette.warning
    INFO = DS.palette.info
    FIELD_ERROR = DS.palette.field_error

    # --- ניטרליים (Neutrals) ---
    BACKGROUND = DS.palette.background
    SURFACE = DS.palette.surface
    TEXT_MAIN = DS.palette.text_main
    TEXT_ON_PRIMARY = DS.palette.text_on_primary

    # --- נוכחות (Presence indicators) ---
    ONLINE  = DS.palette.online
    OFFLINE = DS.palette.offline

    # --- בועות צ'אט (Chat bubbles) ---
    BUBBLE_SELF = DS.palette.bubble_self
    BUBBLE_PEER = DS.palette.bubble_peer


class DBConfig:
    # --- File location ---
    DB_DIR  = Path(__file__).resolve().parents[2] / "data"
    DB_FILE = "yahdav.sqlite3"
    DB_PATH = DB_DIR / DB_FILE
    SCHEMA_VERSION = 1

    # --- Connection / pragmas ---
    CONNECT_TIMEOUT_SEC = 5.0
    ISOLATION_LEVEL     = None        # autocommit; we manage txns explicitly
    JOURNAL_MODE        = "WAL"       # reader/writer concurrency for Flet event loop
    SYNCHRONOUS         = "NORMAL"    # WAL-safe, ~10x faster than FULL
    FOREIGN_KEYS        = True
    BUSY_TIMEOUT_MS     = 3000


class StorageConfig:
    """Media/Storage subsystem knobs — single source of truth.

    The uploads root is **absolute and stable**, derived from the source tree
    exactly like `DBConfig.DB_PATH` (never `:memory:`, never CWD-relative), so
    every process opens the same directory regardless of where it was launched.
    It sits under `data/uploads/`, which `.gitignore` already protects (`data/`
    + `uploads/`), so dev-run photos never leak to GitHub.
    """
    UPLOADS_DIR = DBConfig.DB_DIR / "uploads"   # absolute; mkdir'd on first use

    # Per-profile photo cap surfaced to the UI: 1 primary + 4 portfolio extras.
    MAX_PROFILE_PHOTOS = 5
    MAX_EXTRA_PHOTOS   = 4

    # Accepted image extensions (lower-case, dot-prefixed). An upload whose name
    # carries none of these is still stored, but with a safe '.img' fallback.
    ALLOWED_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic")


class AuthConfig:
    # Lockout / abuse thresholds — tuned for a 50+ audience (mistyping is common,
    # so threshold is lenient; lockout is short, not permanent).
    MAX_FAILED_LOGIN_ATTEMPTS = 5
    LOCKOUT_MINUTES           = 15
    PASSWORD_MIN_LENGTH       = 8

    # scrypt cost parameters — centralized so we can rotate without code edits.
    SCRYPT_N      = 2 ** 14
    SCRYPT_R      = 8
    SCRYPT_P      = 1
    SCRYPT_DKLEN  = 32
    SCRYPT_SALT_BYTES = 16

    # Session
    SESSION_TTL_MINUTES = 60 * 24 * 7  # 1 week

    # --- "Remember Me" (long-lived device token) ---
    # The device persists ONLY a backend-generated random token (never the
    # email/password). These knobs control its strength and lifetime.
    REMEMBER_ME_DAYS        = 30   # token validity window — tune here, never hardcode
    REMEMBER_ME_TOKEN_BYTES = 32   # entropy for secrets.token_urlsafe (256-bit)
    REMEMBER_ME_CLIENT_KEY  = "remember_me_token"  # device-storage key (single source; see utils/local_storage.py)


class FirebaseConfig:
    # --- Identity ---
    PROJECT_ID           = "yahdav-dates-app"
    WEB_API_KEY          = ""   # Identity Toolkit REST key (signInWithPassword)
    STORAGE_BUCKET       = "yahdav-dates-app.appspot.com"

    # --- Service-account credentials (Admin SDK) ---
    # File is git-ignored (see .gitignore: serviceAccountKey.json / firebase_credentials.json).
    SERVICE_ACCOUNT_PATH = Path(__file__).resolve().parents[2] / "serviceAccountKey.json"

    # --- REST endpoints ---
    IDENTITY_TOOLKIT_URL = "https://identitytoolkit.googleapis.com/v1"

    # --- Firestore collections (mirror the SQLite table layout) ---
    USERS_COLLECTION       = "users"
    USERNAMES_COLLECTION   = "usernames"
    USER_BLOCKS_COLLECTION = "user_blocks"
    MESSAGES_COLLECTION    = "direct_messages"


# ============================================================================
#  Direct Messaging
# ============================================================================

class MessageType(Enum):
    """Type of payload in a direct message.

    Integer values are persisted in SQLite — order/values are part of the
    on-disk contract. Append new members; never renumber existing ones.
    """
    TEXT  = 1
    AUDIO = 2   # Voice notes — critical channel for 50+ users (typing is hard).
    IMAGE = 3


class MessageStatus(Enum):
    """Lifecycle of a direct message, monotonic-ascending.

    The ordering matters: `status < READ` is used to find unread messages,
    and transitions only ever go upward (SENT → DELIVERED → READ).
    """
    SENT      = 1
    DELIVERED = 2
    READ      = 3


class ChatConfig:
    # --- Pagination ---
    DEFAULT_PAGE_SIZE = 20    # senior-friendly: small batches, smooth scroll
    MAX_PAGE_SIZE     = 100   # hard ceiling to keep payloads under ~2 MB

    # --- Payload limits ---
    MAX_TEXT_LENGTH        = 4000   # characters per text message
    MAX_AUDIO_DURATION_SEC = 120    # 2-minute voice notes (UX cap, not storage)
    MAX_IMAGE_BYTES        = 8 * 1024 * 1024  # 8 MB

    # --- Storage prefixes (Firebase Storage / local fs) ---
    AUDIO_BUCKET_PREFIX = "voice/"
    IMAGE_BUCKET_PREFIX = "images/"

    # --- Indexing / query knobs ---
    CONVERSATION_SEPARATOR = "|"    # builds deterministic chat keys: "min(uid)|max(uid)"


# ============================================================================
#  Discover / Matching feed
# ============================================================================

class MatchConfig:
    """Knobs for the discover feed (views/matching/discover_view.py).

    Kept here — not hardcoded in the view or backend — so the page size and
    its hard ceiling can be tuned in one place, exactly like ChatConfig.
    """
    DISCOVER_PAGE_SIZE     = 30    # senior-friendly: a browsable batch, not an endless wall
    MAX_DISCOVER_PAGE_SIZE = 100   # hard ceiling — clamps any caller-supplied limit

