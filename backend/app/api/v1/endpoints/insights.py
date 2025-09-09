# GET /insights, /correlations
# ===========================
# backend/app/api/v1/endpoints/insights.py
# ===========================

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from datetime import datetime, date, timedelta

from app.api import deps
from app.models.database import User, Company
from app.models.schemas import (
    CorrelationAnalysis,
    ImpactAnalysis,
    AIInsight,
    PredictionRequest,
    PredictionResponse,
    ScenarioSimulation,
    SimulationResponse
)
from app.services.sales_service import SalesService
from app.services.ml_service import MLService
from app.services.ai_agent_service import AIAgentService

router = APIRouter()


@router.get("/correlations", response_model=CorrelationAnalysis)
async def analyze_correlations(
    start_date: date = Query(...),
    end_date: date = Query(...),
    variables: Optional[List[str]] = Query(None),
    min_significance: float = Query(0.05, ge=0, le=1),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Analyze correlations between weather variables and sales
    """
    sales_service = SalesService(db, company.id)
    
    try:
        impact_analysis = await sales_service.analyze_weather_impact(
            start_date=datetime.combine(start_date, datetime.min.time()),
            end_date=datetime.combine(end_date, datetime.max.time()),
            weather_variables=variables,
            lag_days=0
        )
        
        # Format response
        correlation_matrix = {}
        significant_correlations = []
        
        for var, corr_data in impact_analysis["correlations"].items():
            correlation_matrix[var] = {
                "sales": corr_data["correlation"],
                "p_value": corr_data["p_value"],
                "significant": corr_data["significant"]
            }
            
            if corr_data["p_value"] <= min_significance:
                significant_correlations.append({
                    "variable": var,
                    "correlation": corr_data["correlation"],
                    "p_value": corr_data["p_value"],
                    "strength": corr_data["strength"]
                })
        
        return {
            "variables": list(correlation_matrix.keys()),
            "correlation_matrix": {"sales": correlation_matrix},
            "significant_correlations": significant_correlations,
            "recommendations": impact_analysis["recommendations"],
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing correlations: {str(e)}"
        )


@router.get("/impact/{weather_variable}", response_model=ImpactAnalysis)
async def analyze_weather_impact(
    weather_variable: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    lag_days: int = Query(0, ge=0, le=7),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Analyze impact of specific weather variable on sales
    """
    sales_service = SalesService(db, company.id)
    
    try:
        impact = await sales_service.analyze_weather_impact(
            start_date=datetime.combine(start_date, datetime.min.time()),
            end_date=datetime.combine(end_date, datetime.max.time()),
            weather_variables=[weather_variable],
            lag_days=lag_days
        )
        
        var_impact = impact["impacts"][weather_variable]
        var_correlation = impact["correlations"][weather_variable]
        
        return {
            "weather_variable": weather_variable,
            "impact_coefficient": var_impact["coefficient"],
            "confidence_interval": (
                var_impact["coefficient"] - 0.1 * abs(var_impact["coefficient"]),
                var_impact["coefficient"] + 0.1 * abs(var_impact["coefficient"])
            ),
            "r_squared": var_impact["r_squared"],
            "interpretation": var_impact["interpretation"],
            "recommendations": impact["recommendations"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing impact: {str(e)}"
        )


@router.post("/predictions", response_model=PredictionResponse)
async def generate_predictions(
    request: PredictionRequest,
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Generate sales predictions
    """
    ml_service = MLService(db, company.id)
    
    try:
        predictions = await ml_service.predict_sales(
            start_date=datetime.combine(request.start_date, datetime.min.time()),
            end_date=datetime.combine(request.end_date, datetime.max.time()),
            weather_forecast=request.weather_scenario,
            product_id=request.product_id,
            confidence_level=0.95 if request.include_confidence else None
        )
        
        return predictions
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating predictions: {str(e)}"
        )


@router.post("/simulate", response_model=SimulationResponse)
async def simulate_scenario(
    simulation: ScenarioSimulation,
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Simulate weather scenario and predict impact
    """
    ai_service = AIAgentService(db, company.id, current_user.id)
    
    try:
        result = await ai_service.simulate_scenario(
            scenario={
                "weather_conditions": simulation.weather_conditions,
                "impact_type": simulation.impact_type
            },
            target_date=datetime.combine(
                simulation.target_date or date.today() + timedelta(days=1),
                datetime.min.time()
            )
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error simulating scenario: {str(e)}"
        )


@router.get("/ai-insights", response_model=List[AIInsight])
async def get_ai_insights(
    data_type: str = Query("all", regex="^(all|sales|weather|correlations)$"),
    lookback_days: int = Query(30, ge=7, le=90),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get AI-generated insights
    """
    ai_service = AIAgentService(db, company.id, current_user.id)
    
    try:
        insights = await ai_service.generate_insights(
            data_type=data_type,
            lookback_days=lookback_days
        )
        
        # Return top insights
        return insights[:limit]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating insights: {str(e)}"
        )


@router.get("/patterns")
async def analyze_patterns(
    pattern_type: str = Query("all", regex="^(weekly|monthly|seasonal|all)$"),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Identify patterns in sales data
    """
    sales_service = SalesService(db, company.id)
    
    try:
        patterns = await sales_service.calculate_patterns(pattern_type=pattern_type)
        return patterns
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing patterns: {str(e)}"
        )


@router.get("/kpis")
async def get_key_performance_indicators(
    period: str = Query("today", regex="^(today|week|month|year)$"),
    compare_to_previous: bool = Query(True),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get key performance indicators
    """
    # Calculate period dates
    end_date = datetime.utcnow()
    if period == "today":
        start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        prev_start = start_date - timedelta(days=1)
        prev_end = end_date - timedelta(days=1)
    elif period == "week":
        start_date = end_date - timedelta(days=7)
        prev_start = start_date - timedelta(days=7)
        prev_end = end_date - timedelta(days=7)
    elif period == "month":
        start_date = end_date - timedelta(days=30)
        prev_start = start_date - timedelta(days=30)
        prev_end = end_date - timedelta(days=30)
    else:  # year
        start_date = end_date - timedelta(days=365)
        prev_start = start_date - timedelta(days=365)
        prev_end = end_date - timedelta(days=365)
    
    sales_service = SalesService(db, company.id)
    
    # Get current period metrics
    current_metrics = await sales_service.get_sales_metrics(
        start_date=start_date,
        end_date=end_date
    )
    
    kpis = {
        "period": period,
        "total_revenue": current_metrics.total_revenue,
        "average_daily_revenue": current_metrics.average_daily_revenue,
        "growth_rate": current_metrics.growth_rate,
        "trend": current_metrics.trend
    }
    
    # Compare to previous period if requested
    if compare_to_previous:
        prev_metrics = await sales_service.get_sales_metrics(
            start_date=prev_start,
            end_date=prev_end
        )
        
        kpis["comparison"] = {
            "revenue_change": current_metrics.total_revenue - prev_metrics.total_revenue,
            "revenue_change_pct": (
                (current_metrics.total_revenue - prev_metrics.total_revenue) / 
                prev_metrics.total_revenue * 100
            ) if prev_metrics.total_revenue > 0 else 0,
            "previous_revenue": prev_metrics.total_revenue
        }
    
    return kpis


@router.get("/recommendations")
async def get_recommendations(
    context: str = Query("general", regex="^(general|weather|sales|inventory)$"),
    urgency: str = Query("all", regex="^(all|immediate|short_term|long_term)$"),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get AI-powered recommendations
    """
    ai_service = AIAgentService(db, company.id, current_user.id)
    
    # Prepare context message
    if context == "weather":
        message = "Quais ações devo tomar baseado na previsão do tempo?"
    elif context == "sales":
        message = "Como posso melhorar minhas vendas?"
    elif context == "inventory":
        message = "Como devo ajustar meu estoque?"
    else:
        message = "Quais são suas recomendações gerais para o negócio?"
    
    # Get AI recommendations
    response = await ai_service.process_message(message)
    
    # Parse recommendations
    recommendations = []
    if response.message:
        lines = response.message.split('\n')
        for line in lines:
            if line.strip() and (line.strip().startswith('-') or line.strip().startswith('•')):
                rec_text = line.strip().lstrip('-•').strip()
                
                # Categorize urgency
                rec_urgency = "short_term"
                if any(word in rec_text.lower() for word in ["imediato", "hoje", "agora", "urgente"]):
                    rec_urgency = "immediate"
                elif any(word in rec_text.lower() for word in ["longo prazo", "futuro", "planejamento"]):
                    rec_urgency = "long_term"
                
                if urgency == "all" or urgency == rec_urgency:
                    recommendations.append({
                        "text": rec_text,
                        "urgency": rec_urgency,
                        "context": context
                    })
    
    return {
        "recommendations": recommendations,
        "context": context,
        "generated_at": datetime.utcnow().isoformat()
    }