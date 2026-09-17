def main() -> None:
    import uvicorn
    uvicorn.run("detect_ai.main:app", host="0.0.0.0", port=8000, reload=True)
