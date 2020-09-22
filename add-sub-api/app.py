from flask import Flask, request, jsonify
from flask_restful import Api, Resource
app = Flask(__name__)

api=Api(app)

class Add(Resource):
    def post(self):
        posted = request.get_json()
        x = posted["x"]
        y = posted["y"]
        x = int(x)
        y = int(y)
        sum = x+y
        ret = {
            'Message': sum,
            'Status code': 200
        }
        return jsonify(ret)

class Sub(Resource):
    def post(self):
        posted = request.get_json()
        x = posted["x"]
        y = posted["y"]
        x = int(x)
        y = int(y)
        diff = x-y
        ret = {
            'Message': diff,
            'Status code': 200
        }
        return jsonify(ret)

api.add_resource(Add, "/add")
api.add_resource(Sub,"/sub")
if __name__ == "__main__":
    app.run(host='0.0.0.0', port= 5000, debug=True)
