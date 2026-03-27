from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL
    POSTGRES_USER: str = "template_user"
    POSTGRES_PASSWORD: str = "template_dev_password"
    POSTGRES_DB: str = "template_db"
    POSTGRES_HOST: str = "pgbouncer"
    POSTGRES_PORT: int = 6432

    # Pool sizing DB
    POOL_SIZE: int = 20
    POOL_MAX_OVERFLOW: int = 30

    # JWT
    SECRET_KEY: str = "dev_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Encryption (Fernet key for secrets at rest)
    ENCRYPTION_KEY: str = ""

    # Upload
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # File storage
    STORAGE_BACKEND: str = "local"  # "local" (futur: "s3")
    UPLOAD_QUOTA_MB: int = 0  # 0 = illimite
    UPLOAD_THUMBNAIL_SIZE: int = 200  # px max dimension

    # Antivirus (ClamAV)
    ANTIVIRUS_ENABLED: bool = False
    ANTIVIRUS_HOST: str = "clamav"
    ANTIVIRUS_PORT: int = 3310

    # SMTP
    SMTP_HOST: str = "smtp.office365.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@example.com"
    SMTP_FROM_NAME: str = "Sitter"
    SMTP_USE_TLS: bool = True
    EMAIL_ENABLED: bool = False

    # Webhooks
    WEBHOOK_TIMEOUT: int = 10
    WEBHOOK_MAX_RETRIES: int = 3

    # Web Push (VAPID)
    VAPID_PRIVATE_KEY: str = ""
    VAPID_PUBLIC_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:noreply@example.com"
    PUSH_ENABLED: bool = False

    # Intranet SSO
    INTRANET_AUTH_URL: str = ""
    INTRANET_EMAIL_DOMAIN: str = ""
    INTRANET_SSL_CA_BUNDLE: str = ""  # Path to CA bundle for intranet SSL verification

    # Seed defaults
    DEFAULT_ADMIN_EMAIL: str = "admin@example.com"
    SUPER_ADMIN_ROLE_SLUG: str = "super_admin"

    # SSO - Google OAuth2
    SSO_GOOGLE_CLIENT_ID: str = ""
    SSO_GOOGLE_CLIENT_SECRET: str = ""
    SSO_GOOGLE_REDIRECT_URI: str = "http://localhost:5482/sso/callback/google"

    # SSO - GitHub OAuth2
    SSO_GITHUB_CLIENT_ID: str = ""
    SSO_GITHUB_CLIENT_SECRET: str = ""
    SSO_GITHUB_REDIRECT_URI: str = "http://localhost:5482/sso/callback/github"

    # MFA - TOTP
    MFA_TOTP_ISSUER_NAME: str = "Sitter"

    # MFA - Email OTP
    MFA_EMAIL_CODE_LENGTH: int = 6
    MFA_EMAIL_CODE_EXPIRY_MINUTES: int = 5
    MFA_EMAIL_RESEND_COOLDOWN_SECONDS: int = 120

    # Backups
    BACKUP_DIR: str = "/app/backups"
    ENV: str = "production"

    # Notification purge
    NOTIFICATION_PURGE_DAYS: int = 90  # Hard-delete soft-deleted notifications older than N days

    # Event purge
    EVENT_RETENTION_DAYS: int = 1460  # Delete events older than N days (48 mois)

    # Notification max age (hard-delete regardless of soft-delete status)
    NOTIFICATION_MAX_AGE_DAYS: int = 365  # Hard-delete ALL notifications older than N days

    # Batch processing
    PURGE_BATCH_SIZE: int = 10000  # Rows per batch for batch_delete operations

    # Push subscription cleanup
    PUSH_SUBSCRIPTION_RETENTION_DAYS: int = 90  # Delete inactive subscriptions older than N days

    # Impersonation log retention
    IMPERSONATION_LOG_RETENTION_DAYS: int = 180  # Delete impersonation logs older than N days

    # Command execution log retention
    COMMAND_LOG_RETENTION_DAYS: int = 90  # Delete command execution logs older than N days

    # User session retention
    SESSION_RETENTION_DAYS: int = 90  # Delete revoked/expired sessions older than N days

    # Webhook delivery log retention
    DELIVERY_LOG_RETENTION_DAYS: int = 90  # Delete webhook delivery logs older than N days

    # RGPD retention
    RGPD_AUDIT_LOG_RETENTION_DAYS: int = 365  # Delete data access audit logs older than N days
    RGPD_CONSENT_RETENTION_DAYS: int = 1095  # Delete consent records older than N days (~3 ans)

    # Lifecycle (user account lifecycle management)
    LIFECYCLE_INACTIVITY_DAYS: int = 1460  # ~48 months of inactivity before archive
    LIFECYCLE_ARCHIVE_DAYS: int = 365  # ~12 months of archive before permanent deletion

    # i18n
    I18N_DEFAULT_LOCALE: str = "fr"
    I18N_SUPPORTED_LOCALES: str = "fr,en"

    # Frontend URL (for reset password links)
    FRONTEND_URL: str = "http://localhost:5482"

    # CORS
    CORS_ORIGINS: str = ""  # Comma-separated origins; empty = use FRONTEND_URL

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_REGISTER: str = "3/minute"
    RATE_LIMIT_FORGOT_PASSWORD: str = "3/minute"
    RATE_LIMIT_RESET_PASSWORD: str = "5/minute"
    RATE_LIMIT_MFA_VERIFY: str = "5/minute"
    RATE_LIMIT_DEFAULT: str = "60/minute"

    # Permission cache
    PERMISSION_CACHE_TTL_SECONDS: int = 300  # 5 min
    PERMISSION_CACHE_MAX_SIZE: int = 1000

    # TTS
    TTS_MODELS_DIR: str = "/app/tts_models"
    TTS_OUTPUT_DIR: str = "/app/uploads/tts/output"
    TTS_REFERENCE_DIR: str = "/app/uploads/tts/references"
    TTS_DEFAULT_VOICE_SLUG: str = "siwis"
    TTS_MAX_TEXT_LENGTH: int = 10000
    TTS_MAX_REFERENCE_AUDIO_MB: int = 20
    TTS_CROSSFADE_MS: int = 100

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Meilisearch
    MEILISEARCH_URL: str = "http://meilisearch:7700"
    MEILISEARCH_MASTER_KEY: str = "meili_dev_master_key"
    MEILISEARCH_ENABLED: bool = True

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def is_dev(self) -> bool:
        return self.ENV == "dev"

    class Config:
        env_file = ".env"
        secrets_dir = "/run/secrets"


settings = Settings()
