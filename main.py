from fastapi import FastAPI

app=FastAPI()

@app.get('/')
async def home_root():
    return {"message":"success"}

@app.get('/deploy')
async def home_root():
    return {"message":"deployed"}

@app.get('/home')
async def home_root():
    return {"message":"home"}