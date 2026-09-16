import os, json
from pathlib import Path
import httpx
from fastapi import FastAPI, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

BASE=Path(__file__).resolve().parent.parent
DATABASE_URL=os.getenv("DATABASE_URL","sqlite:///./data.db")
connect_args={"check_same_thread":False} if DATABASE_URL.startswith("sqlite") else {}
engine=create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal=sessionmaker(bind=engine)
Base=declarative_base()

class Product(Base):
    __tablename__="products"
    id=Column(Integer,primary_key=True)
    name=Column(String(200),default="")
    description=Column(Text,default="")
    image_url=Column(String(500),default="")
    title=Column(String(500),default="")
    selling_points=Column(Text,default="")
    detail=Column(Text,default="")
    keywords=Column(Text,default="")
    created_at=Column(DateTime,default=datetime.utcnow)

Base.metadata.create_all(engine)
app=FastAPI(title="AI Ecommerce Bot",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

def demo_generate(product):
    return {"title":f"2026新款{product}｜高质感实用型商品","selling_points":"精选材质；设计简洁耐用；适合日常使用；兼顾颜值与实用性","detail":f"{product}采用简洁现代的设计思路，突出实用性与品质感。适合日常使用、送礼及电商场景展示。","keywords":f"{product},新品,高质感,实用,电商热卖"}

async def ai_generate(product):
    if os.getenv("AI_DEMO_MODE","true").lower()=="true" or not os.getenv("AI_API_KEY"):
        return demo_generate(product)
    url=os.getenv("AI_BASE_URL","https://api.openai.com/v1").rstrip("/")+"/chat/completions"
    payload={"model":os.getenv("AI_MODEL","gpt-4o-mini"),"messages":[{"role":"system","content":"你是专业电商运营。请输出严格JSON，字段为title,selling_points,detail,keywords。"},{"role":"user","content":f"请为以下商品生成电商内容：{product}"}],"temperature":0.7}
    async with httpx.AsyncClient(timeout=60) as client:
        r=await client.post(url,json=payload,headers={"Authorization":f"Bearer {os.getenv('AI_API_KEY')}"})
        r.raise_for_status(); content=r.json()["choices"][0]["message"]["content"]
        return json.loads(content.replace("```json","").replace("```","").strip())

class ChatRequest(BaseModel): message:str

@app.get("/api/health")
def health(): return {"ok":True}

@app.get("/api/products")
def products():
    db=SessionLocal()
    try:
        return [{"id":p.id,"name":p.name,"description":p.description,"image_url":p.image_url,"title":p.title,"selling_points":p.selling_points,"detail":p.detail,"keywords":p.keywords} for p in db.query(Product).order_by(Product.id.desc()).all()]
    finally: db.close()

@app.post("/api/products")
def create_product(name:str=Form(...),description:str=Form(""),image_url:str=Form("")):
    db=SessionLocal(); p=Product(name=name,description=description,image_url=image_url); db.add(p); db.commit(); db.refresh(p); db.close(); return {"id":p.id,"message":"商品已创建"}

@app.post("/api/products/{product_id}/generate")
async def generate(product_id:int):
    db=SessionLocal(); p=db.get(Product,product_id)
    if not p: db.close(); raise HTTPException(404,"商品不存在")
    result=await ai_generate((p.name+" "+p.description).strip()); p.title=result.get("title",""); p.selling_points=result.get("selling_points",""); p.detail=result.get("detail",""); p.keywords=result.get("keywords",""); db.commit(); db.refresh(p)
    out={"id":p.id,"title":p.title,"selling_points":p.selling_points,"detail":p.detail,"keywords":p.keywords}; db.close(); return out

@app.post("/api/chat")
async def chat(req:ChatRequest):
    if os.getenv("AI_DEMO_MODE","true").lower()=="true" or not os.getenv("AI_API_KEY"):
        return {"reply":"你好！我是 AI 电商助手。你可以问我商品标题、卖点、详情页、广告文案或客服话术。当前为 Demo 模式。"}
    url=os.getenv("AI_BASE_URL","https://api.openai.com/v1").rstrip("/")+"/chat/completions"
    payload={"model":os.getenv("AI_MODEL","gpt-4o-mini"),"messages":[{"role":"system","content":"你是专业、简洁的中文电商客服与运营助手。"},{"role":"user","content":req.message}]}
    async with httpx.AsyncClient(timeout=60) as client:
        r=await client.post(url,json=payload,headers={"Authorization":f"Bearer {os.getenv('AI_API_KEY')}"}); r.raise_for_status(); return {"reply":r.json()["choices"][0]["message"]["content"]}

@app.get("/")
def index(): return FileResponse(BASE/"frontend"/"index.html")
