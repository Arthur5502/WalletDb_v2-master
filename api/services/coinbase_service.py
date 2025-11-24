from decimal import Decimal
import httpx

class CoinbaseService:
    BASE_URL = "https://api.coinbase.com/v2/prices"
    
    @staticmethod
    async def obter_cotacao(moeda_origem: str, moeda_destino: str) -> Decimal:
        url = f"{CoinbaseService.BASE_URL}/{moeda_origem}-{moeda_destino}/spot"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
                response.raise_for_status()
                
                data = response.json()
                
                if "data" in data and "amount" in data["data"]:
                    cotacao = Decimal(data["data"]["amount"])
                    return cotacao
                else:
                    raise ValueError(f"Resposta inesperada da API: {data}")
                    
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Erro ao obter cotação {moeda_origem}-{moeda_destino}: {e.response.status_code}")
        except httpx.RequestError as e:
            raise ValueError(f"Erro de conexão com API Coinbase: {str(e)}")
        except (KeyError, ValueError) as e:
            raise ValueError(f"Erro ao processar resposta da API: {str(e)}")
