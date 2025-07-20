# ==================== src/upstox_client.py (FIXED) ====================
import requests
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import asyncio
import aiohttp
from pathlib import Path

class UpstoxClient:
    """Upstox API client with token persistence"""
    
    def __init__(self, api_key: str, api_secret: str, redirect_uri: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.redirect_uri = redirect_uri
        self.access_token = None
        self.base_url = "https://api.upstox.com/v2"
        self.logger = logging.getLogger(__name__)
        
        # Token storage
        self.token_file = Path("data") / "access_token.json"
        self.load_stored_token()
        
    def save_token(self, token_data: dict):
        """Save access token to file"""
        try:
            # Create data directory if it doesn't exist
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Add timestamp
            token_data['saved_at'] = datetime.now().isoformat()
            
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
                
            self.logger.info("Access token saved successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to save token: {e}")
    
    def load_stored_token(self):
        """Load stored access token"""
        try:
            if self.token_file.exists():
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                    
                self.access_token = token_data.get('access_token')
                
                if self.access_token:
                    saved_at = token_data.get('saved_at')
                    self.logger.info(f"Loaded stored access token from {saved_at}")
                    return True
                    
        except Exception as e:
            self.logger.error(f"Failed to load stored token: {e}")
            
        return False
    
    def get_login_url(self) -> str:
        """Generate login URL for authorization"""
        auth_url = "https://api.upstox.com/v2/login/authorization/dialog"
        params = {
            'response_type': 'code',
            'client_id': self.api_key,
            'redirect_uri': self.redirect_uri
        }
        
        url = f"{auth_url}?response_type={params['response_type']}&client_id={params['client_id']}&redirect_uri={params['redirect_uri']}"
        return url
    
    async def get_access_token(self, auth_code: str) -> bool:
        """Get access token using authorization code"""
        url = f"{self.base_url}/login/authorization/token"
        
        data = {
            'code': auth_code,
            'client_id': self.api_key,
            'client_secret': self.api_secret,
            'redirect_uri': self.redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as response:
                    response.raise_for_status()
                    token_response = await response.json()
                    
                    # Handle both response formats
                    if isinstance(token_response, dict):
                        # Direct response format (what you're getting)
                        if 'access_token' in token_response:
                            self.access_token = token_response.get('access_token')
                            
                            if self.access_token:
                                # Save token for future use
                                self.save_token(token_response)
                                self.logger.info("Access token obtained and saved successfully")
                                return True
                        
                        # Wrapped response format
                        elif token_response.get('status') == 'success':
                            token_data = token_response.get('data', {})
                            self.access_token = token_data.get('access_token')
                            
                            if self.access_token:
                                # Save token for future use
                                self.save_token(token_data)
                                self.logger.info("Access token obtained and saved successfully")
                                return True
                    
                    self.logger.error(f"Token request failed: {token_response}")
                    return False
                        
        except Exception as e:
            self.logger.error(f"Error getting access token: {e}")
            return False
    
    async def test_token(self) -> bool:
        """Test if current access token is valid"""
        try:
            profile = await self.get_profile()
            # FIX: Check for successful response properly
            if profile and isinstance(profile, dict):
                return profile.get('status') == 'success'
            return False
        except Exception as e:
            self.logger.debug(f"Token test failed: {e}")
            return False
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:  # FIX: Optional[Dict] instead of Dict = None
        """Make authenticated API request"""
        if not self.access_token:
            self.logger.error("No access token available")
            return None
            
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                if method.upper() == 'GET':
                    async with session.get(url, headers=headers) as response:
                        response.raise_for_status()
                        return await response.json()
                        
                elif method.upper() == 'POST':
                    async with session.post(url, headers=headers, json=data) as response:
                        response.raise_for_status()
                        return await response.json()
                        
                elif method.upper() == 'PUT':
                    async with session.put(url, headers=headers, json=data) as response:
                        response.raise_for_status()
                        return await response.json()
                        
                elif method.upper() == 'DELETE':
                    async with session.delete(url, headers=headers) as response:
                        response.raise_for_status()
                        return await response.json()
            
        except Exception as e:
            self.logger.error(f"API request failed: {e}")
            return None
    
    async def get_profile(self) -> Optional[Dict]:
        """Get user profile information"""
        return await self._make_request('GET', '/user/profile')
    
    async def get_funds(self) -> Optional[Dict]:
        """Get account funds information"""
        return await self._make_request('GET', '/user/funds')
    
    async def get_positions(self) -> Optional[Dict]:
        """Get current positions"""
        return await self._make_request('GET', '/portfolio/long-term-positions')
    
    async def search_instruments(self, query: str) -> Optional[Dict]:
        """Search for trading instruments"""
        endpoint = f"/search/instruments?query={query}"
        return await self._make_request('GET', endpoint)
    
    async def get_market_data(self, instrument_key: str) -> Optional[Dict]:
        """Get market data for an instrument"""
        endpoint = f"/market-quote/quotes?instrument_key={instrument_key}"
        return await self._make_request('GET', endpoint)
    
    async def place_order(self, order_data: Dict) -> Optional[Dict]:
        """Place a trading order"""
        return await self._make_request('POST', '/order/place', order_data)
    
    async def get_order_history(self) -> Optional[Dict]:
        """Get order history"""
        return await self._make_request('GET', '/order/retrieve-all')