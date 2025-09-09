"""
Modelo de dados de vendas para o sistema WeatherBiz Analytics.
Armazena informações de vendas, produtos e categorias.
"""

from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, DateTime, Date,
    ForeignKey, Numeric, Index, UniqueConstraint,
    JSON, Boolean, Text
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.config.database import Base, TimestampMixin, TenantMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.company import Company


class ProductCategory(Base, TimestampMixin, TenantMixin):
    """
    Categorias de produtos.
    """
    
    __tablename__ = "product_categories"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== CATEGORY INFO ====================
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Nome da categoria"
    )
    
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Slug da categoria"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Descrição da categoria"
    )
    
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("product_categories.id"),
        nullable=True,
        doc="ID da categoria pai (hierarquia)"
    )
    
    # ==================== DISPLAY ====================
    icon: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Ícone da categoria"
    )
    
    color: Mapped[Optional[str]] = mapped_column(
        String(7),
        nullable=True,
        doc="Cor da categoria (hex)"
    )
    
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Ordem de exibição"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Se está ativa"
    )
    
    # ==================== WEATHER SENSITIVITY ====================
    weather_sensitive: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Se é sensível ao clima"
    )
    
    sensitivity_factors: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Fatores de sensibilidade climática"
    )
    
    # ==================== METADATA ====================
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Metadados adicionais"
    )
    
    # ==================== RELATIONSHIPS ====================
    parent: Mapped[Optional["ProductCategory"]] = relationship(
        "ProductCategory",
        remote_side=[id],
        backref="subcategories"
    )
    
    products: Mapped[List["Product"]] = relationship(
        "Product",
        back_populates="category",
        cascade="all, delete-orphan"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        # Índice único para empresa + slug
        UniqueConstraint("company_id", "slug", name="uq_category_company_slug"),
        
        # Índices para queries
        Index("idx_category_company_active", "company_id", "is_active"),
        Index("idx_category_parent", "parent_id"),
    )
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<ProductCategory(id={self.id}, name={self.name})>"
    
    def __str__(self) -> str:
        return self.name


class Product(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """
    Produtos da empresa.
    """
    
    __tablename__ = "products"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== PRODUCT INFO ====================
    sku: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="SKU do produto"
    )
    
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Nome do produto"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Descrição do produto"
    )
    
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("product_categories.id"),
        nullable=True,
        index=True,
        doc="ID da categoria"
    )
    
    # ==================== PRICING ====================
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        doc="Preço unitário"
    )
    
    cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        doc="Custo unitário"
    )
    
    currency: Mapped[str] = mapped_column(
        String(3),
        default="BRL",
        nullable=False,
        doc="Moeda"
    )
    
    # ==================== INVENTORY ====================
    stock_quantity: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Quantidade em estoque"
    )
    
    min_stock: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Estoque mínimo"
    )
    
    max_stock: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Estoque máximo"
    )
    
    # ==================== STATUS ====================
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Se está ativo"
    )
    
    is_seasonal: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se é produto sazonal"
    )
    
    season_start: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Mês de início da temporada (1-12)"
    )
    
    season_end: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Mês de fim da temporada (1-12)"
    )
    
    # ==================== WEATHER SENSITIVITY ====================
    weather_sensitive: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Se é sensível ao clima"
    )
    
    optimal_temp_min: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Temperatura mínima ótima"
    )
    
    optimal_temp_max: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Temperatura máxima ótima"
    )
    
    rain_impact: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        doc="Impacto da chuva (positive/negative/neutral)"
    )
    
    # ==================== METADATA ====================
    barcode: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Código de barras"
    )
    
    image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="URL da imagem"
    )
    
    tags: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Tags do produto"
    )
    
    attributes: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Atributos adicionais"
    )
    
    # ==================== RELATIONSHIPS ====================
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="products"
    )
    
    category: Mapped[Optional["ProductCategory"]] = relationship(
        "ProductCategory",
        back_populates="products"
    )
    
    sales_data: Mapped[List["SalesData"]] = relationship(
        "SalesData",
        back_populates="product",
        cascade="all, delete-orphan"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        # Índice único para empresa + SKU
        UniqueConstraint("company_id", "sku", name="uq_product_company_sku"),
        
        # Índices para queries
        Index("idx_product_company_active", "company_id", "is_active"),
        Index("idx_product_category", "category_id"),
        Index("idx_product_seasonal", "is_seasonal"),
    )
    
    # ==================== PROPERTIES ====================
    @property
    def margin(self) -> Optional[float]:
        """Calcula margem de lucro."""
        if self.cost and self.price:
            return float((self.price - self.cost) / self.price * 100)
        return None
    
    @property
    def is_in_season(self) -> bool:
        """Verifica se está na temporada."""
        if not self.is_seasonal:
            return True
        
        if not self.season_start or not self.season_end:
            return True
        
        current_month = datetime.now().month
        
        if self.season_start <= self.season_end:
            return self.season_start <= current_month <= self.season_end
        else:  # Temporada cruza o ano
            return current_month >= self.season_start or current_month <= self.season_end
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku={self.sku}, name={self.name})>"
    
    def __str__(self) -> str:
        return f"{self.sku} - {self.name}"


class SalesData(Base, TimestampMixin, TenantMixin):
    """
    Dados de vendas diárias.
    """
    
    __tablename__ = "sales_data"
    
    # ==================== PRIMARY KEY ====================
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ==================== TEMPORAL ====================
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        doc="Data da venda"
    )
    
    hour: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Hora da venda (0-23)"
    )
    
    week_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Dia da semana (0=Segunda)"
    )
    
    month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Mês (1-12)"
    )
    
    year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Ano"
    )
    
    quarter: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Trimestre (1-4)"
    )
    
    # ==================== PRODUCT ====================
    product_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("products.id"),
        nullable=True,
        index=True,
        doc="ID do produto"
    )
    
    product_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Nome do produto (backup)"
    )
    
    category_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Nome da categoria (backup)"
    )
    
    # ==================== LOCATION ====================
    store_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="ID da loja/filial"
    )
    
    store_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Nome da loja/filial"
    )
    
    region: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Região de venda"
    )
    
    # ==================== SALES METRICS ====================
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Quantidade vendida"
    )
    
    revenue: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        doc="Receita total"
    )
    
    cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        doc="Custo total"
    )
    
    profit: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        doc="Lucro total"
    )
    
    discount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        doc="Desconto aplicado"
    )
    
    # ==================== CUSTOMER METRICS ====================
    transactions_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Número de transações"
    )
    
    customers_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Número de clientes únicos"
    )
    
    average_ticket: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        doc="Ticket médio"
    )
    
    # ==================== CHANNEL ====================
    sales_channel: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Canal de venda (store/online/app)"
    )
    
    payment_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Método de pagamento principal"
    )
    
    # ==================== WEATHER CORRELATION ====================
    weather_data_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="ID dos dados climáticos do dia"
    )
    
    temperature_at_sale: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        doc="Temperatura no momento da venda"
    )
    
    weather_condition_at_sale: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Condição climática na venda"
    )
    
    # ==================== COMPARISON ====================
    revenue_last_year: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        doc="Receita mesmo período ano anterior"
    )
    
    revenue_last_month: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        doc="Receita mesmo dia mês anterior"
    )
    
    growth_yoy: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        doc="Crescimento ano a ano (%)"
    )
    
    growth_mom: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        doc="Crescimento mês a mês (%)"
    )
    
    # ==================== FLAGS ====================
    is_holiday: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se é feriado"
    )
    
    is_weekend: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se é fim de semana"
    )
    
    is_promotion: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se teve promoção"
    )
    
    is_anomaly: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Se é anomalia (outlier)"
    )
    
    # ==================== METADATA ====================
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Observações"
    )
    
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Metadados adicionais"
    )
    
    # ==================== RELATIONSHIPS ====================
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="sales_data"
    )
    
    product: Mapped[Optional["Product"]] = relationship(
        "Product",
        back_populates="sales_data"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        # Índices para queries comuns
        Index("idx_sales_company_date", "company_id", "date"),
        Index("idx_sales_product_date", "product_id", "date"),
        Index("idx_sales_date_product", "date", "product_id"),
        Index("idx_sales_company_month_year", "company_id", "month", "year"),
        Index("idx_sales_store", "store_id", "date"),
    )
    
    # ==================== PROPERTIES ====================
    @property
    def margin(self) -> Optional[float]:
        """Calcula margem de lucro."""
        if self.cost and self.revenue:
            return float((self.revenue - self.cost) / self.revenue * 100)
        return None
    
    @property
    def average_price(self) -> Optional[float]:
        """Calcula preço médio unitário."""
        if self.quantity > 0:
            return float(self.revenue / self.quantity)
        return None
    
    # ==================== METHODS ====================
    def to_dict(self) -> dict:
        """
        Converte dados de vendas para dicionário.
        
        Returns:
            dict: Dados de vendas
        """
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "category_name": self.category_name,
            "quantity": self.quantity,
            "revenue": float(self.revenue) if self.revenue else 0,
            "cost": float(self.cost) if self.cost else None,
            "profit": float(self.profit) if self.profit else None,
            "margin": self.margin,
            "average_price": self.average_price,
            "transactions_count": self.transactions_count,
            "customers_count": self.customers_count,
            "average_ticket": float(self.average_ticket) if self.average_ticket else None,
            "weather_condition": self.weather_condition_at_sale,
            "temperature": float(self.temperature_at_sale) if self.temperature_at_sale else None,
            "is_holiday": self.is_holiday,
            "is_weekend": self.is_weekend,
            "is_promotion": self.is_promotion
        }
    
    # ==================== STRING REPRESENTATION ====================
    def __repr__(self) -> str:
        return f"<SalesData(date={self.date}, revenue={self.revenue})>"
    
    def __str__(self) -> str:
        return f"{self.date}: R$ {self.revenue}"