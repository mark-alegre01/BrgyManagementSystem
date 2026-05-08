import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-brgy-system-change-this-in-production-2024"

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Local ESP32 fingerprint module proxy target
ESP32_BASE_URL = 'http://192.168.1.49:80'

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8001",
    "http://localhost:8001",
    "http://192.168.1.63:8001",
    "http://brgysicosico.local:8001",
    "http://brgysicosico:8001",
    "https://*.trycloudflare.com",
    "https://*.ts.net",
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    # Barangay apps
    "core",
    "residents",
    "certifications",
    "attendance",
    "census",
    "ordinances",
    "officials",
    "reports",
    "philsys",
    "appointments",
    "payments",
    "biometrics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
    "core.middleware.AutoLogoutMiddleware",
]

ROOT_URLCONF = "barangay_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.user_role_context",
            ],
        },
    },
]

WSGI_APPLICATION = "barangay_project.wsgi.application"

# Use PostgreSQL if DB_TYPE is set to 'postgres' or if DB_HOST is provided, otherwise fallback to SQLite
DB_TYPE = os.environ.get("DB_TYPE", "sqlite")

if DB_TYPE == "postgres" or os.environ.get("DB_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "sicosico_db"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", "postgres"),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

AUTH_USER_MODEL = 'core.User'

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Security configuration
SESSION_COOKIE_AGE = 1800  # 30 minutes
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = False  # Set to True in production over HTTPS
CSRF_COOKIE_SECURE = False     # Set to True in production over HTTPS
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Axes Configuration
AXES_FAILURE_LIMIT = 5          
AXES_COOLOFF_TIME = 1           
AXES_LOCK_OUT_AT_FAILURE = True 
AXES_RESET_ON_SUCCESS = True    
# Barangay Settings
BARANGAY_NAME = "Barangay Sico-Sico"
BARANGAY_MUNICIPALITY = "Gigaquit"
BARANGAY_PROVINCE = "Surigao del Norte"
BARANGAY_REGION = "XIII (Caraga)"
BARANGAY_CAPTAIN = "HON. MARITES R. MANONGAS"

# Biometric Settings
BIOMETRIC_PROVIDER = 'biometrics.stub.StubBiometricProvider'

# Attendance
ATTENDANCE_START_HOUR = 7
ATTENDANCE_END_HOUR = 18
LATE_THRESHOLD_MINUTES = 30

# Pagination
ITEMS_PER_PAGE = 25
