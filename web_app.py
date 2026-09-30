import streamlit as st
import sqlite3
import pdfplumber
import pandas as pd
import re
from datetime import datetime
import os
import base64

# ==========================================================
# 1. SAYFA YAPILANDIRMASI
# ==========================================================
st.set_page_config(
    page_title="BLUECREA İŞ VE MÜŞTERİ TAKİP",
    page_icon="📦",
    layout="wide"
)

# ==========================================================
# 2. APPLE / İPHONE İKON (FAVICON) TANIMLAMASI VE CSS
# ==========================================================
icon_path = "favicon.png"
icon_base64 = ""
if os.path.exists(icon_path):
    with open(icon_path, "rb") as f:
        icon_base64 = base64.b64encode(f.read()).decode()

st.markdown(f"""
<head>
    <link rel="apple-touch-icon" href="data:image/png;base64,{icon_base64}">
    <link rel="icon" type="image/png" href="data:image/png;base64,{icon_base64}">
</head>
""", unsafe_allow_html=True)

st.markdown("""
<style>
    .main { background-color: #141414; color: #F8F9FA; }
    .stApp { background-color: #141414; }
    h1, h2, h3, h4 { color: #00B4D8 !important; }
    
    .stock-row-wrapper {
        position: relative;
        width: 100%;
        margin-bottom: 6px;
        overflow: hidden;
        border-radius: 8px;
        border: 1px solid #222;
        background: #161616;
        transition: border-color 0.2s;
    }
    .stock-row-wrapper:hover {
        border-color: #E63946;
    }
    
    .stock-row-grid {
        display: grid;
        grid-template-columns: 1fr 1.5fr 1fr 2fr 1.2fr 1fr 1fr 1.2fr 1.2fr 1.5fr;
        padding: 12px 15px;
        align-items: center;
        font-size: 13px;
        background: #161616;
        transition: background 0.2s;
    }
    .stock-row-wrapper:hover .stock-row-grid {
        background: #1A1E24;
    }

    .stock-delete-slide {
        position: absolute;
        right: -80px; 
        top: 0;
        bottom: 0;
        width: 80px;
        background: #E63946;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: right 0.25s ease-in-out;
        z-index: 5;
    }
    .stock-row-wrapper:hover .stock-delete-slide {
        right: 0px;
    }
    .stock-delete-slide form {
        width: 100%; height: 100%; margin: 0; display: flex;
    }
    .stock-delete-slide button {
        width: 100%; height: 100%;
        background: transparent; color: white; border: none; font-size: 13px; font-weight: bold; cursor: pointer;
    }
    .stock-delete-slide button:hover {
        background: #D90429;
    }
</style>
""", unsafe_allow_html=True)


DB = "ambalaj_web.db"

def init_db():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS customers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address TEXT,
        email TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        product TEXT NOT NULL,
        dimension TEXT,
        material TEXT,
        label_type TEXT,
        quantity INTEGER NOT NULL,
        unit_price REAL,
        total_price REAL,
        delivery_date TEXT,
        status TEXT NOT NULL DEFAULT 'Aktif',
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS stock(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT,
        company TEXT,
        dimension TEXT,
        product_name TEXT,
        paper_type TEXT,
        core_diameter TEXT,
        roll_quantity TEXT,
        unit_price REAL,
        quantity INTEGER,
        critical_level INTEGER
    )""")
    
    existing_cols = [col[1] for col in cur.execute("PRAGMA table_info(customers)").fetchall()]
    if "phone" in existing_cols and "address" not in existing_cols:
        cur.execute("ALTER TABLE customers ADD COLUMN address TEXT")
    if "contact" in existing_cols and "email" not in existing_cols:
        cur.execute("ALTER TABLE customers ADD COLUMN email TEXT")

    existing_stock_cols = [col[1] for col in cur.execute("PRAGMA table_info(stock)").fetchall()]
    columns_to_add = {
        "company": "TEXT",
        "dimension": "TEXT",
        "paper_type": "TEXT",
        "core_diameter": "TEXT",
        "roll_quantity": "TEXT",
        "unit_price": "REAL",
        "quantity": "INTEGER",
        "critical_level": "INTEGER"
    }
    for col_name, col_type in columns_to_add.items():
        if col_name not in existing_stock_cols:
            cur.execute(f"ALTER TABLE stock ADD COLUMN {col_name} {col_type}")
            
    con.commit()
    con.close()

init_db()

header_html = """<div style='background: linear-gradient(90deg, #0A192F 0%, #00B4D8 100%); padding: 15px; border-radius: 10px; margin-bottom: 20px;'>
<h2 style='color: white !important; margin: 0; font-size: 20px;'>BLUECREA ETİKET AMBALAJ SAN. TİC. LTD. ŞTİ.</h2>
<p style='color: #E0E0E0; margin: 0; font-size: 14px;'>İş ve Müşteri Takip Programı</p>
</div>"""
st.markdown(header_html, unsafe_allow_html=True)


# ==========================================================
# 3. SEKMELER VE MODÜLLER
# ==========================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Siparişler & Fişler", "➕ Yeni Sipariş / Müşteri", "📦 Depo & Stok", "📄 Çoklu PDF (Otomasyon)", "📊 Durum & Özet"])

# --- SEKME 1: SİPARİŞLER VE FİŞLER ---
with tab1:
    st.subheader("🧾 Siparişler ve Termin Fişleri Arşivi")
    st.markdown("💡 *Aktif siparişler yukarıda listelenir. Teslim edilenler aşağıdaki özel arşiv bölümünde yeşil renkli olarak gösterilir.*")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        with st.expander("➕ Arşive Manuel Sipariş Fişi Ekle", expanded=False):
            con = sqlite3.connect(DB)
            cust_rows_slip = con.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
            con.close()
            
            if cust_rows_slip:
                cust_dict_slip = {f"{r[0]} - {r[1]}": r[0] for r in cust_rows_slip}
                with st.form("manual_slip_form"):
                    m_cust = st.selectbox("Firma / Müşteri Seçin", options=list(cust_dict_slip.keys()))
                    m_prod = st.text_input("Ürün / Etiket Adı ve Detayı")
                    m_qty = st.number_input("Miktar (Adet)", min_value=1, value=1000)
                    m_date = st.text_input("Termin Tarihi (Örn: 15.10.2026)")
                    
                    if st.form_submit_button("Fişi Arşive Ekle"):
                        con = sqlite3.connect(DB)
                        con.execute("INSERT INTO orders(customer_id, product, dimension, material, label_type, quantity, unit_price, total_price, delivery_date, status) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                    (cust_dict_slip[m_cust], m_prod, "Manuel Fiş", "Manuel", "Manuel", m_qty, 0.0, 0.0, m_date, "Aktif"))
                        con.commit()
                        con.close()
                        st.success("🎉 Fiş eklendi!")
                        st.rerun()

    with col_p2:
        with st.expander("✏️️ Fiş Durumunu veya Detayını Güncelle", expanded=False):
            con = sqlite3.connect(DB)
            all_active_slips = con.execute("SELECT o.id, c.name, o.product, o.quantity, o.delivery_date, o.status FROM orders o JOIN customers c ON c.id=o.customer_id ORDER BY o.id DESC").fetchall()
            con.close()
            
            if all_active_slips:
                slip_edit_dict = {f"ID: #{s[0]} | {s[1]} - {s[2]} (Durum: {s[5]})": s[0] for s in all_active_slips}
                with st.form("edit_slip_form"):
                    sel_slip_to_edit = st.selectbox("Düzenlenecek Fişi Seçin", options=list(slip_edit_dict.keys()))
                    edit_id = slip_edit_dict[sel_slip_to_edit]
                    
                    con = sqlite3.connect(DB)
                    current_slip = con.execute("SELECT product, quantity, delivery_date, status FROM orders WHERE id=?", (edit_id,)).fetchone()
                    con.close()
                    
                    e_prod = st.text_input("Ürün Adı", value=current_slip[0] or "")
                    e_qty = st.number_input("Miktar", min_value=1, value=int(current_slip[1] or 1000))
                    e_date = st.text_input("Termin Tarihi", value=current_slip[2] or "")
                    e_status = st.selectbox("Durum", options=["Aktif", "Teslim Edildi ✅"], index=0 if current_slip[3]=="Aktif" else 1)
                    
                    if st.form_submit_button("💾 Güncellemeyi Kaydet"):
                        con = sqlite3.connect(DB)
                        con.execute("UPDATE orders SET product=?, quantity=?, delivery_date=?, status=? WHERE id=?", (e_prod, e_qty, e_date, e_status, edit_id))
                        con.commit()
                        con.close()
                        st.success("🎉 Başarıyla güncellendi!")
                        st.rerun()

    st.markdown("---")

    con = sqlite3.connect(DB)
    archived_orders = con.execute("""
        SELECT o.id, c.name, o.product, o.dimension, o.material, o.quantity, o.delivery_date, o.status, o.total_price
        FROM orders o 
        JOIN customers c ON c.id = o.customer_id 
        ORDER BY o.delivery_date ASC, c.name ASC
    """).fetchall()
    con.close()

    if archived_orders:
        dates = sorted(list(set([ord[6] for ord in archived_orders if ord[6]])))
        selected_date_filter = st.selectbox("📅 Termin Tarihine Göre Filtrele", options=["Tüm Terminler"] + dates)
        
        filtered_orders = archived_orders if selected_date_filter == "Tüm Terminler" else [o for o in archived_orders if o[6] == selected_date_filter]
        
        active_list = [o for o in filtered_orders if o[7] == "Aktif"]
        closed_list = [o for o in filtered_orders if o[7] != "Aktif"]

        st.markdown("### ⚡ Aktif Siparişler ve Termin Fişleri")
        
        if active_list:
            with st.form("bulk_delete_form"):
                selected_ids_to_delete = []
                
                current_group_date = None
                for ord_item in active_list:
                    o_id, c_name, prod, dim, mat, qty, d_date, status, price = ord_item
                    qty_fmt = f"{qty:,}".replace(",", ".")
                    
                    if d_date != current_group_date:
                        current_group_date = d_date
                        st.markdown(f"""
                        <div style='background: linear-gradient(90deg, #0A192F 0%, #112240 100%); padding: 10px 15px; border-radius: 6px; margin-top: 15px; margin-bottom: 8px; border-left: 5px solid #4ECDC4;'>
                            <h4 style='color: #4ECDC4; margin: 0; font-size: 16px;'>📅 {current_group_date} Terminleri</h4>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    col_chk, col_content = st.columns([0.05, 0.95])
                    with col_chk:
                        is_checked = st.checkbox("", key=f"chk_{o_id}", label_visibility="collapsed")
                        if is_checked:
                            selected_ids_to_delete.append(o_id)
                    with col_content:
                        st.markdown(f"""
                        <div style='background: #1A1A1A; border: 1px solid #333; border-left: 5px solid #4ECDC4; padding: 12px; border-radius: 8px; margin-bottom: 8px;'>
                            <div style='display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #282828; padding-bottom: 4px; margin-bottom: 4px;'>
                                <span style='color: #00B4D8; font-weight: bold; font-size: 13px;'>🏢 Firma: {c_name}</span>
                                <span style='background: #0A192F; color: #4ECDC4; padding: 2px 6px; border-radius: 4px; font-size: 11px;'>📅 Termin: {d_date}</span>
                            </div>
                            <div style='display: grid; grid-template-columns: 2fr 1fr; font-size: 13px;'>
                                <div><b>Ürün:</b> {prod}</div>
                                <div><b>Miktar:</b> <span style='color: #4ECDC4; font-weight: bold;'>{qty_fmt} Adet</span></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                bulk_submit = st.form_submit_button("🗑️ Seçilen İşaretli Siparişleri Toplu Sil")
                if bulk_submit:
                    if selected_ids_to_delete:
                        con = sqlite3.connect(DB)
                        cur = con.cursor()
                        for sid in selected_ids_to_delete:
                            cur.execute("DELETE FROM orders WHERE id=?", (sid,))
                        con.commit()
                        con.close()
                        st.success(f"✅ Seçilen {len(selected_ids_to_delete)} adet sipariş başarıyla silindi!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Silmek için herhangi bir sipariş seçmediniz.")
        else:
            st.info("Aktif sipariş bulunmuyor.")

        st.markdown("---")
        st.markdown("### 📥 Teslim Edilen Siparişler Arşivi")
        
        if closed_list:
            with st.form("bulk_delete_closed_form"):
                closed_ids_to_delete = []
                for ord_item in closed_list:
                    o_id, c_name, prod, dim, mat, qty, d_date, status, price = ord_item
                    qty_fmt = f"{qty:,}".replace(",", ".")
                    
                    col_chk, col_content = st.columns([0.05, 0.95])
                    with col_chk:
                        is_checked_c = st.checkbox("", key=f"chk_c_{o_id}", label_visibility="collapsed")
                        if is_checked_c:
                            closed_ids_to_delete.append(o_id)
                    with col_content:
                        st.markdown(f"""
                        <div style='background: #161616; border: 1px solid #2A2A2A; border-left: 5px solid #2A9D8F; padding: 12px; border-radius: 8px; margin-bottom: 8px;'>
                            <div style='display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #222; padding-bottom: 4px; margin-bottom: 4px;'>
                                <span style='color: #2A9D8F; font-weight: bold; font-size: 13px;'>🏢 Firma: {c_name} | Durum: <span style='color: #2A9D8F;'>Teslim Edildi ✅</span></span>
                                <span style='background: #0A192F; color: #4ECDC4; padding: 2px 6px; border-radius: 4px; font-size: 11px;'>📅 Termin: {d_date}</span>
                            </div>
                            <div style='display: grid; grid-template-columns: 2fr 1fr; font-size: 13px;'>
                                <div><b>Ürün:</b> {prod}</div>
                                <div><b>Miktar:</b> <span style='color: #4ECDC4; font-weight: bold;'>{qty_fmt} Adet</span></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                
                closed_submit = st.form_submit_button("🗑 Seçilen Arşivlenmiş Siparişleri Toplu Sil")
                if closed_submit:
                    if closed_ids_to_delete:
                        con = sqlite3.connect(DB)
                        cur = con.cursor()
                        for sid in closed_ids_to_delete:
                            cur.execute("DELETE FROM orders WHERE id=?", (sid,))
                        con.commit()
                        con.close()
                        st.success(f"✅ Seçilen {len(closed_ids_to_delete)} adet teslim edilmiş sipariş arşivden silindi!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Silmek için herhangi bir sipariş seçmediniz.")
        else:
            st.info("Teslim edilip arşivlenmiş sipariş bulunmuyor.")
    else:
        st.info("Sistemde henüz kayıtlı sipariş bulunmuyor.")

# --- SEKME 2: YENİ MÜŞTERİ / SİPARİŞ VE MÜŞTERİ LİSTESİ ---
with tab2:
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 👤 Yeni Müşteri / Firma Ekle")
        with st.form("cust_form"):
            c_name = st.text_input("Müşteri / Firma Adı")
            c_address = st.text_area("Adres")
            c_email = st.text_input("Mail Adresi")
            c_submit = st.form_submit_button("Müşteri Kaydet")
            
            if c_submit and c_name:
                con = sqlite3.connect(DB)
                con.execute("INSERT INTO customers(name, address, email) VALUES(?,?,?)", (c_name, c_address, c_email))
                con.commit()
                con.close()
                st.success(f"'{c_name}' başarıyla eklendi!")
                st.rerun()

    with col2:
        st.markdown("### 📦 Yeni Manuel Sipariş")
        con = sqlite3.connect(DB)
        cust_rows = con.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
        con.close()
        
        cust_dict = {f"{r[0]} - {r[1]}": r[0] for r in cust_rows}
        
        with st.form("order_form"):
            selected_cust = st.selectbox("Müşteri Seçin", options=list(cust_dict.keys()) if cust_dict else ["Önce müşteri ekleyin"])
            prod_name = st.text_input("Ürün Adı / Etiket Adı")
            dimension = st.text_input("Ölçü (Örn: 8 oz, vb.)")
            material = st.selectbox("Malzeme Türü", ["Belirtilmedi", "Kraft", "Karton", "Plastik", "Diğer"])
            label_type = st.selectbox("Etiket Tipi", ["Belirtilmedi", "Kuşe", "Şeffaf", "Termal", "Diğer"])
            qty = st.number_input("Miktar (Adet)", min_value=1, value=1000)
            delivery_date = st.text_input("Teslim Tarihi (Örn: 25.09.2026)")
            
            o_submit = st.form_submit_button("Siparişi Sisteme Kaydet")
            
            if o_submit and cust_dict and prod_name:
                c_id = cust_dict[selected_cust]
                con = sqlite3.connect(DB)
                con.execute("""INSERT INTO orders(customer_id, product, dimension, material, label_type, quantity, unit_price, total_price, delivery_date)
                               VALUES(?,?,?,?,?,?,?,?,?)""",
                            (c_id, prod_name, dimension, material, label_type, qty, 0.0, 0.0, delivery_date))
                con.commit()
                con.close()
                st.success("Manuel sipariş başarıyla eklendi!")
                st.rerun()

    st.markdown("---")
    st.markdown("### ❌ Müşteri / Firma Sil (Ticari İlişkiyi Bitir)")
    
    con = sqlite3.connect(DB)
    all_customers = con.execute("SELECT id, name, address, email FROM customers ORDER BY id DESC").fetchall()
    con.close()
    
    if all_customers:
        cust_del_dict = {f"ID: #{c[0]} | {c[1]} (Adres: {c[2] if c[2] else 'Yok'})": c[0] for c in all_customers}
        
        with st.form("delete_customer_form"):
            sel_cust_to_del = st.selectbox("Silinecek Müşteriyi / Firmayı Seçin", options=list(cust_del_dict.keys()))
            target_cust_id = cust_del_dict[sel_cust_to_del]
            
            del_cust_submit = st.form_submit_button("🗑 Seçilen Müşteriyi Sistemden Sil")
            if del_cust_submit:
                con = sqlite3.connect(DB)
                con.execute("DELETE FROM customers WHERE id=?", (target_cust_id,))
                con.commit()
                con.close()
                st.success("✅ Seçilen müşteri başarıyla sistemden silindi!")
                st.rerun()
                
        st.markdown("---")
        st.markdown("### 📋 Kayıtlı Müşteriler / Firmalar Listesi")
        cust_table_html = """<div style='background: #1A1A1A; padding: 10px 15px; border-radius: 8px; font-weight: bold; color: #00B4D8; margin-bottom: 8px; border: 1px solid #333; display: grid; grid-template-columns: 0.5fr 2fr 3fr 2fr;'>
<div>ID</div>
<div>Firma Adı</div>
<div>Adres</div>
<div>Mail Adresi</div>
</div>"""
        st.markdown(cust_table_html, unsafe_allow_html=True)
        
        for c in all_customers:
            row_c_html = f"""<div style='background: #161616; padding: 10px 15px; border-radius: 6px; margin-bottom: 5px; border: 1px solid #222; display: grid; grid-template-columns: 0.5fr 2fr 3fr 2fr; font-size: 13px;'>
<div style='color: #00B4D8; font-weight: bold;'>#{c[0]}</div>
<div style='color: #FFFFFF; font-weight: 500;'>{c[1]}</div>
<div style='color: #A0A0A0;'>{c[2] if c[2] else "-"}</div>
<div style='color: #A0A0A0;'>{c[3] if c[3] else "-"}</div>
</div>"""
            st.markdown(row_c_html, unsafe_allow_html=True)
    else:
        st.info("Sistemde henüz kayıtlı müşteri bulunmuyor.")

# --- SEKME 3: DEPO VE STOK LİSTESİ ---
with tab3:
    try:
        if "del_stk" in st.query_params:
            del_id = st.query_params["del_stk"]
            con = sqlite3.connect(DB)
            con.execute("DELETE FROM stock WHERE id=?", (del_id,))
            con.commit()
            con.close()
            st.query_params.clear()
            st.success("✅ Seçilen stok başarıyla silindi!")
            st.rerun()
    except Exception:
        pass

    st.subheader("📦 Depo & Etiket Stok Listesi")
    
    with st.expander("➕ Yeni Stok Kalemi Ekle", expanded=False):
        with st.form("stock_form"):
            st_col1, st_col2, st_col3 = st.columns(3)
            with st_col1:
                s_code = st.text_input("Stok Kimliği")
                s_company = st.text_input("Firma")
                s_dim = st.text_input("Ölçü (mm)")
            with st_col2:
                s_name = st.text_input("Ürün İsmi")
                s_paper = st.text_input("Kağıt Cinsi")
                s_core = st.text_input("Kuka Çapı")
            with st_col3:
                s_roll_qty = st.text_input("Sarım Adedi")
                s_qty = st.number_input("Stok Miktarı", min_value=0, value=10000)
                s_price = st.number_input("Birim Fiyatı (€)", min_value=0.0, value=0.035, format="%.5f")
            
            s_submit = st.form_submit_button("Stoklara Ekle")
            
            if s_submit and s_name:
                con = sqlite3.connect(DB)
                con.execute("""INSERT INTO stock(stock_code, company, dimension, product_name, paper_type, core_diameter, roll_quantity, unit_price, quantity, critical_level) 
                               VALUES(?,?,?,?,?,?,?,?,?,?)""",
                            (s_code, s_company, s_dim, s_name, s_paper, s_core, s_roll_qty, s_price, s_qty, 500))
                con.commit()
                con.close()
                st.success(f"'{s_name}' stoğa eklendi!")
                st.rerun()

    with st.expander("✏️ Etiket / Stok Revize Et (Tüm Özellikleri Güncelle)", expanded=False):
        con = sqlite3.connect(DB)
        all_stocks_for_edit = con.execute("SELECT id, stock_code, company, dimension, product_name, paper_type, core_diameter, roll_quantity, unit_price, quantity FROM stock ORDER BY id DESC").fetchall()
        con.close()
        
        if all_stocks_for_edit:
            stock_dict = {f"#{st[1]} - {st[4]} ({st[2]})": st[0] for st in all_stocks_for_edit}
            
            with st.form("full_update_form"):
                sel_stock_label = st.selectbox("Revize Edilecek Ürünü Seçin", options=list(stock_dict.keys()))
                target_id = stock_dict[sel_stock_label]
                
                con = sqlite3.connect(DB)
                current_data = con.execute("SELECT stock_code, company, dimension, product_name, paper_type, core_diameter, roll_quantity, unit_price, quantity FROM stock WHERE id=?", (target_id,)).fetchone()
                con.close()
                
                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1:
                    rev_code = st.text_input("Stok Kimliği", value=current_data[0] or "")
                    rev_company = st.text_input("Firma", value=current_data[1] or "")
                    rev_dim = st.text_input("Ölçü (mm)", value=current_data[2] or "")
                with f_col2:
                    rev_name = st.text_input("Ürün İsmi", value=current_data[3] or "")
                    rev_paper = st.text_input("Kağıt Cinsi", value=current_data[4] or "")
                    rev_core = st.text_input("Kuka Çapı", value=current_data[5] or "")
                with f_col3:
                    rev_roll = st.text_input("Sarım Adedi", value=current_data[6] or "")
                    rev_price = st.number_input("Birim Fiyat (€)", min_value=0.0, value=float(current_data[7] or 0.0), format="%.5f")
                    rev_qty = st.number_input("Stok Miktarı", min_value=0, value=int(current_data[8] or 0))
                
                full_submit = st.form_submit_button("💾 Revizyonu Kaydet ve Güncelle")
                if full_submit:
                    con = sqlite3.connect(DB)
                    con.execute("""UPDATE stock SET stock_code=?, company=?, dimension=?, product_name=?, paper_type=?, core_diameter=?, roll_quantity=?, unit_price=?, quantity=? WHERE id=?""",
                                (rev_code, rev_company, rev_dim, rev_name, rev_paper, rev_core, rev_roll, rev_price, rev_qty, target_id))
                    con.commit()
                    con.close()
                    st.success("🎉 Ürün/Etiket detayları başarıyla revize edildi ve güncellendi!")
                    st.rerun()
        else:
            st.info("Güncellenecek stok bulunmuyor.")

    st.markdown("---")
    st.markdown("<p style='color: #4ECDC4; font-size: 13px; margin-top: -10px;'>💡 İpucu: Stoğu silmek için farenizi satırın üzerine getirin ve sağdan açılan sil butonuna tıklayın.</p>", unsafe_allow_html=True)
    search_query = st.text_input("🔍 Stok Ara (Kod, Firma, Ürün veya Ölçü)...", placeholder="Örn: 23913, saf holland, 50x100...")
    
    con = sqlite3.connect(DB)
    if search_query:
        stocks = con.execute("""SELECT id, stock_code, company, dimension, product_name, paper_type, core_diameter, roll_quantity, unit_price, quantity, critical_level 
                                FROM stock WHERE product_name LIKE ? OR stock_code LIKE ? OR company LIKE ? OR dimension LIKE ? ORDER BY id DESC""", 
                             (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%", f"%{search_query}%")).fetchall()
    else:
        stocks = con.execute("SELECT id, stock_code, company, dimension, product_name, paper_type, core_diameter, roll_quantity, unit_price, quantity, critical_level FROM stock ORDER BY id DESC").fetchall()
    con.close()
    
    if stocks:
        total_portfolio_value = sum((st[8] or 0.0) * (st[9] or 0) for st in stocks)
        
        summary_html = f"""<div style='background: #1A1A1A; padding: 12px 20px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #333; display: flex; justify-content: space-between; align-items: center;'>
<span style='color: #A0A0A0;'>Toplam Stok Kalemi: <b>{len(stocks)}</b></span>
<span style='color: #4ECDC4; font-size: 16px; font-weight: bold;'>Toplam Envanter Değeri: € {total_portfolio_value:,.2f}</span>
</div>"""
        st.markdown(summary_html, unsafe_allow_html=True)

        headers_html = """<div style='display: grid; grid-template-columns: 1fr 1.5fr 1fr 2fr 1.2fr 1fr 1fr 1.2fr 1.2fr 1.5fr; background: #1A1A1A; padding: 10px 15px; border-radius: 8px; font-weight: bold; color: #00B4D8; margin-bottom: 8px; border: 1px solid #333; font-size: 12px;'>
<div>Stok Kimliği</div>
<div>Firma</div>
<div>Ölçü (mm)</div>
<div>Ürün İsmi</div>
<div>Kağıt Cinsi</div>
<div>Kuka Çapı</div>
<div>Sarım Adedi</div>
<div style='text-align: right;'>Stok Miktarı</div>
<div style='text-align: right;'>Birim Fiyat (€)</div>
<div style='text-align: right;'>Stok Değeri (€)</div>
</div>"""
        st.markdown(headers_html, unsafe_allow_html=True)
        
        for st_item in stocks:
            st_id = st_item[0]
            st_code = st_item[1] if st_item[1] else "-"
            st_company = st_item[2] if st_item[2] else "-"
            st_dim = st_item[3] if st_item[3] else "-"
            st_name = st_item[4] if st_item[4] else "-"
            st_paper = st_item[5] if st_item[5] else "-"
            st_core = st_item[6] if st_item[6] else "-"
            st_roll_qty = st_item[7] if st_item[7] else "-"
            u_price = st_item[8] if st_item[8] else 0.0
            st_qty = st_item[9] if st_item[9] else 0
            st_crit = st_item[10] if st_item[10] else 500
            
            stock_value = u_price * st_qty
            is_critical = st_qty <= st_crit
            text_color = "#FF6B6B" if is_critical else "#4ECDC4"
            qty_text = f"⚠️ {st_qty:,}" if is_critical else f"{st_qty:,}".replace(",", ".")
            
            row_html = f"""<div class="stock-row-wrapper">
<div class="stock-row-grid">
<div style='color: #00B4D8; font-weight: bold;'>#{st_code}</div>
<div style='color: #E0E0E0;'>{st_company}</div>
<div style='color: #A0A0A0;'>{st_dim}</div>
<div style='color: #FFFFFF; font-weight: 500;'>{st_name}</div>
<div style='color: #A0A0A0;'>{st_paper}</div>
<div style='color: #A0A0A0;'>{st_core}</div>
<div style='color: #A0A0A0;'>{st_roll_qty}</div>
<div style='text-align: right; color: {text_color}; font-weight: bold;'>{qty_text}</div>
<div style='text-align: right; color: #E0E0E0;'>€ {u_price:.5f}</div>
<div style='text-align: right; color: #F8F9FA; font-weight: bold;'>€ {stock_value:,.2f}</div>
</div>
<div class="stock-delete-slide">
<form method="GET" action="">
<input type="hidden" name="del_stk" value="{st_id}">
<button type="submit">🗑️ Sil</button>
</form>
</div>
</div>"""
            st.markdown(row_html, unsafe_allow_html=True)
    else:
        st.info("Sistemde henüz stok kaydı bulunmuyor.")

# --- SEKME 4: ÇOKLU PDF (SİPARİŞ VE FATURA OTOMASYONU) ---
with tab4:
    st.subheader("📄 Çoklu PDF Otomasyonu (Siparişler & Faturalar)")
    
    sub_choice = st.radio("İşlem Türünü Seçin:", ["Sipariş PDF Yükle (Otomatik Aç)", "Fatura PDF Yükle (Otomatik Kapat / Teslim Et)"], horizontal=True)
    
    if "Sipariş" in sub_choice:
        st.markdown("Sipariş PDF'lerini yüklediğiniz anda siparişler sisteme işlenir ve depodan düşülür.")
        con = sqlite3.connect(DB)
        cust_rows = con.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
        con.close()
        
        if not cust_rows:
            st.warning("⚠️ Lütfen önce 'Yeni Sipariş / Müşteri' sekmesinden en az bir müşteri / firma ekleyin.")
        else:
            cust_dict = {f"{r[0]} - {r[1]}": r[0] for r in cust_rows}
            selected_cust_auto = st.selectbox("PDF Siparişlerinin Ekleneceği Müşteri / Firma:", options=list(cust_dict.keys()), key="auto_cust_select")
            
            uploaded_pdfs = st.file_uploader("Sipariş PDF Dosyalarını Seçin", type=["pdf"], accept_multiple_files=True, key="multi_pdf_order")
            
            if uploaded_pdfs:
                all_parsed_orders = []
                for uploaded_pdf in uploaded_pdfs:
                    with pdfplumber.open(uploaded_pdf) as pdf:
                        for page in pdf.pages:
                            text = page.extract_text()
                            if not text:
                                continue
                            lines = text.split('\n')
                            for i, line in enumerate(lines):
                                date_match = re.search(r'\b(0[1-9]|[12][0-9]|3[01])\.(0[1-9]|1[0-2])\.202[6-9]\b', line)
                                if date_match and "ADET" in line.upper():
                                    termin_date = date_match.group(0)
                                    code_match = re.search(r'\b(2\d{4,5})\b', line)
                                    code = code_match.group(1) if code_match else "SİPARİŞ"
                                    
                                    parts = re.split(r'\bADET\b', line, flags=re.IGNORECASE)
                                    left_part = parts[0].strip()
                                    left_words = left_part.split()
                                    raw_qty = left_words[-1] if left_words else "0"
                                    clean_qty_str = "".join(filter(str.isdigit, raw_qty))
                                    formatted_qty = f"{int(clean_qty_str):,}".replace(",", ".") if clean_qty_str else "0"
                                    urun_adi = left_part.replace(code, "", 1).replace(raw_qty, "").strip()
                                    
                                    if i + 1 < len(lines):
                                        next_line = lines[i+1].strip()
                                        if len(next_line) > 2 and len(next_line) < 50 and not "ADET" in next_line.upper():
                                            urun_adi += " " + next_line
                                            
                                    all_parsed_orders.append({
                                        "dosya": uploaded_pdf.name,
                                        "kod": code,
                                        "urun": urun_adi,
                                        "miktar_str": formatted_qty,
                                        "miktar_int": int(clean_qty_str) if clean_qty_str else 0,
                                        "termin": termin_date,
                                        "dt": datetime.strptime(termin_date, "%d.%m.%Y")
                                    })
                                    
                if all_parsed_orders:
                    sorted_all_orders = sorted(all_parsed_orders, key=lambda x: x["dt"])
                    c_id = cust_dict[selected_cust_auto]
                    con = sqlite3.connect(DB)
                    cur = con.cursor()
                    saved_count = 0
                    
                    for item in sorted_all_orders:
                        existing_check = cur.execute("SELECT id FROM orders WHERE customer_id=? AND product=? AND quantity=? AND delivery_date=?", 
                                                     (c_id, item["urun"], item["miktar_int"], item["termin"])).fetchone()
                        if not existing_check:
                            cur.execute("INSERT INTO orders(customer_id, product, dimension, material, label_type, quantity, unit_price, total_price, delivery_date, status) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                        (c_id, item["urun"], f"Kod: {item['kod']}", "PDF", "PDF", item["miktar_int"], 0.0, 0.0, item["termin"], "Aktif"))
                            saved_count += 1
                            
                            cur.execute("SELECT id, quantity FROM stock WHERE stock_code=?", (item["kod"],))
                            stk = cur.fetchone()
                            if stk:
                                cur.execute("UPDATE stock SET quantity=? WHERE id=?", ((stk[1] or 0) - item["miktar_int"], stk[0]))
                    con.commit()
                    con.close()
                    st.success(f"🎉 {saved_count} yeni sipariş fişi otomatik olarak açıldı ve arşive eklendi!")
    else:
        st.markdown("🧾 **Fatura PDF Yükle:** Fatura dosyasını yüklediğinizde, içindeki ürün kodları taranarak ilgili açık fişler otomatik olarak **'Teslim Edildi ✅'** durumuna getirilir ve arşive taşınır.")
        uploaded_invoices = st.file_uploader("Fatura PDF Dosyasını Seçin", type=["pdf"], accept_multiple_files=True, key="invoice_pdf_uploader")
        
        if uploaded_invoices:
            closed_count = 0
            con = sqlite3.connect(DB)
            cur = con.cursor()
            
            for inv in uploaded_invoices:
                with pdfplumber.open(inv) as pdf:
                    invoice_text = ""
                    for p in pdf.pages:
                        t = p.extract_text()
                        if t: invoice_text += t + "\n"
                
                found_codes = re.findall(r'\b(2\d{4,5})\b', invoice_text)
                
                for code in found_codes:
                    rows_to_close = cur.execute("SELECT id FROM orders WHERE dimension LIKE ? AND status='Aktif'", (f"%{code}%",)).fetchall()
                    for r in rows_to_close:
                        cur.execute("UPDATE orders SET status='Teslim Edildi ✅' WHERE id=?", (r[0],))
                        closed_count += 1
                        
            con.commit()
            con.close()
            
            if closed_count > 0:
                st.success(f"🎉 İşlem Başarılı! Fatura onaylandı ve eşleşen {closed_count} adet sipariş fişi teslim edildi olarak işaretlendi!")
            else:
                st.info("ℹ️ Fatura okundu ancak sistemdeki aktif sipariş kodlarıyla tam eşleşme sağlanamadı.")

# --- SEKME 5: İSTATİSTİK VE ÖZET ---
with tab5:
    st.subheader("Üretim ve İstatistik Özeti")
    con = sqlite3.connect(DB)
    total_c = con.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    total_o = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    active_p = con.execute("SELECT COUNT(*) FROM orders WHERE status='Aktif'").fetchone()[0]
    closed_p = con.execute("SELECT COUNT(*) FROM orders WHERE status!='Aktif'").fetchone()[0]
    total_stock_items = con.execute("SELECT COUNT(*) FROM stock").fetchone()[0]
    con.close()
    
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Toplam Müşteri", total_c)
    kpi2.metric("Toplam Sipariş", total_o)
    kpi3.metric("Aktif İşler", active_p)
    kpi4.metric("Teslim Edilenler", closed_p)
    kpi5.metric("Stok Kalemi", total_stock_items)
