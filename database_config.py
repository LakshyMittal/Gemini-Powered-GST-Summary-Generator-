# database_config.py
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from pymongo import MongoClient


class DatabaseConfig:
    CENTRAL_KYC_MONGO_DB_URL = os.getenv(
        "CENTRAL_KYC_MONGO_URI", "mongodb://localhost:27017/"
    )


class NetworkConnections:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NetworkConnections, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.central_kyc_database = None

        try:
            # MongoDB Connections
            self.mongo_client = MongoClient(DatabaseConfig.CENTRAL_KYC_MONGO_DB_URL)
            self.central_kyc_database = self.mongo_client["centralKyc"]

        except Exception as e:
            print(f"Error establishing database connections: {e}")
            raise

        self._initialized = True

    def get_mongo_db(self):
        return self.central_kyc_database


class BalanceSheetData(BaseModel):
    companyGst: str
    fiscalYearEnd: int
    data: Optional[Dict[str, Any]] = None
    createdAt: Optional[datetime] = Field(default_factory=datetime.now)
    updatedAt: Optional[datetime] = Field(default_factory=datetime.now)


class LosApplicationTracker(BaseModel):
    identifier: str
    customerId: Optional[str] = None
    stage: Optional[str] = None
    source: Optional[str] = None
    isActive: Optional[bool] = True
    productName: Optional[str] = None
    kycApplicationId: Optional[str] = None
    metaData: Optional[Dict[str, Any]] = None
    currentlyAssignedTo: Optional[Dict[str, Any]] = None  # Simplified LOSTeam
    assignmentHistory: Optional[List[Dict[str, Any]]] = None  # Simplified LOSTeam list
    drawDownParentId: Optional[str] = None
    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updatedAt: Optional[datetime] = Field(default_factory=datetime.utcnow)


class ProfitAndLossSheetData(BaseModel):
    companyGst: str
    fiscalYearEnd: int
    data: Optional[Dict[str, Any]] = (
        None  # Assuming 'data' can be any JSON-like structure
    )
    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updatedAt: Optional[datetime] = Field(default_factory=datetime.utcnow)
