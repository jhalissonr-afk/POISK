# app/algorithms/poisk_score.py

class AlgoritmoPOISK:
    """
    Algoritmo proprietário do POISK - Versão 1.0
    """
    
    def __init__(self):
        self.nome = "POISK Score v1.0"
        self.criador = "POISK Labs"
        
        # Pesos definidos por você (sua assinatura!)
        self.pesos = {
            "valorizacao": 0.30,      # 30% - Variação recente
            "volume": 0.20,             # 20% - Liquidez
            "rsi": 0.20,                # 20% - Momento
            "fundamentos": 0.30         # 30% - Dividendos, etc
        }
        
        # Fator secreto do POISK (só você sabe)
        self.FATOR_POISK = 1.382  # Número mágico!
    
    def calcular_score(self, acao):
        """
        Calcula o score da ação baseado em múltiplos fatores
        """
        score = 0
        criterios = []
        
        # 1. ANÁLISE DE VALORIZAÇÃO
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
        else:
            criterios.append("📊 Estabilidade")
        
        # 2. ANÁLISE DE VOLUME
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
        
        # 3. ANÁLISE DE RSI (se disponível)
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
        
        # 4. ANÁLISE DE FUNDAMENTOS
        dy = acao.get('dy_percent', 0)
        if dy > 8:
            score += 30 * self.pesos["fundamentos"]
            criterios.append(f"💰 Dividend Yield excepcional: {dy}%")
        elif dy > 5:
            score += 20 * self.pesos["fundamentos"]
            criterios.append(f"💰 Bom Dividend Yield: {dy}%")
        elif dy > 2:
            score += 10 * self.pesos["fundamentos"]
            criterios.append(f"💰 Dividend Yield positivo: {dy}%")
        
        # 5. APLICAR FATOR POISK (SEU SEGREDO!)
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
            "criterios": criterios[:4],  # Mostra só os principais
            "algoritmo": self.nome
        }
