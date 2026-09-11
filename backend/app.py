from flask import Flask, jsonify

from config import Config

app = Flask(__name__)
app.config.from_object(Config)


@app.route("/api/health")
def health_check():
    return jsonify({"status": "ok", "service": "MakanWhereSG API"})


@app.route("/api/establishments")
def get_establishments():
    return jsonify({
        "message": "Relational API placeholder for MariaDB integration.",
        "establishments": []
    })


@app.route("/api/reviews")
def get_reviews():
    return jsonify({
        "message": "MongoDB review API placeholder.",
        "reviews": []
    })


if __name__ == "__main__":
    app.run(debug=True)
