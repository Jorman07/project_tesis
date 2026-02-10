from config import Config

def create_app():
    from flask import Flask   # mover en caso de falla 
    app = Flask(__name__)
    app.config.from_object(Config)

    from app.auth.routes import auth_bp
    from app.main.routes import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    return app
