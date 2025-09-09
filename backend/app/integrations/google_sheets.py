# ===========================
# backend/app/integrations/google_sheets.py
# ===========================
"""
Google Sheets Integration
For data import/export
"""

import httpx
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import pandas as pd

from app.core.config import settings

logger = logging.getLogger(__name__)


class GoogleSheetsClient:
    """
    Client for Google Sheets API
    """
    
    SHEETS_API_URL = "https://sheets.googleapis.com/v4/spreadsheets"
    
    def __init__(self, credentials: Optional[Dict] = None):
        self.credentials = credentials
        self.client = httpx.AsyncClient(timeout=30.0)
        # In production, implement OAuth2 flow
        self.access_token = None
    
    async def read_sheet(
        self,
        spreadsheet_id: str,
        range_name: str = "Sheet1!A:Z"
    ) -> pd.DataFrame:
        """
        Read data from Google Sheets
        """
        try:
            # This would use proper OAuth2 in production
            response = await self.client.get(
                f"{self.SHEETS_API_URL}/{spreadsheet_id}/values/{range_name}",
                params={"key": settings.GOOGLE_API_KEY}  # or use OAuth token
            )
            
            if response.status_code != 200:
                raise Exception(f"Google Sheets API error: {response.status_code}")
            
            data = response.json()
            values = data.get("values", [])
            
            if not values:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(values[1:], columns=values[0])
            return df
            
        except Exception as e:
            logger.error(f"Error reading Google Sheets: {str(e)}")
            raise
    
    async def write_sheet(
        self,
        spreadsheet_id: str,
        range_name: str,
        data: pd.DataFrame
    ) -> bool:
        """
        Write data to Google Sheets
        """
        try:
            # Convert DataFrame to values array
            values = [data.columns.tolist()] + data.values.tolist()
            
            response = await self.client.put(
                f"{self.SHEETS_API_URL}/{spreadsheet_id}/values/{range_name}",
                params={"valueInputOption": "USER_ENTERED"},
                json={"values": values},
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error writing to Google Sheets: {str(e)}")
            return False
    
    async def create_spreadsheet(
        self,
        title: str,
        sheets: List[str] = None
    ) -> str:
        """
        Create new spreadsheet
        """
        try:
            body = {
                "properties": {"title": title},
                "sheets": [
                    {"properties": {"title": sheet}}
                    for sheet in (sheets or ["Sheet1"])
                ]
            }
            
            response = await self.client.post(
                self.SHEETS_API_URL,
                json=body,
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            
            if response.status_code == 200:
                return response.json()["spreadsheetId"]
            
            raise Exception(f"Failed to create spreadsheet: {response.status_code}")
            
        except Exception as e:
            logger.error(f"Error creating spreadsheet: {str(e)}")
            raise
