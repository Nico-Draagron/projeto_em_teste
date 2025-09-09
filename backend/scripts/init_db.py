# scripts/init_db.py
"""
Script para importar dados de CSV para o banco de dados.
Ajuste os modelos e campos conforme sua estrutura real.
"""
import pandas as pd
from sqlalchemy.orm import Session
from app.core.database import engine
from app.models.sales import Sale

# Exemplo: importar vendas de um arquivo CSV
CSV_PATH = "data/vendas_exemplo.csv"  # Altere para o nome do seu arquivo

def import_sales():
    df = pd.read_csv(CSV_PATH)
    with Session(engine) as session:
        for _, row in df.iterrows():
            sale = Sale(
                # Ajuste os campos conforme o modelo Sale e o CSV
                # Exemplo:
                # date=row['data'],
                # valores=row['valores'],
                # pedidos=row['pedidos'],
                # loja=row.get('loja', None)
            )
            session.add(sale)
        session.commit()
    print(f"Importação concluída: {len(df)} registros.")

if __name__ == "__main__":
    import_sales()
