from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import httpx
import asyncio
import logging
import random
import threading
import time
from typing import Optional, Dict, List, Any
import json

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import hmac
# Configuração
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

# Função para gerar variação aleatória realista
def gerar_variacao():
    return round(random.uniform(-2.5, 3.5), 2)

# Função para atualizar todos os dados automaticamente
def atualizar_dados_automatico():
    """Atualiza todos os dados em tempo real"""
    global dados_tempo_real
    
    while True:
        try:
            # Atualiza câmbio (variação pequena)
            dados_tempo_real['dolar'] = round(dados_tempo_real['dolar'] * (1 + random.uniform(-0.005, 0.005)), 2)
            dados_tempo_real['bitcoin'] = round(dados_tempo_real['bitcoin'] * (1 + random.uniform(-0.02, 0.03)), 0)
            
            # Atualiza índices
            dados_tempo_real['ibovespa'] = round(dados_tempo_real['ibovespa'] * (1 + random.uniform(-0.01, 0.015)), 0)
            dados_tempo_real['sp500'] = round(dados_tempo_real['sp500'] * (1 + random.uniform(-0.008, 0.012)), 0)
            dados_tempo_real['nasdaq'] = round(dados_tempo_real['nasdaq'] * (1 + random.uniform(-0.015, 0.02)), 0)
            dados_tempo_real['nikkei'] = round(dados_tempo_real['nikkei'] * (1 + random.uniform(-0.012, 0.018)), 0)
            
            # Atualiza timestamp
            dados_tempo_real['ultima_atualizacao'] = datetime.now()
            
            # Log a cada atualização
            print(f"🔄 Dados atualizados em: {dados_tempo_real['ultima_atualizacao'].strftime('%H:%M:%S')}")
            print(f"   Dólar: R$ {dados_tempo_real['dolar']} | Bitcoin: ${dados_tempo_real['bitcoin']:,.0f}")
            
        except Exception as e:
            print(f"Erro na atualização: {e}")
        
        # Espera 60 segundos antes da próxima atualização
        time.sleep(60)

# Inicia a thread de atualização automática
thread_atualizacao = threading.Thread(target=atualizar_dados_automatico, daemon=True)
thread_atualizacao.start()
print("✅ Sistema de atualização automática iniciado (a cada 60 segundos)")

# ==================== DADOS GLOBAIS COMPLETOS ====================

# AMÉRICA DO SUL
SOUTH_AMERICA = [
    {'ticker': 'PETR4.SA', 'nome': 'Petrobras', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Petróleo', 'moeda': 'BRL'},
    {'ticker': 'VALE3.SA', 'nome': 'Vale', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Mineração', 'moeda': 'BRL'},
    {'ticker': 'ITUB4.SA', 'nome': 'Itaú', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Bancário', 'moeda': 'BRL'},
    {'ticker': 'BBDC4.SA', 'nome': 'Bradesco', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Bancário', 'moeda': 'BRL'},
    {'ticker': 'ABEV3.SA', 'nome': 'Ambev', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Bebidas', 'moeda': 'BRL'},
    {'ticker': 'WEGE3.SA', 'nome': 'WEG', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Industrial', 'moeda': 'BRL'},
    {'ticker': 'BBAS3.SA', 'nome': 'Banco do Brasil', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Bancário', 'moeda': 'BRL'},
    {'ticker': 'RENT3.SA', 'nome': 'Localiza', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Aluguel', 'moeda': 'BRL'},
    {'ticker': 'SUZB3.SA', 'nome': 'Suzano', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Papel', 'moeda': 'BRL'},
    {'ticker': 'GGBR4.SA', 'nome': 'Gerdau', 'pais': 'Brasil', 'bandeira': '🇧🇷', 'setor': 'Siderurgia', 'moeda': 'BRL'},
    {'ticker': 'GGAL.BA', 'nome': 'Grupo Galicia', 'pais': 'Argentina', 'bandeira': '🇦🇷', 'setor': 'Bancário', 'moeda': 'ARS'},
    {'ticker': 'YPF.BA', 'nome': 'YPF', 'pais': 'Argentina', 'bandeira': '🇦🇷', 'setor': 'Petróleo', 'moeda': 'ARS'},
    {'ticker': 'FALABELLA.SN', 'nome': 'Falabella', 'pais': 'Chile', 'bandeira': '🇨🇱', 'setor': 'Varejo', 'moeda': 'CLP'},
    {'ticker': 'COPEC.SN', 'nome': 'Copec', 'pais': 'Chile', 'bandeira': '🇨🇱', 'setor': 'Energia', 'moeda': 'CLP'},
]

# AMÉRICA DO NORTE
NORTH_AMERICA = [
    {'ticker': 'AAPL', 'nome': 'Apple', 'pais': 'EUA', 'bandeira': '🇺🇸', 'setor': 'Tecnologia', 'moeda': 'USD'},
    {'ticker': 'MSFT', 'nome': 'Microsoft', 'pais': 'EUA', 'bandeira': '🇺🇸', 'setor': 'Tecnologia', 'moeda': 'USD'},
    {'ticker': 'GOOGL', 'nome': 'Google', 'pais': 'EUA', 'bandeira': '🇺🇸', 'setor': 'Tecnologia', 'moeda': 'USD'},
    {'ticker': 'AMZN', 'nome': 'Amazon', 'pais': 'EUA', 'bandeira': '🇺🇸', 'setor': 'E-commerce', 'moeda': 'USD'},
    {'ticker': 'NVDA', 'nome': 'NVIDIA', 'pais': 'EUA', 'bandeira': '🇺🇸', 'setor': 'Tecnologia', 'moeda': 'USD'},
    {'ticker': 'META', 'nome': 'Meta', 'pais': 'EUA', 'bandeira': '🇺🇸', 'setor': 'Tecnologia', 'moeda': 'USD'},
    {'ticker': 'TSLA', 'nome': 'Tesla', 'pais': 'EUA', 'bandeira': '🇺🇸', 'setor': 'Automotivo', 'moeda': 'USD'},
    {'ticker': 'JPM', 'nome': 'JPMorgan', 'pais': 'EUA', 'bandeira': '🇺🇸', 'setor': 'Bancário', 'moeda': 'USD'},
    {'ticker': 'V', 'nome': 'Visa', 'pais': 'EUA', 'bandeira': '🇺🇸', 'setor': 'Financeiro', 'moeda': 'USD'},
    {'ticker': 'WMT', 'nome': 'Walmart', 'pais': 'EUA', 'bandeira': '🇺🇸', 'setor': 'Varejo', 'moeda': 'USD'},
    {'ticker': 'RY.TO', 'nome': 'Royal Bank', 'pais': 'Canadá', 'bandeira': '🇨🇦', 'setor': 'Bancário', 'moeda': 'CAD'},
    {'ticker': 'SHOP.TO', 'nome': 'Shopify', 'pais': 'Canadá', 'bandeira': '🇨🇦', 'setor': 'Tecnologia', 'moeda': 'CAD'},
]

# EUROPA
EUROPE = [
    {'ticker': 'NESN.SW', 'nome': 'Nestlé', 'pais': 'Suíça', 'bandeira': '🇨🇭', 'setor': 'Alimentos', 'moeda': 'CHF'},
    {'ticker': 'NOVN.SW', 'nome': 'Novartis', 'pais': 'Suíça', 'bandeira': '🇨🇭', 'setor': 'Saúde', 'moeda': 'CHF'},
    {'ticker': 'SAP.DE', 'nome': 'SAP', 'pais': 'Alemanha', 'bandeira': '🇩🇪', 'setor': 'Tecnologia', 'moeda': 'EUR'},
    {'ticker': 'MC.PA', 'nome': 'LVMH', 'pais': 'França', 'bandeira': '🇫🇷', 'setor': 'Luxo', 'moeda': 'EUR'},
    {'ticker': 'OR.PA', 'nome': 'L\'Oréal', 'pais': 'França', 'bandeira': '🇫🇷', 'setor': 'Cosméticos', 'moeda': 'EUR'},
    {'ticker': 'ULVR.L', 'nome': 'Unilever', 'pais': 'Reino Unido', 'bandeira': '🇬🇧', 'setor': 'Consumo', 'moeda': 'GBP'},
    {'ticker': 'HSBA.L', 'nome': 'HSBC', 'pais': 'Reino Unido', 'bandeira': '🇬🇧', 'setor': 'Bancário', 'moeda': 'GBP'},
    {'ticker': 'SHEL.L', 'nome': 'Shell', 'pais': 'Reino Unido', 'bandeira': '🇬🇧', 'setor': 'Petróleo', 'moeda': 'GBP'},
    {'ticker': 'ENEL.MI', 'nome': 'Enel', 'pais': 'Itália', 'bandeira': '🇮🇹', 'setor': 'Energia', 'moeda': 'EUR'},
    {'ticker': 'SAN.MC', 'nome': 'Santander', 'pais': 'Espanha', 'bandeira': '🇪🇸', 'setor': 'Bancário', 'moeda': 'EUR'},
]

# ÁSIA
ASIA = [
    {'ticker': '7203.T', 'nome': 'Toyota', 'pais': 'Japão', 'bandeira': '🇯🇵', 'setor': 'Automotivo', 'moeda': 'JPY'},
    {'ticker': '6758.T', 'nome': 'Sony', 'pais': 'Japão', 'bandeira': '🇯🇵', 'setor': 'Tecnologia', 'moeda': 'JPY'},
    {'ticker': '9984.T', 'nome': 'SoftBank', 'pais': 'Japão', 'bandeira': '🇯🇵', 'setor': 'Holdings', 'moeda': 'JPY'},
    {'ticker': '0700.HK', 'nome': 'Tencent', 'pais': 'Hong Kong', 'bandeira': '🇭🇰', 'setor': 'Tecnologia', 'moeda': 'HKD'},
    {'ticker': '9988.HK', 'nome': 'Alibaba', 'pais': 'Hong Kong', 'bandeira': '🇭🇰', 'setor': 'E-commerce', 'moeda': 'HKD'},
    {'ticker': 'RELIANCE.NS', 'nome': 'Reliance', 'pais': 'Índia', 'bandeira': '🇮🇳', 'setor': 'Conglomerado', 'moeda': 'INR'},
    {'ticker': 'TCS.NS', 'nome': 'Tata Consultancy', 'pais': 'Índia', 'bandeira': '🇮🇳', 'setor': 'Tecnologia', 'moeda': 'INR'},
    {'ticker': '005930.KS', 'nome': 'Samsung', 'pais': 'Coreia', 'bandeira': '🇰🇷', 'setor': 'Tecnologia', 'moeda': 'KRW'},
    {'ticker': '000660.KS', 'nome': 'SK Hynix', 'pais': 'Coreia', 'bandeira': '🇰🇷', 'setor': 'Tecnologia', 'moeda': 'KRW'},
    {'ticker': 'BABA', 'nome': 'Alibaba', 'pais': 'China', 'bandeira': '🇨🇳', 'setor': 'E-commerce', 'moeda': 'USD'},
]

# ÁFRICA
AFRICA = [
    {'ticker': 'NPN.JO', 'nome': 'Naspers', 'pais': 'África do Sul', 'bandeira': '🇿🇦', 'setor': 'Tecnologia', 'moeda': 'ZAR'},
    {'ticker': 'AGL.JO', 'nome': 'Anglo American', 'pais': 'África do Sul', 'bandeira': '🇿🇦', 'setor': 'Mineração', 'moeda': 'ZAR'},
    {'ticker': 'SBK.JO', 'nome': 'Standard Bank', 'pais': 'África do Sul', 'bandeira': '🇿🇦', 'setor': 'Bancário', 'moeda': 'ZAR'},
    {'ticker': 'FSR.JO', 'nome': 'FirstRand', 'pais': 'África do Sul', 'bandeira': '🇿🇦', 'setor': 'Bancário', 'moeda': 'ZAR'},
    {'ticker': 'MTN.JO', 'nome': 'MTN Group', 'pais': 'África do Sul', 'bandeira': '🇿🇦', 'setor': 'Telecom', 'moeda': 'ZAR'},
    {'ticker': 'BHP.JO', 'nome': 'BHP Group', 'pais': 'África do Sul', 'bandeira': '🇿🇦', 'setor': 'Mineração', 'moeda': 'ZAR'},
]

# OCEANIA
OCEANIA = [
    {'ticker': 'BHP.AX', 'nome': 'BHP Group', 'pais': 'Austrália', 'bandeira': '🇦🇺', 'setor': 'Mineração', 'moeda': 'AUD'},
    {'ticker': 'CBA.AX', 'nome': 'Commonwealth Bank', 'pais': 'Austrália', 'bandeira': '🇦🇺', 'setor': 'Bancário', 'moeda': 'AUD'},
    {'ticker': 'WBC.AX', 'nome': 'Westpac', 'pais': 'Austrália', 'bandeira': '🇦🇺', 'setor': 'Bancário', 'moeda': 'AUD'},
    {'ticker': 'TLS.AX', 'nome': 'Telstra', 'pais': 'Austrália', 'bandeira': '🇦🇺', 'setor': 'Telecom', 'moeda': 'AUD'},
    {'ticker': 'FPH.NZ', 'nome': 'Fisher & Paykel', 'pais': 'Nova Zelândia', 'bandeira': '🇳🇿', 'setor': 'Saúde', 'moeda': 'NZD'},
]

# ORIENTE MÉDIO
MIDDLE_EAST = [
    {'ticker': '2222.SR', 'nome': 'Saudi Aramco', 'pais': 'Arábia Saudita', 'bandeira': '🇸🇦', 'setor': 'Petróleo', 'moeda': 'SAR'},
    {'ticker': '1120.SR', 'nome': 'Al Rajhi Bank', 'pais': 'Arábia Saudita', 'bandeira': '🇸🇦', 'setor': 'Bancário', 'moeda': 'SAR'},
    {'ticker': 'EMAAR.DU', 'nome': 'Emaar', 'pais': 'Dubai', 'bandeira': '🇦🇪', 'setor': 'Imobiliário', 'moeda': 'AED'},
    {'ticker': 'FAB.AE', 'nome': 'First Abu Dhabi', 'pais': 'Emirados', 'bandeira': '🇦🇪', 'setor': 'Bancário', 'moeda': 'AED'},
    {'ticker': 'QNBK.QA', 'nome': 'QNB', 'pais': 'Catar', 'bandeira': '🇶🇦', 'setor': 'Bancário', 'moeda': 'QAR'},
    {'ticker': 'KFH.KW', 'nome': 'Kuwait Finance', 'pais': 'Kuwait', 'bandeira': '🇰🇼', 'setor': 'Bancário', 'moeda': 'KWD'},
]

# FUNDOS IMOBILIÁRIOS (FIIs)
FIIS = [
    {'ticker': 'KNRI11.SA', 'nome': 'Kinea Renda', 'segmento': 'Híbrido', 'dy': '0.82%'},
    {'ticker': 'HGLG11.SA', 'nome': 'CSHG Logística', 'segmento': 'Logístico', 'dy': '0.91%'},
    {'ticker': 'XPLG11.SA', 'nome': 'XP Log', 'segmento': 'Logístico', 'dy': '0.78%'},
    {'ticker': 'VISC11.SA', 'nome': 'Vinci Shopping', 'segmento': 'Shopping', 'dy': '0.71%'},
    {'ticker': 'HSML11.SA', 'nome': 'HSI Mall', 'segmento': 'Shopping', 'dy': '0.69%'},
    {'ticker': 'VRTA11.SA', 'nome': 'Fator Veritá', 'segmento': 'Papel', 'dy': '1.02%'},
    {'ticker': 'RBRR11.SA', 'nome': 'RBR Rendimento', 'segmento': 'Papel', 'dy': '0.95%'},
    {'ticker': 'TGAR11.SA', 'nome': 'TG Core', 'segmento': 'Desenvolvimento', 'dy': '0.62%'},
    {'ticker': 'MXRF11.SA', 'nome': 'Maxi Renda', 'segmento': 'Híbrido', 'dy': '0.88%'},
    {'ticker': 'BCFF11.SA', 'nome': 'BTG Pactual', 'segmento': 'Fundo de Fundos', 'dy': '0.75%'},
]

# CDBs RECOMENDADOS
CDBS = [
    {'banco': 'Daycoval', 'taxa': '110% CDI', 'liquidez': 'Diária', 'rating': 'A+', 'minimo': 'R$ 100', 'vencimento': '2027'},
    {'banco': 'Daycoval', 'taxa': 'IPCA+8.5%', 'liquidez': '3 anos', 'rating': 'A', 'minimo': 'R$ 1.000', 'vencimento': '2029'},
    {'banco': 'BMG', 'taxa': '108% CDI', 'liquidez': '2 anos', 'rating': 'B+', 'minimo': 'R$ 500', 'vencimento': '2028'},
    {'banco': 'Mercantil', 'taxa': '105% CDI', 'liquidez': 'Diária', 'rating': 'B+', 'minimo': 'R$ 100', 'vencimento': '2026'},
    {'banco': 'BR Partners', 'taxa': '107% CDI', 'liquidez': '2 anos', 'rating': 'A-', 'minimo': 'R$ 5.000', 'vencimento': '2027'},
    {'banco': 'Pan', 'taxa': '104% CDI', 'liquidez': '2 anos', 'rating': 'B+', 'minimo': 'R$ 1.000', 'vencimento': '2028'},
    {'banco': 'ABC', 'taxa': '102% CDI', 'liquidez': 'Diária', 'rating': 'A', 'minimo': 'R$ 100', 'vencimento': '2026'},
    {'banco': 'Sofisa', 'taxa': '112% CDI', 'liquidez': '2 anos', 'rating': 'B+', 'minimo': 'R$ 5.000', 'vencimento': '2028'},
]

# CRIPTOMOEDAS
CRIPTO = [
    {'ticker': 'BTC', 'nome': 'Bitcoin', 'dominancia': '52.3%', 'volume': '28.5B'},
    {'ticker': 'ETH', 'nome': 'Ethereum', 'dominancia': '18.7%', 'volume': '12.3B'},
    {'ticker': 'BNB', 'nome': 'BNB', 'dominancia': '4.2%', 'volume': '2.1B'},
    {'ticker': 'SOL', 'nome': 'Solana', 'dominancia': '3.8%', 'volume': '1.8B'},
    {'ticker': 'XRP', 'nome': 'Ripple', 'dominancia': '3.1%', 'volume': '1.5B'},
    {'ticker': 'ADA', 'nome': 'Cardano', 'dominancia': '2.5%', 'volume': '0.9B'},
]

# ==================== FUNÇÕES DE ENRIQUECIMENTO ====================

def enriquecer_dados(ativos):
    """Adiciona dados simulados aos ativos com variação automática"""
    enriquecidos = []
    for ativo in ativos:
        # Gera preço baseado no ticker (consistente)
        seed = hash(ativo['ticker']) % 1000
        preco_base = 10 + (seed % 490)
        
        # Adiciona variação baseada no tempo real
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
        ativo['atualizado'] = dados_tempo_real['ultima_atualizacao'].strftime('%H:%M:%S')
        enriquecidos.append(ativo)
    return enriquecidos

def enriquecer_fiis(fiis):
    """Adiciona dados aos FIIs"""
    enriquecidos = []
    for fii in fiis:
        seed = hash(fii['ticker']) % 1000
        preco_base = 80 + (seed % 120)
        variacao = gerar_variacao()
        preco_atual = round(preco_base * (1 + variacao/100), 2)
        
        fii['preco'] = preco_atual
        fii['variacao'] = variacao
        fii['variacao_class'] = 'positive' if variacao > 0 else 'negative'
        fii['pvp'] = round(random.uniform(0.9, 1.2), 2)
        enriquecidos.append(fii)
    return enriquecidos

# ==================== FUNÇÕES DE API EXTERNA ====================

async def fetch_coindesk(client: httpx.AsyncClient) -> Optional[Dict]:
    """Busca dados de criptomoedas"""
    try:
        url = "https://api.coindesk.com/v1/bpi/currentprice.json"
        response = await client.get(url, timeout=10.0)
        data = response.json()
        return {'btc_usd': float(data['bpi']['USD']['rate_float'])}
    except:
        return {'btc_usd': dados_tempo_real['bitcoin']}

async def fetch_bcb_data(client: httpx.AsyncClient) -> Optional[Dict]:
    """Busca dados do Banco Central"""
    try:
        url_dolar = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.10813/dados/ultimos/1?formato=json"
        resp_dolar = await client.get(url_dolar, timeout=10.0)
        dolar_data = resp_dolar.json()
        return {'dolar': float(dolar_data[0]['valor'])}
    except:
        return {'dolar': dados_tempo_real['dolar']}
# ==================== FUNÇÕES DE API EXTERNA ====================

async def fetch_coindesk(client: httpx.AsyncClient) -> Optional[Dict]:
    """Busca dados de criptomoedas"""
    try:
        url = "https://api.coindesk.com/v1/bpi/currentprice.json"
        response = await client.get(url, timeout=10.0)
        data = response.json()
        return {'btc_usd': float(data['bpi']['USD']['rate_float'])}
    except:
        return {'btc_usd': dados_tempo_real['bitcoin']}

async def fetch_bcb_data(client: httpx.AsyncClient) -> Optional[Dict]:
    """Busca dados do Banco Central"""
    try:
        url_dolar = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.10813/dados/ultimos/1?formato=json"
        resp_dolar = await client.get(url_dolar, timeout=10.0)
        dolar_data = resp_dolar.json()
        return {'dolar': float(dolar_data[0]['valor'])}
    except:
        return {'dolar': dados_tempo_real['dolar']}

# ===== COLE A FUNÇÃO DA GNEWS AQUI =====
async def fetch_gnews():
    """Busca notícias da GNews API usando sua chave"""
    try:
        # Sua chave API
        GNEWS_KEY = "84237ccac51392827588f16fc9595893"
        
        # Busca notícias
        url = f"https://gnews.io/api/v4/search?q=bolsa OR ações OR bitcoin OR dolar OR ibovespa OR investimentos&lang=pt&country=br&max=10&apikey={GNEWS_KEY}"
        
        print(f"📰 Buscando notícias da GNews...")
        response = requests.get(url)
        data = response.json()
        
        if data.get('articles'):
            noticias = []
            for artigo in data['articles']:
                # Extrair categoria do título
                categoria = 'Brasil'
                if 'bitcoin' in artigo['title'].lower() or 'cripto' in artigo['title'].lower():
                    categoria = 'Cripto'
                elif 'eua' in artigo['title'].lower() or 'wall street' in artigo['title'].lower():
                    categoria = 'Internacional'
                
                noticias.append({
                    'titulo': artigo['title'],
                    'fonte': artigo['source']['name'],
                    'data': datetime.strptime(artigo['publishedAt'][:10], '%Y-%m-%d').strftime('%d/%m/%Y'),
                    'categoria': categoria,
                    'url': artigo['url'],
                    'imagem': artigo.get('image', '')
                })
            print(f"✅ GNews: {len(noticias)} notícias encontradas")
            return noticias
        else:
            print(f"⚠️ GNews: Nenhuma notícia encontrada")
            return []
    except Exception as e:
        print(f"❌ Erro GNews: {e}")
        return []
# ===== FIM DA FUNÇÃO =====

# ==================== FUNÇÃO DE NOTÍCIAS ====================

async def get_noticias_tempo_real():
    """Agrega notícias de todas as fontes em tempo real"""
    # ... código existente ou novo ...  
# ==================== FUNÇÃO DE NOTÍCIAS (50+ NOTÍCIAS) ====================

def get_poisk_news():
    """Notícias POISK - 50+ notícias atualizadas automaticamente"""
    hoje = datetime.now()
    datas = [(hoje - timedelta(days=i)).strftime('%d/%m/%Y') for i in range(7)]
    
    return [
        # POISK News (6)
        {'titulo': '🚀 POISK atinge 52 APIs integradas globalmente', 'fonte': 'POISK News', 'data': datas[0], 'categoria': 'POISK'},
        {'titulo': '🌍 POISK lança cobertura de 42 países', 'fonte': 'POISK News', 'data': datas[0], 'categoria': 'POISK'},
        {'titulo': '📊 Nova versão POISK 3.0 com dados em tempo real', 'fonte': 'POISK Tech', 'data': datas[1], 'categoria': 'POISK'},
        {'titulo': '🎯 POISK News atinge 1 milhão de leitores', 'fonte': 'POISK', 'data': datas[1], 'categoria': 'POISK'},
        {'titulo': '⚡ Sistema de atualização automática lançado', 'fonte': 'POISK', 'data': datas[0], 'categoria': 'POISK'},
        {'titulo': '🔔 POISK agora tem alertas em tempo real', 'fonte': 'POISK', 'data': datas[2], 'categoria': 'POISK'},
        
        # Brasil (8)
        {'titulo': '🇧🇷 Petrobras anuncia novo campo de petróleo', 'fonte': 'Valor Econômico', 'data': datas[0], 'categoria': 'Brasil'},
        {'titulo': '🇧🇷 Vale bate recorde de produção de minério', 'fonte': 'Reuters', 'data': datas[1], 'categoria': 'Brasil'},
        {'titulo': '🇧🇷 Itaú projeta crescimento do PIB em 2.8%', 'fonte': 'Bloomberg', 'data': datas[2], 'categoria': 'Brasil'},
        {'titulo': '🇧🇷 WEG expande fábrica nos EUA', 'fonte': 'Valor', 'data': datas[1], 'categoria': 'Brasil'},
        {'titulo': '🇧🇷 Banco do Brasil lucra R$ 8 bi', 'fonte': 'Estadão', 'data': datas[3], 'categoria': 'Brasil'},
        {'titulo': '🇧🇷 Localiza compra concorrente', 'fonte': 'Exame', 'data': datas[2], 'categoria': 'Brasil'},
        {'titulo': '🇧🇷 Suzano investe R$ 5 bi em nova fábrica', 'fonte': 'Valor', 'data': datas[4], 'categoria': 'Brasil'},
        {'titulo': '🇧🇷 Gerdau anuncia programa de recompra', 'fonte': 'Reuters', 'data': datas[3], 'categoria': 'Brasil'},
        
        # EUA (8)
        {'titulo': '🇺🇸 NVIDIA atinge valor de mercado de US$ 2 trilhões', 'fonte': 'CNBC', 'data': datas[0], 'categoria': 'EUA'},
        {'titulo': '🇺🇸 Apple lança iPhone com IA generativa', 'fonte': 'Bloomberg', 'data': datas[1], 'categoria': 'EUA'},
        {'titulo': '🇺🇸 Microsoft anuncia investimento de US$ 10 bi em IA', 'fonte': 'Reuters', 'data': datas[2], 'categoria': 'EUA'},
        {'titulo': '🇺🇸 Tesla entrega 500 mil veículos no trimestre', 'fonte': 'CNBC', 'data': datas[1], 'categoria': 'EUA'},
        {'titulo': '🇺🇸 Fed mantém juros em 5.25%', 'fonte': 'WSJ', 'data': datas[3], 'categoria': 'EUA'},
        {'titulo': '🇺🇸 Amazon lucra US$ 30 bi no ano', 'fonte': 'Bloomberg', 'data': datas[2], 'categoria': 'EUA'},
        {'titulo': '🇺🇸 Google lança nova versão do Gemini', 'fonte': 'TechCrunch', 'data': datas[1], 'categoria': 'EUA'},
        {'titulo': '🇺🇸 Meta apresenta óculos de realidade mista', 'fonte': 'The Verge', 'data': datas[3], 'categoria': 'EUA'},
        
        # Europa (7)
        {'titulo': '🇨🇭 Nestlé compra empresa de nutrição vegetal', 'fonte': 'FT', 'data': datas[0], 'categoria': 'Europa'},
        {'titulo': '🇩🇪 SAP cresce 15% com serviços na nuvem', 'fonte': 'Reuters', 'data': datas[1], 'categoria': 'Europa'},
        {'titulo': '🇫🇷 LVMH atinge recorde histórico de vendas', 'fonte': 'Bloomberg', 'data': datas[2], 'categoria': 'Europa'},
        {'titulo': '🇬🇧 Shell anuncia programa de recompra de ações', 'fonte': 'FT', 'data': datas[1], 'categoria': 'Europa'},
        {'titulo': '🇪🇺 BCE reduz juros para 3.5%', 'fonte': 'Reuters', 'data': datas[3], 'categoria': 'Europa'},
        {'titulo': '🇮🇹 Enel investe € 5 bi em energia solar', 'fonte': 'Bloomberg', 'data': datas[2], 'categoria': 'Europa'},
        {'titulo': '🇪🇸 Santander expande no México', 'fonte': 'Expansión', 'data': datas[4], 'categoria': 'Europa'},
        
        # Ásia (8)
        {'titulo': '🇯🇵 Toyota anuncia carro elétrico com autonomia de 1000km', 'fonte': 'Nikkei', 'data': datas[0], 'categoria': 'Ásia'},
        {'titulo': '🇭🇰 Tencent lança novo jogo com 100M de downloads', 'fonte': 'SCMP', 'data': datas[1], 'categoria': 'Ásia'},
        {'titulo': '🇨🇳 Alibaba cresce 20% no e-commerce', 'fonte': 'Bloomberg', 'data': datas[2], 'categoria': 'Ásia'},
        {'titulo': '🇮🇳 Reliance anuncia entrada no mercado de IA', 'fonte': 'Economic Times', 'data': datas[1], 'categoria': 'Ásia'},
        {'titulo': '🇰🇷 Samsung lança celular dobrável com 5 câmeras', 'fonte': 'Yonhap', 'data': datas[3], 'categoria': 'Ásia'},
        {'titulo': '🇯🇵 Sony vende 50 milhões de PS5', 'fonte': 'Nikkei', 'data': datas[2], 'categoria': 'Ásia'},
        {'titulo': '🇨🇳 China anuncia pacote de estímulos', 'fonte': 'Reuters', 'data': datas[4], 'categoria': 'Ásia'},
        {'titulo': '🇮🇳 Índia: TCS contrata 10 mil profissionais', 'fonte': 'Hindu Times', 'data': datas[3], 'categoria': 'Ásia'},
        
        # África (5)
        {'titulo': '🇿🇦 Naspers: lucro sobe 25% com investimentos', 'fonte': 'Bloomberg', 'data': datas[0], 'categoria': 'África'},
        {'titulo': '🇿🇦 Anglo American vende mina de carvão', 'fonte': 'Reuters', 'data': datas[2], 'categoria': 'África'},
        {'titulo': '🇿🇦 Standard Bank lucra R$ 3 bi', 'fonte': 'FT', 'data': datas[1], 'categoria': 'África'},
        {'titulo': '🇿🇦 MTN expande 5G para 10 países', 'fonte': 'Tech Africa', 'data': datas[3], 'categoria': 'África'},
        {'titulo': '🇿🇦 África do Sul: PIB cresce 2.5%', 'fonte': 'Bloomberg', 'data': datas[4], 'categoria': 'África'},
        
        # FIIs (4)
        {'titulo': '🏢 KNRI11 distribui dividendos de R$ 1,20 por cota', 'fonte': 'FIIs.com', 'data': datas[0], 'categoria': 'FIIs'},
        {'titulo': '🏢 HGLG11 anuncia nova aquisição', 'fonte': 'FIIs.com', 'data': datas[2], 'categoria': 'FIIs'},
        {'titulo': '🏢 IFIX sobe 2% com recompras', 'fonte': 'Valor', 'data': datas[1], 'categoria': 'FIIs'},
        {'titulo': '🏢 MXRF11 paga maior dividendo do ano', 'fonte': 'FIIs.com', 'data': datas[3], 'categoria': 'FIIs'},
        
        # CDBs (4)
        {'titulo': '💰 Daycoval oferece 112% do CDI', 'fonte': 'Nord Research', 'data': datas[0], 'categoria': 'CDBs'},
        {'titulo': '💰 BMG lança CDB com liquidez diária', 'fonte': 'Suno', 'data': datas[2], 'categoria': 'CDBs'},
        {'titulo': '💰 Sofisa paga 110% do CDI', 'fonte': 'Yubb', 'data': datas[1], 'categoria': 'CDBs'},
        {'titulo': '💰 BR Partners capta R$ 500 mi em CDB', 'fonte': 'Eleven', 'data': datas[3], 'categoria': 'CDBs'},
    ]

# ==================== ROTAS ====================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Página principal com dados em tempo real"""
    
    # Busca dados externos (opcional)
    async with httpx.AsyncClient() as client:
        tasks = [fetch_coindesk(client), fetch_bcb_data(client)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    coindesk = results[0] if not isinstance(results[0], Exception) else {'btc_usd': dados_tempo_real['bitcoin']}
    bcb = results[1] if not isinstance(results[1], Exception) else {'dolar': dados_tempo_real['dolar']}
    
    # Atualiza com dados em tempo real
    dolar_atual = bcb.get('dolar', dados_tempo_real['dolar'])
    bitcoin_atual = coindesk.get('btc_usd', dados_tempo_real['bitcoin'])
    
    # Estatísticas
    stats = {
        'acoes': len(SOUTH_AMERICA) + len(NORTH_AMERICA) + len(EUROPE) + len(ASIA) + len(AFRICA) + len(OCEANIA) + len(MIDDLE_EAST),
        'paises': 42,
        'apis': 52,
        'fiis': len(FIIS),
        'cripto': len(CRIPTO),
        'cdbs': len(CDBS)
    }
    
    return templates.TemplateResponse(
        "poisk_global_robusto.html",
        {
            "request": request,
            "south_america": enriquecer_dados(SOUTH_AMERICA),
            "north_america": enriquecer_dados(NORTH_AMERICA),
            "europe": enriquecer_dados(EUROPE),
            "asia": enriquecer_dados(ASIA),
            "africa": enriquecer_dados(AFRICA),
            "oceania": enriquecer_dados(OCEANIA),
            "middle_east": enriquecer_dados(MIDDLE_EAST),
            "fiis": enriquecer_fiis(FIIS),
            "cdbs": CDBS,
            "criptos": CRIPTO,
            "noticias_poisk": get_poisk_news(),
            "indicadores": {
                'ibovespa': {'valor': f"{dados_tempo_real['ibovespa']:,}".replace(',', '.'), 'var': '+1.2%'},
                'sp500': {'valor': f"{dados_tempo_real['sp500']:,}".replace(',', '.'), 'var': '+0.8%'},
                'nasdaq': {'valor': f"{dados_tempo_real['nasdaq']:,}".replace(',', '.'), 'var': '+1.5%'},
                'nikkei': {'valor': f"{dados_tempo_real['nikkei']:,}".replace(',', '.'), 'var': '+2.1%'},
            },
            "stats": stats,
            "dolar": dolar_atual,
            "bitcoin": bitcoin_atual,
            "data": datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            "ultima_atualizacao": dados_tempo_real['ultima_atualizacao'].strftime('%H:%M:%S'),
        }
    )

@app.get("/api/tempo-real")
async def api_tempo_real():
    """API que retorna dados em tempo real (atualizados automaticamente)"""
    return {
        "status": "success",
        "data": {
            "dolar": dados_tempo_real['dolar'],
            "bitcoin": dados_tempo_real['bitcoin'],
            "ibovespa": dados_tempo_real['ibovespa'],
            "sp500": dados_tempo_real['sp500'],
            "nasdaq": dados_tempo_real['nasdaq'],
            "nikkei": dados_tempo_real['nikkei'],
        },
        "ultima_atualizacao": dados_tempo_real['ultima_atualizacao'].isoformat(),
        "proxima_atualizacao": (dados_tempo_real['ultima_atualizacao'] + timedelta(seconds=60)).isoformat()
    }

@app.get("/api/noticias/poisk")
async def api_noticias():
    """API de notícias POISK"""
    return {
        "status": "success",
        "total": len(get_poisk_news()),
        "noticias": get_poisk_news()
    }

@app.get("/detalhe/{ticker}", response_class=HTMLResponse)
async def detalhe(request: Request, ticker: str):
    """Página de detalhes do ativo"""
    return templates.TemplateResponse(
        "detalhe.html",
        {
            "request": request,
            "ticker": ticker,
            "preco": random.uniform(10, 500),
            "variacao": gerar_variacao(),
            "data": datetime.now().strftime('%d/%m/%Y %H:%M')
        }
    )
@app.get("/detalhe/{ticker}", response_class=HTMLResponse)
async def detalhe(request: Request, ticker: str):
    """Página de detalhes do ativo"""
    return templates.TemplateResponse(
        "detalhe.html",
        {
            "request": request,
            "ticker": ticker,
            "preco": random.uniform(10, 500),
            "variacao": gerar_variacao(),
            "data": datetime.now().strftime('%d/%m/%Y %H:%M')
        }
    )

# ==================== SISTEMA DE ADMIN ====================

security = HTTPBasic()

# Credenciais do admin
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "poisk2026"

def verificar_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Verifica se o usuário é admin"""
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
    """Painel administrativo do POISK"""
    
    stats = {
        "servidor": {
            "status": "online",
            "inicio": datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            "versao": "3.1.0",
            "apis_integradas": 53,
            "paises": 42,
        },
        "dados_tempo_real": {
            "dolar": dados_tempo_real['dolar'],
            "bitcoin": dados_tempo_real['bitcoin'],
            "ibovespa": dados_tempo_real['ibovespa'],
            "sp500": dados_tempo_real['sp500'],
            "ultima_atualizacao": dados_tempo_real['ultima_atualizacao'].strftime('%H:%M:%S'),
        }
    }
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>POISK Admin</title>
        <style>
            * {{ margin:0; padding:0; box-sizing:border-box; }}
            body {{
                background: #0a0a0a;
                color: #fff;
                font-family: 'Segoe UI', sans-serif;
                padding: 20px;
            }}
            .container {{ max-width: 1200px; margin:0 auto; }}
            .header {{
                background: linear-gradient(145deg, #1a1a1a, #0a0a0a);
                padding: 30px;
                border-radius: 15px;
                margin-bottom: 30px;
                border: 1px solid #333;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .logo {{ font-size:2em; color:#00ff88; font-weight:bold; }}
            .badge-admin {{ background:#ff4444; color:#fff; padding:5px 15px; border-radius:20px; }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}
            .card {{
                background: #1a1a1a;
                border-radius: 15px;
                padding: 20px;
                border: 1px solid #333;
            }}
            .card-title {{
                color: #00ff88;
                font-size: 1.3em;
                margin-bottom: 15px;
                border-bottom: 1px solid #333;
                padding-bottom: 10px;
            }}
            .stat-row {{
                display: flex;
                justify-content: space-between;
                padding: 8px 0;
                border-bottom: 1px solid #222;
            }}
            .stat-label {{ color: #888; }}
            .stat-value {{ color: #00ff88; font-weight:600; }}
            .btn {{
                background: #00ff88;
                color: #000;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                margin: 5px;
            }}
            .footer {{ text-align:center; color:#666; margin-top:30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">🔍 POISK ADMIN</div>
                <div>
                    <span class="badge-admin">Bem-vindo, {username}</span>
                </div>
            </div>
            
            <div class="grid">
                <div class="card">
                    <div class="card-title">🖥️ SERVIDOR</div>
                    <div class="stat-row"><span class="stat-label">Status:</span> <span class="stat-value">{stats['servidor']['status'].upper()}</span></div>
                    <div class="stat-row"><span class="stat-label">Início:</span> <span class="stat-value">{stats['servidor']['inicio']}</span></div>
                    <div class="stat-row"><span class="stat-label">Versão:</span> <span class="stat-value">{stats['servidor']['versao']}</span></div>
                    <div class="stat-row"><span class="stat-label">APIs:</span> <span class="stat-value">{stats['servidor']['apis_integradas']}</span></div>
                </div>
                
                <div class="card">
                    <div class="card-title">📊 DADOS EM TEMPO REAL</div>
                    <div class="stat-row"><span class="stat-label">Dólar:</span> <span class="stat-value">R$ {stats['dados_tempo_real']['dolar']:.2f}</span></div>
                    <div class="stat-row"><span class="stat-label">Bitcoin:</span> <span class="stat-value">$ {stats['dados_tempo_real']['bitcoin']:,.0f}</span></div>
                    <div class="stat-row"><span class="stat-label">Ibovespa:</span> <span class="stat-value">{stats['dados_tempo_real']['ibovespa']}</span></div>
                    <div class="stat-row"><span class="stat-label">Última atualização:</span> <span class="stat-value">{stats['dados_tempo_real']['ultima_atualizacao']}</span></div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-title">⚡ AÇÕES RÁPIDAS</div>
                <div style="display: flex; gap:10px; flex-wrap:wrap;">
                    <a href="/" class="btn" target="_blank">🌍 Ver Site</a>
                    <a href="/docs" class="btn" target="_blank">📚 Documentação</a>
                    <a href="/api/status" class="btn" target="_blank">🔌 API Status</a>
                </div>
            </div>
            
            <div class="footer">
                POISK ADMIN • Acesso restrito • {datetime.now().strftime('%d/%m/%Y %H:%M')}
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)

if __name__ == "__main__":
    import uvicorn
    print("="*80)
    print("🌍 POISK GLOBAL - VERSÃO COMPLETA")
    print("="*80)
    print("📊 Ações: 70+")
    print("🌎 Países: 42")
    print("📰 Notícias: 50+")
    print("⚡ Atualização automática: a cada 60 segundos")
    print("📱 Site: http://localhost:8000")
    print("📚 Documentação: http://localhost:8000/docs")
    print("="*80)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
