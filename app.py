import os
from flask import Flask, redirect, url_for, render_template
from flask_login import LoginManager, current_user
from config import config
from database.db import db
from database.models import User


def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Init extensions
    db.init_app(app)
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'error'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from auth.routes import auth_bp
    from dashboard.routes import dashboard_bp
    from students.routes import students_bp
    from scheduling.routes import scheduling_bp
    from booking.routes import booking_bp
    from payments.routes import payments_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(scheduling_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(payments_bp)

    # Home route
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return render_template('landing.html')

    # Create tables and run migrations
    with app.app_context():
        db.create_all()

        # Auto-migration: add missing columns to existing tables
        try:
            from sqlalchemy import text, inspect
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('users')]

            if 'default_meeting_link' not in columns:
                db.session.execute(text(
                    "ALTER TABLE users ADD COLUMN default_meeting_link VARCHAR(500) DEFAULT ''"
                ))
                db.session.commit()
                print("Migration: Added default_meeting_link column to users table")

            if 'meeting_link' not in [col['name'] for col in inspector.get_columns('sessions')]:
                db.session.execute(text(
                    "ALTER TABLE sessions ADD COLUMN meeting_link VARCHAR(500) DEFAULT ''"
                ))
                db.session.commit()
                print("Migration: Added meeting_link column to sessions table")
        except Exception as e:
            print(f"Migration check: {e}")

    return app


if __name__ == '__main__':
    app = create_app('development')
    app.run(debug=True, port=5000)
