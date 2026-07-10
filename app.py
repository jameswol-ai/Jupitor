# app.py
from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "Hello from Jupitor!"

# app.py
from fastapi import FastAPI
app = FastAPI()

@app.get('/')
def home():
    return {"message": "Hello from Jupitor!"}