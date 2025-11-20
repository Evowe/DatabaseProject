from flask import Flask
from flask_login import LoginManager
from csi3335f2025 import mysql
from models import db, User, create_default_admin
from routes import register_routes

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'eff1159b7421704e488b999fa089d686790e5ca89e16060ad9565d5efc69f8db'
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{mysql['user']}:{mysql['password']}@{mysql['host']}/{mysql['database']}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Create default admin user on app startup
with app.app_context():
    create_default_admin()

# Register all routes
register_routes(app)

if __name__ == '__main__':
    app.run(debug=True, port=5001)