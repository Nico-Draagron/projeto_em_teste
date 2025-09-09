# ===========================
# backend/alembic/versions/001_initial_migration.py
# ===========================
"""Initial migration - Create all tables

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    op.execute("CREATE TYPE user_role AS ENUM ('admin', 'manager', 'user');")
    op.execute("CREATE TYPE alert_type AS ENUM ('weather', 'sales', 'anomaly', 'threshold', 'custom');")
    op.execute("CREATE TYPE alert_severity AS ENUM ('low', 'medium', 'high', 'critical');")
    op.execute("CREATE TYPE notification_channel AS ENUM ('email', 'sms', 'whatsapp', 'slack', 'in_app');")
    op.execute("CREATE TYPE subscription_plan AS ENUM ('trial', 'basic', 'professional', 'enterprise');")
    
    # Create companies table
    op.create_table('companies',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('business_type', sa.String(length=100), nullable=True),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('size', sa.String(length=50), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('timezone', sa.String(length=50), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('subscription_plan', postgresql.ENUM('trial', 'basic', 'professional', 'enterprise', name='subscription_plan'), nullable=True),
        sa.Column('subscription_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('api_calls_limit', sa.Integer(), nullable=True),
        sa.Column('api_calls_used', sa.Integer(), nullable=True),
        sa.Column('storage_limit_mb', sa.Integer(), nullable=True),
        sa.Column('storage_used_mb', sa.Float(), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_companies_name'), 'companies', ['name'], unique=False)
    op.create_index(op.f('ix_companies_is_active'), 'companies', ['is_active'], unique=False)
    
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.Column('is_superuser', sa.Boolean(), nullable=False),
        sa.Column('role', postgresql.ENUM('admin', 'manager', 'user', name='user_role'), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('department', sa.String(length=100), nullable=True),
        sa.Column('position', sa.String(length=100), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=True),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('preferences', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )
    op.create_index(op.f('ix_users_company_id'), 'users', ['company_id'], unique=False)
    op.create_index(op.f('ix_users_is_active'), 'users', ['is_active'], unique=False)
    
    # Create locations table
    op.create_table('locations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('postal_code', sa.String(length=20), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('timezone', sa.String(length=50), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_locations_company_id'), 'locations', ['company_id'], unique=False)
    
    # Create weather_data table
    op.create_table('weather_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('location_id', sa.String(length=36), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('time', sa.Time(), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('feels_like', sa.Float(), nullable=True),
        sa.Column('temp_min', sa.Float(), nullable=True),
        sa.Column('temp_max', sa.Float(), nullable=True),
        sa.Column('pressure', sa.Float(), nullable=True),
        sa.Column('humidity', sa.Float(), nullable=True),
        sa.Column('wind_speed', sa.Float(), nullable=True),
        sa.Column('wind_direction', sa.Float(), nullable=True),
        sa.Column('wind_gust', sa.Float(), nullable=True),
        sa.Column('cloudiness', sa.Float(), nullable=True),
        sa.Column('precipitation', sa.Float(), nullable=True),
        sa.Column('rain_1h', sa.Float(), nullable=True),
        sa.Column('rain_3h', sa.Float(), nullable=True),
        sa.Column('snow_1h', sa.Float(), nullable=True),
        sa.Column('snow_3h', sa.Float(), nullable=True),
        sa.Column('weather_condition', sa.String(length=100), nullable=True),
        sa.Column('weather_description', sa.String(length=255), nullable=True),
        sa.Column('visibility', sa.Float(), nullable=True),
        sa.Column('uv_index', sa.Float(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_weather_company_date', 'weather_data', ['company_id', 'date'], unique=False)
    op.create_index('ix_weather_location_date', 'weather_data', ['location_id', 'date'], unique=False)
    
    # Create products table
    op.create_table('products',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('sku', sa.String(length=100), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('subcategory', sa.String(length=100), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.Column('is_seasonal', sa.Boolean(), nullable=True),
        sa.Column('weather_sensitive', sa.Boolean(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'sku', name='unique_company_sku')
    )
    op.create_index(op.f('ix_products_company_id'), 'products', ['company_id'], unique=False)
    
    # Create sales_data table
    op.create_table('sales_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('location_id', sa.String(length=36), nullable=True),
        sa.Column('product_id', sa.String(length=36), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('time', sa.Time(), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('revenue', sa.Float(), nullable=False),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.Column('profit', sa.Float(), nullable=True),
        sa.Column('transactions', sa.Integer(), nullable=True),
        sa.Column('average_ticket', sa.Float(), nullable=True),
        sa.Column('customer_count', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sales_company_date', 'sales_data', ['company_id', 'date'], unique=False)
    op.create_index('ix_sales_location_date', 'sales_data', ['location_id', 'date'], unique=False)
    op.create_index('ix_sales_product_date', 'sales_data', ['product_id', 'date'], unique=False)
    
    print("✅ Initial migration completed successfully!")


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('sales_data')
    op.drop_table('products')
    op.drop_table('weather_data')
    op.drop_table('locations')
    op.drop_table('users')
    op.drop_table('companies')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS subscription_plan;")
    op.execute("DROP TYPE IF EXISTS notification_channel;")
    op.execute("DROP TYPE IF EXISTS alert_severity;")
    op.execute("DROP TYPE IF EXISTS alert_type;")
    op.execute("DROP TYPE IF EXISTS user_role;")