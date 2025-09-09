# GET/POST /sales, /analysis
# backend/app/api/v1/endpoints/sales.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from datetime import datetime, date, timedelta

from app.api import deps
from app.models.database import User, Company, SalesData, Product
from app.models.schemas import (
    SalesDataCreate,
    SalesDataUpdate,
    SalesDataResponse,
    SalesMetrics,
    SalesAnalysis,
    PaginatedResponse,
    AnomalyDetection
)
from app.services.sales_service import SalesService
from app.core.exceptions import DataNotFoundError, AnalysisError

router = APIRouter()


@router.post("/", response_model=SalesDataResponse, status_code=status.HTTP_201_CREATED)
async def create_sales_data(
    sales_data: SalesDataCreate,
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Create new sales data entry
    """
    # Check for duplicate
    existing = db.query(SalesData).filter(
        SalesData.company_id == company.id,
        SalesData.date == sales_data.date,
        SalesData.location_id == sales_data.location_id,
        SalesData.product_id == sales_data.product_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sales data for this date/location/product already exists"
        )
    
    # Create sales data
    db_sales = SalesData(
        company_id=company.id,
        **sales_data.dict()
    )
    
    db.add(db_sales)
    db.commit()
    db.refresh(db_sales)
    
    return db_sales


@router.get("/", response_model=PaginatedResponse)
async def list_sales_data(
    start_date: Optional[date] = Query(None, description="Start date for filtering"),
    end_date: Optional[date] = Query(None, description="End date for filtering"),
    location_id: Optional[str] = Query(None, description="Filter by location"),
    product_id: Optional[str] = Query(None, description="Filter by product"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    List sales data with filters
    """
    query = db.query(SalesData).filter(SalesData.company_id == company.id)
    
    # Apply filters
    if start_date:
        query = query.filter(SalesData.date >= start_date)
    if end_date:
        query = query.filter(SalesData.date <= end_date)
    if location_id:
        query = query.filter(SalesData.location_id == location_id)
    if product_id:
        query = query.filter(SalesData.product_id == product_id)
    
    # Get total count
    total = query.count()
    
    # Get paginated items
    items = query.order_by(SalesData.date.desc()).offset(skip).limit(limit).all()
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": total > skip + limit
    }


@router.get("/metrics", response_model=SalesMetrics)
async def get_sales_metrics(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    location_id: Optional[str] = Query(None),
    product_id: Optional[str] = Query(None),
    aggregation: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get aggregated sales metrics
    """
    service = SalesService(db, company.id)
    
    try:
        metrics = await service.get_sales_metrics(
            start_date=datetime.combine(start_date, datetime.min.time()),
            end_date=datetime.combine(end_date, datetime.max.time()),
            location_id=location_id,
            product_id=product_id,
            aggregation=aggregation
        )
        return metrics
    except DataNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AnalysisError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/analysis", response_model=SalesAnalysis)
async def analyze_sales(
    start_date: date = Query(...),
    end_date: date = Query(...),
    include_patterns: bool = Query(True),
    include_anomalies: bool = Query(True),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Comprehensive sales analysis
    """
    service = SalesService(db, company.id)
    
    # Get metrics
    metrics = await service.get_sales_metrics(
        start_date=datetime.combine(start_date, datetime.min.time()),
        end_date=datetime.combine(end_date, datetime.max.time())
    )
    
    analysis = {"metrics": metrics}
    
    # Get patterns if requested
    if include_patterns:
        patterns = await service.calculate_patterns()
        analysis["patterns"] = patterns
    
    # Detect anomalies if requested
    if include_anomalies:
        anomalies = await service.detect_anomalies(
            lookback_days=(end_date - start_date).days
        )
        analysis["anomalies"] = anomalies
    
    return analysis


@router.get("/timeseries")
async def get_sales_timeseries(
    start_date: date = Query(...),
    end_date: date = Query(...),
    granularity: str = Query("daily", regex="^(hourly|daily|weekly|monthly)$"),
    location_id: Optional[str] = None,
    product_id: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get sales time series data for charts
    """
    query = db.query(SalesData).filter(
        SalesData.company_id == company.id,
        SalesData.date >= start_date,
        SalesData.date <= end_date
    )
    
    if location_id:
        query = query.filter(SalesData.location_id == location_id)
    if product_id:
        query = query.filter(SalesData.product_id == product_id)
    
    sales_data = query.order_by(SalesData.date).all()
    
    # Format for charts
    timeseries = []
    for sale in sales_data:
        timeseries.append({
            "date": sale.date.isoformat(),
            "revenue": float(sale.revenue),
            "quantity": sale.quantity,
            "transactions": sale.transaction_count or 0
        })
    
    return {
        "data": timeseries,
        "granularity": granularity,
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        }
    }


@router.get("/anomalies", response_model=List[AnomalyDetection])
async def detect_sales_anomalies(
    lookback_days: int = Query(30, ge=7, le=90),
    sensitivity: float = Query(2.0, ge=1.0, le=3.0),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Detect anomalies in recent sales data
    """
    service = SalesService(db, company.id)
    
    try:
        anomalies = await service.detect_anomalies(
            lookback_days=lookback_days,
            sensitivity=sensitivity
        )
        return anomalies
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error detecting anomalies: {str(e)}"
        )


@router.put("/{sales_id}", response_model=SalesDataResponse)
async def update_sales_data(
    sales_id: str,
    sales_update: SalesDataUpdate,
    current_user: User = Depends(deps.require_role("manager")),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Update sales data entry
    """
    sales_data = db.query(SalesData).filter(
        SalesData.id == sales_id,
        SalesData.company_id == company.id
    ).first()
    
    if not sales_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sales data not found"
        )
    
    # Update fields
    update_data = sales_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sales_data, field, value)
    
    sales_data.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(sales_data)
    
    return sales_data


@router.delete("/{sales_id}")
async def delete_sales_data(
    sales_id: str,
    current_user: User = Depends(deps.require_role("admin")),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Delete sales data entry
    """
    sales_data = db.query(SalesData).filter(
        SalesData.id == sales_id,
        SalesData.company_id == company.id
    ).first()
    
    if not sales_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sales data not found"
        )
    
    db.delete(sales_data)
    db.commit()
    
    return {"message": "Sales data deleted successfully"}


@router.post("/import")
async def import_sales_data(
    file_id: str,
    date_column: str = "date",
    revenue_column: str = "revenue",
    quantity_column: str = "quantity",
    current_user: User = Depends(deps.require_role("manager")),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Import sales data from uploaded file
    """
    # Implementation for CSV/Excel import
    # This would process the uploaded file and create multiple sales entries
    
    return {
        "message": "Import started",
        "job_id": "import_job_id",
        "status": "processing"
    }

