# Outras APIs de dados
# ===========================
# backend/app/integrations/external_data.py
# ===========================
"""
External data sources integration
Generic interface for various APIs
"""

import httpx
from typing import Dict, Any, Optional, List
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ExternalDataSource(ABC):
    """
    Abstract base class for external data sources
    """
    
    @abstractmethod
    async def fetch_data(self, **kwargs) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def validate_connection(self) -> bool:
        pass


class SalesforceClient(ExternalDataSource):
    """
    Salesforce CRM integration
    """
    
    def __init__(self, instance_url: str, access_token: str):
        self.instance_url = instance_url
        self.access_token = access_token
        self.client = httpx.AsyncClient()
    
    async def fetch_data(
        self,
        object_type: str = "Opportunity",
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch data from Salesforce
        """
        if not query:
            query = f"SELECT Id, Name, Amount, CloseDate FROM {object_type}"
        
        response = await self.client.get(
            f"{self.instance_url}/services/data/v55.0/query",
            params={"q": query},
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        
        if response.status_code == 200:
            return response.json()
        
        raise Exception(f"Salesforce API error: {response.status_code}")
    
    async def validate_connection(self) -> bool:
        """
        Validate Salesforce connection
        """
        try:
            response = await self.client.get(
                f"{self.instance_url}/services/data",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            return response.status_code == 200
        except:
            return False


class ShopifyClient(ExternalDataSource):
    """
    Shopify e-commerce integration
    """
    
    def __init__(self, shop_url: str, api_key: str, api_secret: str):
        self.shop_url = shop_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = httpx.AsyncClient()
    
    async def fetch_data(
        self,
        resource: str = "orders",
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Fetch data from Shopify
        """
        url = f"https://{self.shop_url}/admin/api/2023-10/{resource}.json"
        
        response = await self.client.get(
            url,
            params=params or {},
            auth=(self.api_key, self.api_secret)
        )
        
        if response.status_code == 200:
            return response.json()
        
        raise Exception(f"Shopify API error: {response.status_code}")
    
    async def fetch_sales_data(
        self,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch sales data from Shopify
        """
        params = {
            "created_at_min": start_date,
            "created_at_max": end_date,
            "status": "any",
            "limit": 250
        }
        
        data = await self.fetch_data("orders", params)
        return data.get("orders", [])
    
    async def validate_connection(self) -> bool:
        """
        Validate Shopify connection
        """
        try:
            response = await self.client.get(
                f"https://{self.shop_url}/admin/api/2023-10/shop.json",
                auth=(self.api_key, self.api_secret)
            )
            return response.status_code == 200
        except:
            return False


class ExternalDataService:
    """
    Service to manage multiple external data sources
    """
    
    def __init__(self):
        self.sources: Dict[str, ExternalDataSource] = {}
    
    def register_source(self, name: str, source: ExternalDataSource):
        """
        Register new data source
        """
        self.sources[name] = source
    
    async def fetch_from_source(
        self,
        source_name: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch data from specific source
        """
        if source_name not in self.sources:
            raise ValueError(f"Unknown data source: {source_name}")
        
        source = self.sources[source_name]
        return await source.fetch_data(**kwargs)
    
    async def validate_all_connections(self) -> Dict[str, bool]:
        """
        Validate all registered connections
        """
        results = {}
        for name, source in self.sources.items():
            try:
                results[name] = await source.validate_connection()
            except Exception as e:
                logger.error(f"Error validating {name}: {str(e)}")
                results[name] = False
        
        return results