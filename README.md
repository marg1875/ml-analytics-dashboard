# ML Analytics - Mercado Libre Mexico

Dashboard de analisis de mercado para Mercado Libre Mexico usando su API publica.

## Funcionalidades

- **Categorias**: Explorador del arbol de categorias con graficos y drill-down
- **Predictor**: Predice la categoria de un producto por su nombre
- **Top Productos**: Top de productos mas vendidos por categoria (incluye subcategorias)

## Instalacion

```bash
pip install -r requirements.txt
```

## Configuracion

1. Crea una aplicacion en [Mercado Libre Developers](https://developers.mercadolibre.com.mx)
2. Copia tu **App ID** y **Secret Key**
3. Pegalas en `app.py` (variables `CLIENT_ID_DEFAULT` y `CLIENT_SECRET_DEFAULT`)
4. Configura el **Redirect URI** en el DevCenter: `https://localhost:8501`

## Ejecucion

```bash
streamlit run app.py
```

Abre http://localhost:8501 en tu navegador.

## Requisitos

- Python 3.8+
- Cuenta de Mercado Libre
- App registrada en ML Developers

## Datos disponibles sin autenticacion

- Arbol de categorias completo
- Numero de publicaciones por categoria
- Subcategorias

## Datos disponibles con OAuth

- Prediccion de categoria por nombre de producto
- Top productos mas vendidos por categoria
- Tendencias de busqueda por categoria y nacionales
