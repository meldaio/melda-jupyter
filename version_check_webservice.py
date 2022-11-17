import subprocess
import json

from platform import python_version
from flask import Flask, request, abort

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    if request.method == 'GET':
        return '<h1>Webhook for Ubuntu, R, and Python (and R/Python Packages) version check.', 200
    else:
        abort(400)

@app.route('/versions', methods=['GET'])
def get_versions():
    '''
    Get a request and send back version info.
    '''
    if request.method == 'GET':

        subprocess.run("get-versions", shell=True)
        with open("/home/melda/versions") as f:
            versions = json.load(f)
        
        return versions, 200
    
    else:
        abort(405)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=2310)
