from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials, OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
import httpx
import asyncio
import logging
import random
import threading
import time
from typing import Optional, Dict, List, Any
import json
import secrets
import hmac
import os

# ==================== CONFIGURAÇÕES BÁSICAS ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="POISK GLOBAL", version="3.0")
templates = Jinja2Templates(directory="templates")

# ==================== CONFIGURAÇÕES ====================
ALPHA_VANTAGE_KEY = "JEFLC20NZDVK4DM9"
CACHE_TTL = 300  # 5 minutos

# Cache
cache = {}
cache_tempo = {}

# ==================== BANCO DE DADOS (OPCIONAL) ====================
from datetime import datetime

# Tenta importar SQLAlchemy, mas não quebra se não existir
try:
    from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker, Session
    SQLALCHEMY_AVAILABLE = True
    print("✅ SQLAlchemy encontrado. Banco de dados ATIVADO.")
except ImportError as e:
    SQLALCHEMY_AVAILABLE = False
    print(f"⚠️ SQLAlchemy NÃO disponível: {e}. Banco de dados DESATIVADO.")
    print("⚠️ O site continuará funcionando sem cadastro de usuários.")

# ==================== CONFIGURAÇÃO DO BANCO (SÓ SE DISPONÍVEL) ====================
if SQLALCHEMY_AVAILABLE:
    # Pega a URL do banco da variável de ambiente
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./poisk.db")

    try:
        if DATABASE_URL.startswith("postgresql"):
            # Para PostgreSQL no Render, precisamos de SSL
            engine = create_engine(DATABASE_URL, connect_args={"sslmode": "require"})
            print("✅ Conectando ao PostgreSQL...")
        else:
            # Para SQLite local (desenvolvimento)
            engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
            print("✅ Conectando ao SQLite local...")

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base = declarative_base()

        # Modelo de Usuário
        class Usuario(Base):
            __tablename__ = "usuarios"
            id = Column(Integer, primary_key=True, index=True)
            username = Column(String, unique=True, index=True)
            email = Column(String, unique=True, index=True)
            senha_hash = Column(String)
            assinante = Column(Boolean, default=False)
            data_criacao = Column(DateTime, default=datetime.now)
            ultimo_acesso = Column(DateTime, nullable=True)

        # Cria as tabelas
        Base.metadata.create_all(bind=engine)

        # Função para obter sessão do banco
        def get_db():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

        print("✅ Banco de dados configurado com sucesso!")
        BANCO_ATIVO = True

    except Exception as e:
        print(f"❌ Erro ao configurar banco de dados: {e}")
        BANCO_ATIVO = False
        SQLALCHEMY_AVAILABLE = False
else:
    BANCO_ATIVO = False

# ==================== FUNÇÃO DE FALLBACK PARA QUANDO NÃO TEM BANCO ====================
async def get_db_fallback():
    """Retorna None quando o banco não está disponível"""
    yield None
    return

# Decide qual função de banco usar
get_db_actual = get_db if SQLALCHEMY_AVAILABLE and BANCO_ATIVO else get_db_fallback

# ==================== SISTEMA DE AUTENTICAÇÃO ====================
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = "seu_segredo_super_forte_mude_isso_123"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def verificar_senha(senha, senha_hash):
    return pwd_context.verify(senha, senha_hash)

def gerar_hash_senha(senha):
    return pwd_context.hash(senha)

def criar_token_acesso(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db_actual)):
    if not SQLALCHEMY_AVAILABLE or not BANCO_ATIVO:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível no momento",
        )
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(Usuario).filter(Usuario.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# ==================== ROTAS DE AUTENTICAÇÃO ====================
from fastapi import APIRouter

auth_router = APIRouter(prefix="/auth", tags=["Autenticação"])

@auth_router.post("/registrar")
async def registrar(
    username: str,
    email: str,
    password: str,
    db: Session = Depends(get_db_actual)
):
    # Se não tem banco, retorna erro amigável
    if not SQLALCHEMY_AVAILABLE or not BANCO_ATIVO:
        return {
            "msg": "Banco de dados não disponível no momento",
            "status": "warning",
            "dica": "O site continuará funcionando sem cadastro de usuários"
        }
    
    # Verifica se já existe
    if db.query(Usuario).filter(Usuario.username == username).first():
        raise HTTPException(status_code=400, detail="Usuário já existe")
    
    if db.query(Usuario).filter(Usuario.email == email).first():
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    
    # Cria usuário
    usuario = Usuario(
        username=username,
        email=email,
        senha_hash=gerar_hash_senha(password)
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    
    return {"msg": "Usuário criado com sucesso", "username": usuario.username}

@auth_router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db_actual)
):
    if not SQLALCHEMY_AVAILABLE or not BANCO_ATIVO:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados não disponível no momento",
        )
    
    usuario = db.query(Usuario).filter(
        Usuario.username == form_data.username
    ).first()
    
    if not usuario or not verificar_senha(form_data.password, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    usuario.ultimo_acesso = datetime.utcnow()
    db.commit()
    
    access_token = criar_token_acesso(
        data={"sub": usuario.username}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": usuario.username,
        "assinante": usuario.assinante
    }

@auth_router.get("/me")
async def me(current_user: Usuario = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "email": current_user.email,
        "assinante": current_user.assinante,
        "criado_em": current_user.data_criacao,
        "ultimo_acesso": current_user.ultimo_acesso
    }

# ==================== INCLUI AS ROTAS NO APP ====================
app.include_router(auth_router)

# ==================== SISTEMA DE ATUALIZAÇÃO AUTOMÁTICA ====================

# Dados em tempo real (simulados)
dados_tempo_real = {
    'dolar': 5.85,
    'bitcoin': 65432,
    'ibovespa': 128500,
    'sp500': 5200,
    'nasdaq': 18500,
    'nikkei': 38500,
    'ultima_atualizacao': datetime.now()
}

def gerar_variacao():
    return round(random.uniform(-2.5, 3.5), 2)

def atualizar_dados_automatico():
    global dados_tempo_real
    
    while True:
        try:
            dados_tempo_real['dolar'] = round(dados_tempo_real['dolar'] * (1 + random.uniform(-0.005, 0.005)), 2)
            dados_tempo_real['bitcoin'] = round(dados_tempo_real['bitcoin'] * (1 + random.uniform(-0.02, 0.03)), 0)
            dados_tempo_real['ibovespa'] = round(dados_tempo_real['ibovespa'] * (1 + random.uniform(-0.01, 0.015)), 0)
            dados_tempo_real['sp500'] = round(dados_tempo_real['sp500'] * (1 + random.uniform(-0.008, 0.012)), 0)
            dados_tempo_real['nasdaq'] = round(dados_tempo_real['nasdaq'] * (1 + random.uniform(-0.015, 0.02)), 0)
            dados_tempo_real['nikkei'] = round(dados_tempo_real['nikkei'] * (1 + random.uniform(-0.012, 0.018)), 0)
            
            dados_tempo_real['ultima_atualizacao'] = datetime.now()
            
            print(f"🔄 Dados atualizados em: {dados_tempo_real['ultima_atualizacao'].strftime('%H:%M:%S')}")
            print(f"   Dólar: R$ {dados_tempo_real['dolar']} | Bitcoin: ${dados_tempo_real['bitcoin']:,.0f}")
            
        except Exception as e:
            print(f"Erro na atualização: {e}")
        
        time.sleep(60)

# Inicia a thread de atualização automática
thread_atualizacao = threading.Thread(target=atualizar_dados_automatico, daemon=True)
thread_atualizacao.start()
print("✅ Sistema de atualização automática iniciado (a cada 60 segundos)")

# ==================== DADOS GLOBAIS ====================

# AMÉRICA DO SUL
SOUTH_AMERICA = [
    {'ticker': 'PETR4.SA', 'nome': 'Petrobras', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Petróleo'},
    {'ticker': 'VALE3.SA', 'nome': 'Vale', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Mineração'},
    {'ticker': 'ITUB4.SA', 'nome': 'Itaú', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Bancário'},
    {'ticker': 'BBDC4.SA', 'nome': 'Bradesco', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Bancário'},
    {'ticker': 'ABEV3.SA', 'nome': 'Ambev', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Bebidas'},
    {'ticker': 'WEGE3.SA', 'nome': 'WEG', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Industrial'},
    {'ticker': 'BBAS3.SA', 'nome': 'Banco do Brasil', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Bancário'},
    {'ticker': 'AAPL', 'nome': 'Apple', 'pais': 'EUA', 'bandeira': '🇺🇸', 'setor': 'Tecnologia'},
    {'ticker': 'MSFT', 'nome': 'Microsoft', 'pais': 'EUA', 'bandeira': '🇺🇸', 'setor': 'Tecnologia'},
]

# ==================== FUNÇÕES AUXILIARES ====================

def enriquecer_dados(ativos):
    enriquecidos = []
    for ativo in ativos:
        seed = hash(ativo['ticker']) % 1000
        preco_base = 10 + (seed % 490)
        variacao = gerar_variacao()
        preco_atual = round(preco_base * (1 + variacao/100), 2)
        
        ativo['preco'] = preco_atual
        ativo['variacao'] = variacao
        ativo['variacao_class'] = 'positive' if variacao > 0 else 'negative'
        ativo['min_52'] = round(preco_base * 0.85, 2)
        ativo['max_52'] = round(preco_base * 1.25, 2)
        ativo['volume'] = f"{round(random.uniform(1, 50), 1)}M"
        ativo['dy'] = f"{round(random.uniform(2, 8), 1)}%"
        ativo['pvp'] = round(random.uniform(0.8, 1.3), 2)
        enriquecidos.append(ativo)
    return enriquecidos

# ==================== ALGORITMO POISK SCORE ====================

class AlgoritmoPOISK:
    """
    Algoritmo proprietário do POISK - Versão 1.0
    """
    
    def __init__(self):
        self.nome = "POISK Score v1.0"
        self.pesos = {
            "valorizacao": 0.30,
            "volume": 0.20,
            "rsi": 0.20,
            "fundamentos": 0.30
        }
        self.FATOR_POISK = 1.382
    
    def calcular_score(self, acao):
        score = 0
        criterios = []
        
        # 1. VALORIZAÇÃO
        variacao = acao.get('variacao', 0)
        if variacao > 5:
            score += 30 * self.pesos["valorizacao"]
            criterios.append("📈 Valorização forte (+5%)")
        elif variacao > 2:
            score += 20 * self.pesos["valorizacao"]
            criterios.append("📈 Valorização moderada (+2%)")
        elif variacao > 0:
            score += 10 * self.pesos["valorizacao"]
            criterios.append("📈 Valorização positiva")
        elif variacao < -5:
            score -= 20 * self.pesos["valorizacao"]
            criterios.append("📉 Queda forte (-5%)")
        
        # 2. VOLUME
        volume_atual = acao.get('volume_num', 1000000)
        volume_medio = acao.get('volume_medio_num', volume_atual)
        
        if volume_atual > volume_medio * 2:
            score += 30 * self.pesos["volume"]
            criterios.append("🔥 Volume 2x acima da média")
        elif volume_atual > volume_medio * 1.5:
            score += 20 * self.pesos["volume"]
            criterios.append("📊 Volume 50% acima da média")
        elif volume_atual > volume_medio:
            score += 10 * self.pesos["volume"]
            criterios.append("📊 Volume acima da média")
        
        # 3. RSI
        rsi = acao.get('rsi', 50)
        if rsi < 30:
            score += 25 * self.pesos["rsi"]
            criterios.append("🎯 RSI indicando sobrevenda")
        elif rsi > 70:
            score -= 15 * self.pesos["rsi"]
            criterios.append("⚠️ RSI indicando sobrecompra")
        elif rsi > 50:
            score += 10 * self.pesos["rsi"]
            criterios.append("✅ RSI em região positiva")
        
        # 4. FUNDAMENTOS
        dy = acao.get('dy_percent', 0)
        if dy > 8:
            score += 30 * self.pesos["fundamentos"]
            criterios.append(f"💰 DY excepcional: {dy}%")
        elif dy > 5:
            score += 20 * self.pesos["fundamentos"]
            criterios.append(f"💰 Bom DY: {dy}%")
        elif dy > 2:
            score += 10 * self.pesos["fundamentos"]
            criterios.append(f"💰 DY positivo: {dy}%")
        
        # FATOR POISK
        score_final = score * self.FATOR_POISK
        
        # Classificação
        if score_final >= 70:
            recomendacao = "COMPRA FORTE"
            cor = "#00ff88"
            emoji = "🚀"
        elif score_final >= 50:
            recomendacao = "COMPRA"
            cor = "#4CAF50"
            emoji = "📈"
        elif score_final >= 30:
            recomendacao = "NEUTRO"
            cor = "#FFC107"
            emoji = "⚖️"
        elif score_final >= 15:
            recomendacao = "ATENÇÃO"
            cor = "#FF9800"
            emoji = "⚠️"
        else:
            recomendacao = "EVITAR"
            cor = "#F44336"
            emoji = "🔻"
        
        return {
            "score": round(score_final, 1),
            "recomendacao": recomendacao,
            "cor": cor,
            "emoji": emoji,
            "criterios": criterios[:4]
        }

# Instancia o algoritmo
algoritmo_poisk = AlgoritmoPOISK()

# ==================== ROTAS PRINCIPAIS ====================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Dados básicos para o template
    stats = {
        'acoes': len(SOUTH_AMERICA),
        'paises': 42,
        'apis': 52,
        'fiis': 10
    }
    
    return templates.TemplateResponse(
        "poisk_global_robusto.html",
        {
            "request": request,
            "south_america": enriquecer_dados(SOUTH_AMERICA),
            "stats": stats,
            "dolar": dados_tempo_real['dolar'],
            "bitcoin": dados_tempo_real['bitcoin'],
            "data": datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            "ultima_atualizacao": dados_tempo_real['ultima_atualizacao'].strftime('%H:%M:%S'),
        }
    )

@app.get("/algoritmo", response_class=HTMLResponse)
async def pagina_algoritmo(request: Request):
    """Página do algoritmo POISK"""
    
    import random
    acoes_com_score = []
    
    for acao in SOUTH_AMERICA[:8]:
        dados_acao = {
            'variacao': round(random.uniform(-6, 8), 2),
            'volume_num': random.randint(100000, 5000000),
            'volume_medio_num': random.randint(500000, 2000000),
            'rsi': random.randint(20, 80),
            'dy_percent': round(random.uniform(2, 10), 2)
        }
        
        score = algoritmo_poisk.calcular_score(dados_acao)
        
        acoes_com_score.append({
            'ticker': acao['ticker'],
            'nome': acao['nome'],
            'score': score['score'],
            'recomendacao': score['recomendacao'],
            'cor': score['cor'],
            'emoji': score['emoji'],
            'criterios': score['criterios']
        })
    
    acoes_com_score.sort(key=lambda x: x['score'], reverse=True)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>POISK Algoritmo</title>
        <style>
            * {{ margin:0; padding:0; box-sizing:border-box; }}
            body {{ background:#0a0a0a; color:#fff; font-family: 'Segoe UI', sans-serif; padding:20px; }}
            .container {{ max-width:1200px; margin:0 auto; }}
            .header {{ background:linear-gradient(145deg, #1a1a1a, #0a0a0a); padding:30px; border-radius:15px; text-align:center; }}
            .logo {{ font-size:3em; font-weight:bold; background:linear-gradient(45deg, #00ff88, #00ccff); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
            .cards-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(350px, 1fr)); gap:20px; margin-top:20px; }}
            .card {{ background:#1a1a1a; border-radius:15px; padding:20px; border:1px solid #333; }}
            .ticker {{ font-size:1.5em; font-weight:bold; color:#00ff88; }}
            .score {{ font-size:2.5em; font-weight:bold; }}
            .criterios {{ background:#2a2a2a; padding:15px; border-radius:8px; margin-top:15px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">🔍 POISK ALGORITMO</div>
                <p style="color:#888;">Algoritmo proprietário v1.0</p>
                <a href="/" style="color:#00ff88;">← Voltar ao site</a>
            </div>
            
            <h2 style="color:#00ff88;">📊 RANKING POISK SCORE</h2>
            <div class="cards-grid">
    """
    
    for acao in acoes_com_score:
        html += f"""
                <div class="card">
                    <div class="card-header">
                        <span class="ticker">{acao['ticker']}</span>
                        <span style="color:{acao['cor']};">{acao['emoji']}</span>
                    </div>
                    <div>{acao['nome']}</div>
                    <div class="score" style="color:{acao['cor']};">{acao['score']}</div>
                    <div style="color:{acao['cor']};">{acao['recomendacao']}</div>
                    <div class="criterios">
                        <h4 style="color:#00ff88;">🔍 Análise:</h4>
        """
        for criterio in acao['criterios']:
            html += f'<div>• {criterio}</div>'
        html += "</div></div>"
    
    html += """
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)

@app.get("/api/algoritmo/{ticker}")
async def api_algoritmo(ticker: str):
    import random
    dados_acao = {
        'variacao': round(random.uniform(-6, 8), 2),
        'volume_num': random.randint(100000, 5000000),
        'volume_medio_num': random.randint(500000, 2000000),
        'rsi': random.randint(20, 80),
        'dy_percent': round(random.uniform(2, 10), 2)
    }
    resultado = algoritmo_poisk.calcular_score(dados_acao)
    resultado['ticker'] = ticker
    return resultado

# ==================== ADMIN ====================

security = HTTPBasic()

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "poisk2026"

def verificar_admin(credentials: HTTPBasicCredentials = Depends(security)):
    is_username_correct = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    is_password_correct = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    
    if not (is_username_correct and is_password_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso negado",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, username: str = Depends(verificar_admin)):
    stats = {
        "servidor": {
            "status": "online",
            "versao": "3.1.0",
            "apis_integradas": 52,
        },
        "dados_tempo_real": {
            "dolar": dados_tempo_real['dolar'],
            "bitcoin": dados_tempo_real['bitcoin'],
            "ultima_atualizacao": dados_tempo_real['ultima_atualizacao'].strftime('%H:%M:%S'),
        }
    }
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>POISK Admin</title>
    <style>
        body {{ background:#0a0a0a; color:#fff; font-family:'Segoe UI'; padding:20px; }}
        .container {{ max-width:800px; margin:0 auto; }}
        .card {{ background:#1a1a1a; padding:20px; border-radius:10px; margin:10px 0; }}
        .btn {{ background:#00ff88; color:#000; padding:10px 20px; text-decoration:none; border-radius:5px; }}
    </style>
    </head>
    <body>
        <div class="container">
            <h1>👑 POISK ADMIN</h1>
            <div class="card">
                <h3>Bem-vindo, {username}</h3>
                <p>Dólar: R$ {stats['dados_tempo_real']['dolar']:.2f}</p>
                <p>Bitcoin: $ {stats['dados_tempo_real']['bitcoin']:,.0f}</p>
                <p>Última atualização: {stats['dados_tempo_real']['ultima_atualizacao']}</p>
                <p>Banco de dados: {'✅ ATIVO' if SQLALCHEMY_AVAILABLE and BANCO_ATIVO else '⚠️ DESATIVADO'}</p>
                <a href="/" class="btn">🌍 Ver Site</a>
                <a href="/algoritmo" class="btn">🤖 Algoritmo</a>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

# ==================== EXECUÇÃO ====================

if __name__ == "__main__":
    import uvicorn
    print("="*80)
    print("🌍 POISK GLOBAL - VERSÃO COMPLETA")
    print("="*80)
    print("📊 Ações: 70+")
    print("🌎 Países: 42")
    print("📰 Notícias: 50+")
    print("⚡ Atualização automática: a cada 60 segundos")
    print(f"💾 Banco de dados: {'✅ ATIVO' if SQLALCHEMY_AVAILABLE and BANCO_ATIVO else '⚠️ DESATIVADO'}")
    print("📱 Site: http://localhost:8000")
    print("📚 Documentação: http://localhost:8000/docs")
    print("="*80)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
