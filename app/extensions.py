from flask_socketio import SocketIO
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per hour"])
mail_ext = Mail()
scheduler = BackgroundScheduler(daemon=True)

login_manager.login_view = "auth.login_page"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"
