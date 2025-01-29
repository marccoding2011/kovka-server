from flask import Flask, request, jsonify # , send_file
import gepi_api

app = Flask(__name__)

path_mask = len('flask_app.py')
json_path = __file__[:-path_mask] + '.sessions.json'

with open(json_path, 'w') as f:
    f.write('[]')

@app.before_request
def custom_function():
    if request.path.startswith('/api/'):
        if request.method == 'POST':
            server = gepi_api.API.load()
            path = request.path
            json = request.form.to_dict() # .get_json()
            response = server.route(path, json)
            server.save()
            return jsonify(response), 200

'''
@app.route("/favicon.ico")
def cookie():
    return send_file(".../favicon.ico", attachment_filename = "favicon.ico")
'''

if __name__ == '__main__':
    app.run()