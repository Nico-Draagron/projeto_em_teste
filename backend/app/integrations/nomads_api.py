# API NOMADS (dados climáticos)
# ===========================
# backend/app/integrations/nomads_api.py
# ===========================
"""
NOMADS (NOAA) Weather Data API Integration
National Oceanic and Atmospheric Administration
"""

import httpx
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
from io import StringIO
import pandas as pd
import numpy as np

from app.core.config import settings
from app.core.exceptions import WeatherAPIError

logger = logging.getLogger(__name__)


class NOMADSClient:
    """
    Client for NOMADS weather data API
    https://nomads.ncep.noaa.gov/
    """
    
    BASE_URL = "https://nomads.ncep.noaa.gov"
    GFS_URL = f"{BASE_URL}/cgi-bin/filter_gfs_0p25.pl"
    NAM_URL = f"{BASE_URL}/cgi-bin/filter_nam.pl"
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def get_gfs_forecast(
        self,
        lat: float,
        lon: float,
        hours_ahead: int = 168,  # 7 days
        variables: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get GFS (Global Forecast System) weather forecast
        Resolution: 0.25 degrees (~25km)
        """
        try:
            # Default variables if not specified
            if not variables:
                variables = [
                    "TMP",     # Temperature
                    "RH",      # Relative Humidity
                    "UGRD",    # U-component of wind
                    "VGRD",    # V-component of wind
                    "PRATE",   # Precipitation rate
                    "TCDC",    # Total cloud cover
                    "PRES",    # Pressure
                ]
            
            # Get latest run
            run_date = datetime.utcnow().replace(hour=(datetime.utcnow().hour // 6) * 6)
            run_str = run_date.strftime("%Y%m%d")
            run_hour = f"{run_date.hour:02d}"
            
            forecast_data = []
            
            # Fetch data for each forecast hour
            for hour in range(0, min(hours_ahead, 384), 3):  # GFS goes to 384 hours
                params = {
                    "file": f"gfs.t{run_hour}z.pgrb2.0p25.f{hour:03d}",
                    "lev_surface": "on",
                    "lev_2_m_above_ground": "on",
                    "lev_10_m_above_ground": "on",
                    "var_TMP": "on" if "TMP" in variables else "off",
                    "var_RH": "on" if "RH" in variables else "off",
                    "var_UGRD": "on" if "UGRD" in variables else "off",
                    "var_VGRD": "on" if "VGRD" in variables else "off",
                    "var_PRATE": "on" if "PRATE" in variables else "off",
                    "var_TCDC": "on" if "TCDC" in variables else "off",
                    "var_PRES": "on" if "PRES" in variables else "off",
                    "subregion": "",
                    "leftlon": lon - 0.5,
                    "rightlon": lon + 0.5,
                    "toplat": lat + 0.5,
                    "bottomlat": lat - 0.5,
                    "dir": f"/gfs.{run_str}/{run_hour}/atmos"
                }
                
                response = await self.client.get(self.GFS_URL, params=params)
                
                if response.status_code == 200:
                    # Parse GRIB2 data (simplified - real implementation would use pygrib)
                    data = self._parse_grib_data(response.content)
                    
                    forecast_time = run_date + timedelta(hours=hour)
                    
                    forecast_data.append({
                        "datetime": forecast_time.isoformat(),
                        "temperature": data.get("TMP", {}).get("value"),
                        "humidity": data.get("RH", {}).get("value"),
                        "wind_u": data.get("UGRD", {}).get("value"),
                        "wind_v": data.get("VGRD", {}).get("value"),
                        "precipitation_rate": data.get("PRATE", {}).get("value"),
                        "cloud_cover": data.get("TCDC", {}).get("value"),
                        "pressure": data.get("PRES", {}).get("value"),
                        "source": "NOMADS_GFS"
                    })
            
            return forecast_data
            
        except Exception as e:
            logger.error(f"Error fetching NOMADS GFS data: {str(e)}")
            raise WeatherAPIError(f"Failed to fetch NOMADS data: {str(e)}")
    
    async def get_historical_data(
        self,
        lat: float,
        lon: float,
        start_date: datetime,
        end_date: datetime,
        dataset: str = "ERA5"
    ) -> List[Dict[str, Any]]:
        """
        Get historical weather data from reanalysis datasets
        """
        try:
            # NOMADS provides access to various reanalysis datasets
            # ERA5, CFSR, MERRA-2, etc.
            
            historical_data = []
            
            # This would connect to the appropriate dataset
            # For now, return mock data structure
            current_date = start_date
            while current_date <= end_date:
                # In production, fetch actual data from NOMADS archives
                historical_data.append({
                    "date": current_date.date().isoformat(),
                    "temperature_mean": 25.0 + np.random.normal(0, 5),
                    "temperature_min": 20.0 + np.random.normal(0, 3),
                    "temperature_max": 30.0 + np.random.normal(0, 3),
                    "humidity": 70.0 + np.random.normal(0, 10),
                    "precipitation": max(0, np.random.exponential(5)),
                    "wind_speed": 10.0 + np.random.normal(0, 3),
                    "pressure": 1013.0 + np.random.normal(0, 5),
                    "source": f"NOMADS_{dataset}"
                })
                current_date += timedelta(days=1)
            
            return historical_data
            
        except Exception as e:
            logger.error(f"Error fetching historical data: {str(e)}")
            raise WeatherAPIError(f"Failed to fetch historical data: {str(e)}")
    
    def _parse_grib_data(self, grib_content: bytes) -> Dict[str, Any]:
        """
        Parse GRIB2 data (simplified version)
        In production, use pygrib or cfgrib
        """
        # This is a placeholder - actual implementation would parse GRIB2
        return {
            "TMP": {"value": 25.0, "unit": "K"},
            "RH": {"value": 70.0, "unit": "%"},
            "UGRD": {"value": 5.0, "unit": "m/s"},
            "VGRD": {"value": 3.0, "unit": "m/s"},
            "PRATE": {"value": 0.0, "unit": "kg/m^2/s"},
            "TCDC": {"value": 50.0, "unit": "%"},
            "PRES": {"value": 101300.0, "unit": "Pa"}
        }
    
    async def get_ensemble_forecast(
        self,
        lat: float,
        lon: float,
        hours_ahead: int = 168
    ) -> Dict[str, Any]:
        """
        Get ensemble forecast for uncertainty quantification
        """
        # GEFS (Global Ensemble Forecast System) provides 31 members
        # This gives probability distributions for weather variables
        
        try:
            ensemble_data = {
                "location": {"lat": lat, "lon": lon},
                "forecast_hours": hours_ahead,
                "members": 31,
                "variables": {}
            }
            
            # Fetch ensemble data (simplified)
            for var in ["temperature", "precipitation", "wind_speed"]:
                ensemble_data["variables"][var] = {
                    "mean": [],
                    "std": [],
                    "percentiles": {"10": [], "25": [], "50": [], "75": [], "90": []}
                }
            
            return ensemble_data
            
        except Exception as e:
            logger.error(f"Error fetching ensemble data: {str(e)}")
            raise WeatherAPIError(f"Failed to fetch ensemble data: {str(e)}")
