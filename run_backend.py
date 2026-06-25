import uvicorn, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PYTHONPATH"] = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, log_level="info", reload=True)
