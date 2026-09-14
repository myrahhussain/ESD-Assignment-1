from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "This is Myrah's invoice job queue."  
if __name__ == "__main__":
    app.run(debug=True)