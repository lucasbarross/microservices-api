from flask import Flask, request, jsonify
from flask_restful import Api, Resource
app = Flask(__name__)

api=Api(app)

class Multiply(Resource):
    def post(self):
        posted = request.get_json()
        x = posted["x"]
        y = posted["y"]
        x = int(x)
        y = int(y)
        prod = x * y
        ret = {
            'Message': prod,
            'Status code': 200
        }
        return jsonify(ret)
class Division(Resource):
    def post(self):
        posted = request.get_json()
        x = posted["x"]
        y = posted["y"]
        x = int(x)
        y = int(y)
        quo = x*1.0/ y
        ret = {
            'Message': quo,
            'Status code': 200
        }
        return jsonify(ret)

api.add_resource(Multiply,"/multiply")
api.add_resource(Division,"/divide")
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=True)