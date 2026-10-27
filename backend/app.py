"""PasswordLab Flask server. Serves the frontend and the JSON API from one origin.
Request bodies are never logged or stored. Run from anywhere:  python backend/app.py [port]"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                      # allow `import combinatorics` etc. when run as a script

from flask import Flask, jsonify, request, send_from_directory  # noqa: E402

import password_analyzer as pa  # noqa: E402

FRONTEND = os.path.join(os.path.dirname(HERE), "frontend")
app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # 64 KB request limit


POST_ROUTES = {"api/analyze-config", "api/compare", "api/sweep"}


def _handle(fn):
    body = request.get_json(silent=True, force=True)   # tolerant of content-type; None if not valid JSON
    out = pa.error_json(["Request body is not valid JSON."]) if body is None else fn(body)
    return jsonify(out), (200 if out.get("ok") else 400)


@app.post("/api/analyze-config")
def analyze_config():
    return _handle(pa.analyze_config)


@app.post("/api/compare")
def compare():
    return _handle(pa.compare_configs)


@app.post("/api/sweep")
def sweep():
    return _handle(pa.sweep_configs)


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.errorhandler(413)
def too_large(_e):
    return jsonify(pa.error_json(["Request body is too large."])), 413


@app.errorhandler(404)
def not_found(_e):
    return jsonify(pa.error_json(["Not found."])), 404


@app.errorhandler(405)
def bad_method(_e):
    return jsonify(pa.error_json(["Method not allowed."])), 405


@app.errorhandler(500)
def server_error(_e):
    return jsonify(pa.error_json(["Internal server error."])), 500


@app.get("/")
def index():
    return send_from_directory(FRONTEND, "index.html")


@app.get("/<path:path>")
def static_files(path):
    if path.startswith("api/"):
        return bad_method(None) if path in POST_ROUTES else not_found(None)
    return send_from_directory(FRONTEND, path)     # send_from_directory blocks path traversal


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 5000))
    print(f"PasswordLab running at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
