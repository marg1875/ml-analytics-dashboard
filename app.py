import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import time
import urllib.parse

SITE = "MLM"
BASE_URL = "https://api.mercadolibre.com"
AUTH_URL = "https://auth.mercadolibre.com.mx/authorization"
CLIENT_ID_DEFAULT = ""   # Pega tu Client ID de Mercado Libre DevCenter
CLIENT_SECRET_DEFAULT = ""  # Pega tu Client Secret de Mercado Libre DevCenter


# ============================================================
# API - Publicas (sin auth)
# ============================================================

@st.cache_data(ttl=3600)
def get_category_detail(category_id):
    r = requests.get(f"{BASE_URL}/categories/{category_id}", timeout=15)
    return r.json() if r.status_code == 200 else None


@st.cache_data(ttl=3600)
def fetch_top_categories():
    root_ids = [
        "MLM1430", "MLM1051", "MLM1648", "MLM1000", "MLM1574", "MLM5726",
        "MLM1276", "MLM1246", "MLM1384", "MLM1132", "MLM1144", "MLM3937",
        "MLM1039", "MLM1182", "MLM3025", "MLM1743", "MLM5725", "MLM1500",
        "MLM407134", "MLM1499", "MLM409431", "MLM1071", "MLM1367", "MLM1368",
        "MLM1403", "MLM9304", "MLM1512", "MLM1168", "MLM2547", "MLM1540", "MLM1459",
    ]
    cats = []
    for cid in root_ids:
        info = get_category_detail(cid)
        if info:
            cats.append({
                "id": info["id"], "nombre": info["name"],
                "total_items": info.get("total_items_in_this_category", 0),
                "children": info.get("children_categories", []),
            })
        time.sleep(0.1)
    return sorted(cats, key=lambda x: x["total_items"], reverse=True)


@st.cache_data(ttl=3600)
def fetch_subcategories(parent_id):
    info = get_category_detail(parent_id)
    if not info:
        return None, []
    children = info.get("children_categories", [])
    subs = [{"id": c["id"], "nombre": c["name"], "total_items": c.get("total_items_in_this_category", 0)} for c in children]
    return info, sorted(subs, key=lambda x: x["total_items"], reverse=True)


# ============================================================
# API - Requiere autenticacion
# ============================================================

def exchange_code_for_token(client_id, client_secret, code, redirect_uri):
    r = requests.post(f"{BASE_URL}/oauth/token", data={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }, headers={"accept": "application/json"}, timeout=15)
    if r.status_code == 200:
        return r.json()
    try:
        return {"error": r.status_code, "body": r.json()}
    except Exception:
        return {"error": r.status_code, "body": r.text}


def predict_category(query, token):
    r = requests.get(f"{BASE_URL}/sites/{SITE}/domain_discovery/search",
                     params={"q": query, "limit": 5},
                     headers={"Authorization": f"Bearer {token}"}, timeout=15)
    return r.json() if r.status_code == 200 else []


def get_trends(token, category_id=None):
    """Obtiene tendencias de busqueda por pais y opcionalmente por categoria"""
    url = f"{BASE_URL}/trends/{SITE}"
    if category_id:
        url += f"/{category_id}"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
    return r.json() if r.status_code == 200 else None


def get_top_sellers(token, category_id):
    """Obtiene top 20 mas vendidos de una categoria"""
    r = requests.get(f"{BASE_URL}/highlights/{SITE}/category/{category_id}",
                     headers={"Authorization": f"Bearer {token}"}, timeout=15)
    if r.status_code == 200:
        return r.json()
    return None


def get_items_batch(token, item_ids):
    """Obtiene detalles de hasta 20 items en una sola llamada"""
    if not item_ids:
        return {}
    ids_str = ",".join(item_ids[:20])
    r = requests.get(f"{BASE_URL}/items?ids={ids_str}",
                     headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if r.status_code == 200:
        results = {}
        for entry in r.json():
            if entry.get("code") == 200 and entry.get("body"):
                body = entry["body"]
                results[body["id"]] = body
        return results
    return {}




# ============================================================
# UI
# ============================================================

def auth_sidebar():
    """Sidebar de autenticacion"""
    with st.sidebar:
        with st.expander("Autenticacion", expanded="access_token" not in st.session_state):
            cid = st.text_input("Client ID", value=CLIENT_ID_DEFAULT, key="auth_cid")
            csecret = st.text_input("Client Secret", value=CLIENT_SECRET_DEFAULT, type="password", key="auth_csecret")
            ruri = st.text_input("Redirect URI", value="https://comma-swooned-ipad.ngrok-free.dev", key="auth_ruri")

            auth_url = (
                f"{AUTH_URL}?response_type=code"
                f"&client_id={cid}"
                f"&redirect_uri={urllib.parse.quote(ruri, safe='')}"
                f"&scope=read"
            )
            st.markdown(f"[Abrir autorizacion ML]({auth_url})")
            st.caption("1. Abre el link, inicia sesion y autoriza")
            st.caption("2. Copia el codigo de la URL (?code=...) y pegalo:")

            code = st.text_input("Codigo de autorizacion", key="auth_code")
            if code:
                with st.spinner("Obteniendo token..."):
                    td = exchange_code_for_token(cid, csecret, code, ruri)
                if td and "access_token" in td:
                    st.session_state.access_token = td["access_token"]
                    st.session_state.refresh_token = td.get("refresh_token", "")
                    st.session_state.user_id = td.get("user_id", "")
                    st.rerun()
                else:
                    st.error(f"Error: {td}")

        if "access_token" in st.session_state:
            st.success(f"Conectado (user: {st.session_state.get('user_id', 'N/A')})")

            if st.button("Cerrar sesion"):
                for k in ["access_token", "refresh_token", "user_id"]:
                    st.session_state.pop(k, None)
                st.rerun()

        st.divider()
        with st.expander("Diagnosticar permisos"):
            if st.button("Probar endpoints", use_container_width=True):
                token = st.session_state.get("access_token")
                if token:
                    h = {"Authorization": f"Bearer {token}"}
                    tests = [
                        ("GET", f"trends/{SITE}"),
                        ("GET", f"trends/{SITE}/MLM1430"),
                        ("GET", f"highlights/{SITE}/category/MLM1430"),
                        ("GET", f"highlights/{SITE}/category/MLM1051"),
                        ("GET", "items/MLM16140709"),
                        ("GET", "items?ids=MLM16140709"),
                    ]
                    results = []
                    for method, path in tests:
                        r = requests.get(f"{BASE_URL}/{path}", headers=h, timeout=10)
                        body = r.json() if r.text else {}
                        info = ""
                        if r.status_code == 200:
                            if isinstance(body, dict):
                                if "title" in body:
                                    info = f" -> title={body['title'][:40]} price={body.get('price')}"
                                elif "content" in body:
                                    info = f" -> content={len(body['content'])} items"
                                else:
                                    info = f" -> keys={list(body.keys())[:4]}"
                            elif isinstance(body, list):
                                info = f" -> count={len(body)}"
                        else:
                            msg = body.get("message", str(body)[:60]) if isinstance(body, dict) else str(body)[:60]
                            info = f" -> {msg}"
                        results.append(f"[{r.status_code}] {path}{info}")
                    st.code("\n".join(results))
                else:
                    st.warning("Sin token")


def main():
    st.set_page_config(page_title="ML Analytics", layout="wide")
    st.title("Analisis de Mercado - Mercado Libre Mexico")

    auth_sidebar()

    tab1, tab2, tab3 = st.tabs(["Categorias", "Predictor", "Top Productos"])

    # ============================================================
    # TAB 1: CATEGORY EXPLORER
    # ============================================================
    with tab1:
        with st.spinner("Cargando categorias..."):
            categories = fetch_top_categories()

        if not categories:
            st.error("No se pudieron cargar las categorias.")
            return

        total_all = sum(c["total_items"] for c in categories)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total publicaciones ML Mexico", f"{total_all:,}")
        c2.metric("Categorias", len(categories))
        c3.metric("#1", categories[0]["nombre"])

        st.divider()

        ch1, ch2 = st.columns([3, 2])
        with ch1:
            st.subheader("Publicaciones por Categoria")
            df_cats = pd.DataFrame(categories)
            fig = px.bar(df_cats.head(15), x="total_items", y="nombre", orientation="h",
                         color="total_items", color_continuous_scale="Blues",
                         labels={"total_items": "Publicaciones", "nombre": ""}, text_auto=".2s")
            fig.update_layout(yaxis_categoryorder="total ascending", height=520, coloraxis_showscale=False)
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

        with ch2:
            st.subheader("Distribucion")
            df_top5 = df_cats.head(8).copy()
            others = df_cats.iloc[8:]["total_items"].sum()
            if others > 0:
                df_top5 = pd.concat([df_top5, pd.DataFrame([{"nombre": "Otras", "total_items": others}])])
            fig_pie = px.pie(df_top5, names="nombre", values="total_items", hole=0.4)
            fig_pie.update_traces(textinfo="percent")
            fig_pie.update_layout(height=520)
            st.plotly_chart(fig_pie, use_container_width=True)

        st.divider()
        st.subheader("Explora subcategorias")
        cat_names = {c["nombre"]: c for c in categories}
        selected = st.selectbox("Selecciona una categoria", list(cat_names.keys()))

        if selected and cat_names[selected]["children"]:
            parent = cat_names[selected]
            with st.spinner(f"Cargando..."):
                _, subs = fetch_subcategories(parent["id"])

            if subs:
                sc1, sc2 = st.columns([3, 2])
                with sc1:
                    st.subheader(f"{selected}")
                    st.caption(f"Total: {parent['total_items']:,} publicaciones")
                    df_subs = pd.DataFrame(subs)
                    fig_sub = px.bar(df_subs.head(20), x="total_items", y="nombre", orientation="h",
                                     color="total_items", color_continuous_scale="Oranges",
                                     labels={"total_items": "Publicaciones", "nombre": ""}, text_auto=".2s")
                    fig_sub.update_layout(yaxis_categoryorder="total ascending",
                                         height=max(400, len(df_subs.head(20))*25), coloraxis_showscale=False)
                    fig_sub.update_traces(textposition="outside")
                    st.plotly_chart(fig_sub, use_container_width=True)
                with sc2:
                    df_subtop = df_subs.head(8).copy()
                    rem = df_subs.iloc[8:]["total_items"].sum()
                    if rem > 0:
                        df_subtop = pd.concat([df_subtop, pd.DataFrame([{"nombre": "Resto", "total_items": rem}])])
                    fig_sp = px.pie(df_subtop, names="nombre", values="total_items", hole=0.4)
                    fig_sp.update_traces(textinfo="percent")
                    fig_sp.update_layout(height=450)
                    st.plotly_chart(fig_sp, use_container_width=True)

                df_subs["%"] = (df_subs["total_items"] / parent["total_items"] * 100).round(1)
                st.dataframe(df_subs, column_config={
                    "nombre": "Subcategoria",
                    "total_items": st.column_config.NumberColumn("Publicaciones", format="%d"),
                    "%": st.column_config.NumberColumn("% del total", format="%.1f%%"),
                }, use_container_width=True, hide_index=True, height=300)

        st.divider()
        df_all = pd.DataFrame(categories)
        df_all["%"] = (df_all["total_items"] / total_all * 100).round(1)
        df_all["Subcats"] = df_all["children"].apply(len)
        st.dataframe(df_all[["nombre", "total_items", "%", "Subcats"]], column_config={
            "nombre": "Categoria", "total_items": st.column_config.NumberColumn("Publicaciones", format="%d"),
            "%": st.column_config.NumberColumn("% mercado", format="%.1f%%"),
            "Subcats": st.column_config.NumberColumn("Subcats", format="%d"),
        }, use_container_width=True, hide_index=True, height=500)

        st.download_button("Descargar CSV",
                           df_all[["nombre", "total_items", "%", "Subcats"]].to_csv(index=False).encode("utf-8"),
                           file_name=f"ml_categorias_{SITE}.csv", mime="text/csv")

    # ============================================================
    # TAB 2: CATEGORY PREDICTOR
    # ============================================================
    with tab2:
        st.subheader("Predice la categoria de un producto")

        if "access_token" not in st.session_state:
            st.info("Autenticate en la sidebar primero.")
        else:
            query = st.text_input("Nombre del producto", value="camisa manga larga",
                                  placeholder="Ej: zapatos nike, laptop gamer...")
            if st.button("Predecir", type="primary"):
                with st.spinner("Prediciendo..."):
                    predictions = predict_category(query, st.session_state.access_token)

                if predictions:
                    st.subheader(f"Resultado: **{query}**")
                    rows = []
                    for p in predictions:
                        rows.append({
                            "Dominio": p.get("domain_name", "N/A"),
                            "Categoria predicha": p.get("category_name", "N/A"),
                            "Category ID": p.get("category_id", ""),
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                    for i, p in enumerate(predictions):
                        attrs = p.get("attributes", [])
                        if attrs:
                            with st.expander(f"Atributos: {p.get('category_name', '')}"):
                                ar = [{"Atributo": a.get("name"), "Valor": a.get("value_name")} for a in attrs]
                                st.dataframe(pd.DataFrame(ar), use_container_width=True, hide_index=True)

                    top_cat_id = predictions[0].get("category_id")
                    if top_cat_id:
                        with st.spinner("Cargando detalles..."):
                            cat_info = get_category_detail(top_cat_id)
                        if cat_info:
                            st.divider()
                            st.subheader(f"Categoria: {cat_info.get('name')}")
                            c1, c2 = st.columns(2)
                            c1.metric("Publicaciones", f"{cat_info.get('total_items_in_this_category', 0):,}")
                            c2.metric("Subcategorias", len(cat_info.get("children_categories", [])))
                            children = cat_info.get("children_categories", [])
                            if children:
                                df_ch = pd.DataFrame([
                                    {"Subcategoria": c["name"],
                                     "Publicaciones": c.get("total_items_in_this_category", 0)}
                                    for c in sorted(children, key=lambda x: x.get("total_items_in_this_category", 0), reverse=True)
                                ])
                                if cat_info.get("total_items_in_this_category", 1) > 0:
                                    df_ch["%"] = (df_ch["Publicaciones"] / cat_info["total_items_in_this_category"] * 100).round(1)
                                st.dataframe(df_ch, use_container_width=True, hide_index=True)
                else:
                    st.warning("Sin predicciones. Prueba otro termino.")

    # ============================================================
    # TAB 3: TOP PRODUCTOS
    # ============================================================
    with tab3:
        if "access_token" not in st.session_state:
            st.info("Autenticate en la sidebar.")
        else:
            token = st.session_state.access_token

            with st.spinner("Cargando categorias..."):
                categories = fetch_top_categories()
            cat_options = {c["nombre"]: c for c in categories}
            selected_cat = st.selectbox("Categoria", list(cat_options.keys()), key="topsell_cat")

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                show_trends = st.button("Tendencias", use_container_width=True)
            with col_btn2:
                show_top = st.button("Top Productos", type="primary", use_container_width=True)

            if show_trends and selected_cat:
                cat_info = cat_options[selected_cat]
                with st.spinner(f"Obteniendo tendencias de {selected_cat}..."):
                    trends = get_trends(token, category_id=cat_info["id"])
                if trends and isinstance(trends, list) and len(trends) > 0:
                    st.subheader(f"Tendencias: {selected_cat}")
                    rows = []
                    for i, t in enumerate(trends):
                        rows.append({"#": i + 1, "Termino": t.get("keyword", "N/A").title(),
                                     "Link": t.get("url", "")})
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                                 column_config={"Link": st.column_config.LinkColumn("Ver en ML")})
                else:
                    st.info(f"Sin tendencias para '{selected_cat}'.")

            if show_top and selected_cat:
                cat_info = cat_options[selected_cat]
                deep_mode = st.checkbox("Incluir subcategorias", value=True,
                                        help="Combina los tops de todas las subcategorias")

                with st.spinner("Obteniendo top productos..."):
                    all_products = []
                    seen_ids = set()

                    def fetch_and_collect(cat_id, cat_name):
                        td = get_top_sellers(token, cat_id)
                        if td and "content" in td:
                            for item in td["content"]:
                                if item.get("type") in ("PRODUCT", "USER_PRODUCT"):
                                    eid = item["id"]
                                    if eid not in seen_ids:
                                        seen_ids.add(eid)
                                        all_products.append({**item, "_cat": cat_name})

                    fetch_and_collect(cat_info["id"], selected_cat)

                    if deep_mode and cat_info["children"]:
                        subcats = cat_info["children"]
                        for sc in subcats:
                            fetch_and_collect(sc["id"], sc["name"])
                            time.sleep(0.25)

                    all_products.sort(key=lambda x: x.get("position", 999))

                if not all_products:
                    st.info("Sin productos de catalogo en esta categoria.")
                else:
                    st.subheader(f"Top Productos: {selected_cat}")
                    st.caption(f"{len(all_products)} productos encontrados" +
                               (" (incluye subcategorias)" if deep_mode else ""))

                    max_display = st.slider("Cantidad a mostrar", 5, min(200, len(all_products)),
                                           min(50, len(all_products)), 5)
                    products_only = all_products[:max_display]

                    # Resolver detalles
                    all_ids = [i["id"] for i in products_only]
                    product_map = {}

                    with st.spinner(f"Resolviendo {len(all_ids)} IDs..."):
                        item_map = get_items_batch(token, all_ids)
                        product_map.update(item_map)

                        unresolved = [eid for eid in all_ids
                                     if eid not in product_map or not product_map[eid].get("title")]
                        progress = st.progress(0)
                        for i, pid in enumerate(unresolved):
                            r = requests.get(f"{BASE_URL}/products/{pid}",
                                headers={"Authorization": f"Bearer {token}"}, timeout=10)
                            if r.status_code == 200:
                                body = r.json()
                                existing = product_map.get(pid, {})
                                product_map[pid] = {
                                    "title": body.get("name") or body.get("title") or existing.get("title"),
                                    "price": existing.get("price"),
                                    "available_quantity": existing.get("available_quantity"),
                                    "sold_quantity": existing.get("sold_quantity", 0),
                                    "condition": existing.get("condition", "-"),
                                    "permalink": f"https://www.mercadolibre.com.mx/p/{pid}",
                                    "currency_id": "MXN",
                                }
                            progress.progress((i + 1) / len(unresolved))
                            time.sleep(0.08)
                        progress.empty()

                    # Build table - only useful columns
                    rows = []
                    for entry in products_only:
                        eid = entry["id"]
                        detail = product_map.get(eid)
                        link = detail.get("permalink") if detail else ""
                        if not link:
                            link = f"https://www.mercadolibre.com.mx/p/{eid}"

                        title = ""
                        price_str = ""
                        if detail:
                            title = (detail.get("title") or "").strip()
                            price = detail.get("price")
                            if price and isinstance(price, (int, float)):
                                currency = detail.get("currency_id", "MXN")
                                price_str = f"${price:,.0f} {currency}"

                        rows.append({
                            "#": len(rows) + 1,
                            "Producto": title if title else link,
                            "Precio": price_str,
                            "Subcategoria": entry.get("_cat", ""),
                            "Link": link,
                        })

                    df_top = pd.DataFrame(rows)

                    st.dataframe(df_top, use_container_width=True, hide_index=True,
                                 column_config={
                                     "Producto": st.column_config.TextColumn("Producto", width="large"),
                                     "Precio": st.column_config.TextColumn("Precio", width="small"),
                                     "Subcategoria": st.column_config.TextColumn("Subcategoria", width="medium"),
                                     "Link": st.column_config.LinkColumn("Link"),
                                 })

                    st.download_button("Descargar CSV",
                                       df_top.to_csv(index=False).encode("utf-8"),
                                       file_name=f"ml_top_{selected_cat.lower().replace(' ','_')}.csv",
                                       mime="text/csv")

            # Tendencias nacionales
            st.divider()
            st.subheader("Tendencias generales en ML Mexico")
            if st.button("Ver tendencias nacionales", use_container_width=True):
                with st.spinner("Cargando..."):
                    nat_trends = get_trends(token)
                if nat_trends and isinstance(nat_trends, list):
                    st.caption("Busquedas con mayor crecimiento esta semana")
                    rows = [{"#": i+1, "Termino": t.get("keyword", "").title(),
                             "Link": t.get("url", "")} for i, t in enumerate(nat_trends)]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                                 column_config={"Link": st.column_config.LinkColumn("Ver")}, height=500)
                else:
                    st.info("No disponible.")


if __name__ == "__main__":
    main()
