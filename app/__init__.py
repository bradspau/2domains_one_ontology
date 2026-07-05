from flask import Flask


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="")

    from .routes import bp

    app.register_blueprint(bp)

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    return app
