-- Core user entity; all profile fields are flat columns
CREATE TABLE user_profiles (
  user_id       TEXT PRIMARY KEY,           -- UUID4
  name          TEXT NOT NULL DEFAULT '',
  bio           TEXT NOT NULL DEFAULT '',
  gender        TEXT,                       -- 'male' | 'female' | 'other'
  date_of_birth TEXT,                       -- 'YYYY-MM-DD'
  city          TEXT NOT NULL DEFAULT '',
  region        TEXT NOT NULL DEFAULT '',
  photo_url     TEXT,                       -- main photo URL (served from /uploads/*)
  expo_push_token TEXT,
  status        TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'suspended' | 'banned'
  registered_at TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

-- Auth credentials; hangs off user_profiles
CREATE TABLE auth_credentials (
  user_id       TEXT PRIMARY KEY,
  username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
  email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,              -- bcrypt hash
  is_admin      INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL,
  last_login_at TEXT,
  FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_auth_username ON auth_credentials(username COLLATE NOCASE);
CREATE INDEX idx_auth_email    ON auth_credentials(email    COLLATE NOCASE);

-- Additional photos (max 4 per user)
CREATE TABLE user_photos (
  photo_id   TEXT PRIMARY KEY,             -- UUID4
  user_id    TEXT NOT NULL,
  url        TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_photos_user ON user_photos(user_id);

-- Refresh token sessions
CREATE TABLE user_sessions (
  token_hash TEXT PRIMARY KEY,             -- SHA-256 hex of the refresh token JWT
  user_id    TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id);

-- Block list
CREATE TABLE user_blocks (
  blocker_id TEXT NOT NULL,
  blocked_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (blocker_id, blocked_id),
  FOREIGN KEY (blocker_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
  FOREIGN KEY (blocked_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
);

-- Direct messages
CREATE TABLE direct_messages (
  message_id   TEXT PRIMARY KEY,           -- UUID4
  sender_id    TEXT NOT NULL,
  recipient_id TEXT NOT NULL,
  content      TEXT NOT NULL,
  msg_type     TEXT NOT NULL DEFAULT 'TEXT',  -- 'TEXT' | 'AUDIO' | 'IMAGE'
  created_at   TEXT NOT NULL,              -- ISO-8601 UTC
  read_at      TEXT,
  FOREIGN KEY (sender_id)    REFERENCES user_profiles(user_id) ON DELETE CASCADE,
  FOREIGN KEY (recipient_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE,
  CHECK (sender_id <> recipient_id)
);

CREATE INDEX idx_messages_pair ON direct_messages(
  sender_id, recipient_id, created_at DESC
);
CREATE INDEX idx_messages_pair2 ON direct_messages(
  recipient_id, sender_id, created_at DESC
);
