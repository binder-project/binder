from flask import Flask
import os

app = Flask(__name__)

@app.route('/login', methods=['GET', 'POST'])
def main():
    if request.method == 'GET':
        return str(os.environ)

if __name__ == "__main__":
    app.run(host="0.0.0.0")
