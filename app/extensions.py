"""Flask extensions initialized and configured."""
from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to access the admin portal."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    """Load user by MongoDB string ObjectId for Flask-Login."""
    from app.repositories.user_repository import UserRepository
    repo = UserRepository()
    return repo.find_by_id(user_id)
