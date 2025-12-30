import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from sqlalchemy import create_engine, text

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sistema ERP", layout="wide")

# --- CSS PARA VISUAL LIMPO ---
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 24px; }
    div.stButton > button:first-child { width: 100%; border-radius: 4px; }
    .stTextInput > div > div > input { padding: 10px; }
</style>
""", unsafe_allow_html=True)

# --- CREDENCIAIS DE ACESSO AO SISTEMA ---
USUARIO_SISTEMA = "admin"
SENHA_SISTEMA = "1234"

# --- GERENCIAMENTO DE ESTADO ---
if 'logado' not in st.session_state:
    st.session_state.logado = False

if 'carrinho' not in st.session_state:
    st.session_state.carrinho = []

# --- CONEXÃO COM BANCO DE DADOS (POSTGRESQL) ---
# Usa as configurações definidas em .streamlit/secrets.toml na nuvem
def get_connection():
    # Monta a string de conexão baseada nos Secrets do Streamlit
    try:
        db_conf = st.secrets["connections"]["postgresql"]
        db_url = f"postgresql://{db_conf['username']}:{db_conf['password']}@{db_conf['host']}:{db_conf['port']}/{db_conf['database']}"
        engine = create_engine(db_url)
        return engine
    except Exception as e:
        st.error(f"Erro ao conectar no banco. Verifique as Secrets. Detalhe: {e}")
        return None

def run_query(query, params=None, fetch=False):
    engine = get_connection()
    if not engine:
        return None
    
    with engine.connect() as conn:
        try:
            # PostgreSQL requer parâmetros como dicionário ou tupla, mas SQLAlchemy usa :param
            # Para facilitar a migração do SQLite, vamos usar execução direta do SQLAlchemy
            result = conn.execute(text(query), params if params else {})
            
            if fetch:
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
                return df
            
            conn.commit()
            return True
        except Exception as e:
            st.error(f"Erro na Query: {e}")
            return None

def init_db():
    # Cria as tabelas se não existirem (Sintaxe PostgreSQL)
    queries = [
        '''CREATE TABLE IF NOT EXISTS produtos (
            id SERIAL PRIMARY KEY, 
            nome TEXT, 
            categoria TEXT, 
            tamanho TEXT,
            preco_custo REAL, 
            preco_venda REAL, 
            estoque INTEGER
        )''',
        '''CREATE TABLE IF NOT EXISTS pedidos (
            id SERIAL PRIMARY KEY, 
            data TEXT, 
            cliente TEXT,
            canal TEXT,
            total_venda REAL, 
            lucro_total REAL,
            status TEXT,
            forma_pagamento TEXT
        )''',
        '''CREATE TABLE IF NOT EXISTS itens_pedido (
            id SERIAL PRIMARY KEY, 
            pedido_id INTEGER REFERENCES pedidos(id), 
            produto_id INTEGER,
            produto_nome TEXT,
            tamanho TEXT,
            quantidade INTEGER, 
            preco_unitario REAL,
            preco_custo REAL
        )''',
        '''CREATE TABLE IF NOT EXISTS transacoes (
            id SERIAL PRIMARY KEY, 
            data TEXT, 
            tipo TEXT, 
            descricao TEXT, 
            valor REAL
        )'''
    ]
    
    engine = get_connection()
    if engine:
        with engine.connect() as conn:
            for q in queries:
                conn.execute(text(q))
            conn.commit()

# --- MÓDULOS DO SISTEMA ---

def verificar_login():
    st.title("🔒 Acesso Restrito")
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        with st.form("login"):
            usr = st.text_input("Usuário")
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                if usr == USUARIO_SISTEMA and pwd == SENHA_SISTEMA:
                    st.session_state.logado = True
                    st.rerun()
                else:
                    st.error("Dados incorretos.")

def pagina_dashboard():
    st.header("Painel Gerencial")
    
    # Buscas
    df_pedidos = run_query("SELECT * FROM pedidos", fetch=True)
    df_prod = run_query("SELECT * FROM produtos", fetch=True)
    df_trans = run_query("SELECT * FROM transacoes", fetch=True)
    
    saldo = df_trans['valor'].sum() if not df_trans.empty else 0.0
    fat = df_pedidos['total_venda'].sum() if not df_pedidos.empty else 0.0
    lucro = df_pedidos['lucro_total'].sum() if not df_pedidos.empty else 0.0
    est = df_prod['estoque'].sum() if not df_prod.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Saldo Caixa", f"R$ {saldo:,.2f}")
    c2.metric("Faturamento", f"R$ {fat:,.2f}")
    c3.metric("Lucro", f"R$ {lucro:,.2f}")
    c4.metric("Estoque (Peças)", est)
    
    st.markdown("---")
    
    c_g1, c_g2 = st.columns(2)
    with c_g1:
        st.subheader("Vendas por Canal")
        if not df_pedidos.empty:
            fig = px.pie(df_pedidos, values='total_venda', names='canal', hole=0.5)
            st.plotly_chart(fig, use_container_width=True)
    
    with c_g2:
        st.subheader("Top Produtos")
        df_itens = run_query("SELECT produto_nome, SUM(quantidade) as qtd FROM itens_pedido GROUP BY produto_nome", fetch=True)
        if not df_itens.empty:
            df_itens['qtd'] = pd.to_numeric(df_itens['qtd'])
            fig2 = px.bar(df_itens, x='produto_nome', y='qtd')
            st.plotly_chart(fig2, use_container_width=True)

def pagina_estoque():
    st.header("Controle de Estoque")
    
    with st.expander("Cadastrar Nova Grade"):
        with st.form("novo_prod", clear_on_submit=True):
            st.subheader("Dados")
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome")
            cat = c2.selectbox("Categoria", ["Roupas", "Acessórios", "Outros"])
            c3, c4 = st.columns(2)
            custo = c3.number_input("Custo", 0.0, step=0.01, format="%.2f")
            venda = c4.number_input("Venda", 0.0, step=0.01, format="%.2f")
            
            st.markdown("### Grade")
            tams = ["PP", "P", "M", "G", "GG", "XG", "Único"]
            qtds = {}
            cols = st.columns(7)
            for i, t in enumerate(tams):
                with cols[i]:
                    qtds[t] = st.number_input(f"{t}", min_value=0, step=1)
            
            if st.form_submit_button("Salvar"):
                if nome and venda > 0:
                    for t, q in qtds.items():
                        if q > 0:
                            # Note o uso de :param no SQLAlchemy
                            run_query(
                                "INSERT INTO produtos (nome, categoria, tamanho, preco_custo, preco_venda, estoque) VALUES (:nome, :cat, :tam, :custo, :venda, :est)",
                                {"nome": nome, "cat": cat, "tam": t, "custo": custo, "venda": venda, "est": q}
                            )
                    st.success("Salvo!")
                    st.rerun()
                else:
                    st.warning("Preencha nome e valor.")
    
    st.markdown("---")
    df = run_query("SELECT * FROM produtos ORDER BY id ASC", fetch=True)
    
    if not df.empty:
        # Agrupamento Visual
        df_view = df.groupby(['nome', 'categoria', 'preco_venda']).apply(
            lambda x: pd.Series({
                'Total': x['estoque'].sum(),
                'Grade': ' | '.join([f"{row['tamanho']}: {row['estoque']}" for i, row in x.iterrows()])
            })
        ).reset_index()
        
        st.dataframe(df_view, use_container_width=True)
        
        c_sel, c_act = st.columns([2, 1])
        with c_sel:
            opts = [f"ID {r.id} | {r.nome} ({r.tamanho})" for i, r in df.iterrows()]
            sel = st.selectbox("Editar Item", opts)
            id_sel = int(sel.split("|")[0].replace("ID ", "").strip())
        
        with c_act:
            novo_est = st.number_input("Nova Qtd", min_value=0)
            if st.button("Atualizar"):
                run_query("UPDATE produtos SET estoque = :est WHERE id = :id", {"est": novo_est, "id": id_sel})
                st.success("Atualizado!")
                st.rerun()

def pagina_pdv():
    st.header("Frente de Caixa (PDV)")
    df_prod = run_query("SELECT * FROM produtos WHERE estoque > 0", fetch=True)
    
    if df_prod.empty:
        st.warning("Sem estoque.")
        return

    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Seleção")
        df_prod['display'] = df_prod.apply(lambda x: f"{x['nome']} ({x['tamanho']}) | R$ {x['preco_venda']:.2f}", axis=1)
        sel = st.selectbox("Produto", df_prod['display'].tolist())
        data = df_prod[df_prod['display'] == sel].iloc[0]
        
        st.info(f"Estoque: {data['estoque']}")
        qtd = st.number_input("Qtd", 1, int(data['estoque']))
        
        if st.button("Adicionar"):
            st.session_state.carrinho.append({
                "id": int(data['id']),
                "nome": data['nome'],
                "tam": data['tamanho'],
                "qtd": qtd,
                "unit": float(data['preco_venda']),
                "custo": float(data['preco_custo']),
                "total": qtd * float(data['preco_venda'])
            })
            st.success("Adicionado.")

    with c2:
        st.subheader("Carrinho")
        if st.session_state.carrinho:
            df_c = pd.DataFrame(st.session_state.carrinho)
            st.dataframe(df_c[['nome', 'tam', 'qtd', 'total']], hide_index=True)
            
            total = df_c['total'].sum()
            st.markdown(f"**Total: R$ {total:.2f}**")
            
            cli = st.text_input("Cliente", "Consumidor")
            pgto = st.selectbox("Pagamento", ["Pix", "Dinheiro", "Cartão"])
            canal = st.selectbox("Canal", ["Loja", "Online", "WhatsApp"])
            dt = st.date_input("Data", datetime.now())
            
            if st.button("FINALIZAR", type="primary"):
                custo_tot = sum(i['qtd'] * i['custo'] for i in st.session_state.carrinho)
                lucro = total - custo_tot
                
                # Inserir Pedido
                run_query(
                    """INSERT INTO pedidos (data, cliente, canal, total_venda, lucro_total, status, forma_pagamento) 
                       VALUES (:dt, :cli, :canal, :tot, :lucro, 'Concluído', :pgto)""",
                    {"dt": dt, "cli": cli, "canal": canal, "tot": total, "lucro": lucro, "pgto": pgto}
                )
                
                # Pegar ID do ultimo pedido (Postgres way)
                # Como SQLAlchemy executa e commita, precisamos fazer uma query de busca logo em seguida ou usar RETURNING
                # Pela simplicidade, vamos buscar o último ID inserido
                df_id = run_query("SELECT id FROM pedidos ORDER BY id DESC LIMIT 1", fetch=True)
                id_ped = int(df_id.iloc[0,0])
                
                # Itens e Baixa
                for i in st.session_state.carrinho:
                    run_query(
                        """INSERT INTO itens_pedido (pedido_id, produto_id, produto_nome, tamanho, quantidade, preco_unitario, preco_custo)
                           VALUES (:pid, :prod_id, :nome, :tam, :qtd, :unit, :custo)""",
                        {"pid": id_ped, "prod_id": i['id'], "nome": i['nome'], "tam": i['tam'], "qtd": i['qtd'], "unit": i['unit'], "custo": i['custo']}
                    )
                    run_query("UPDATE produtos SET estoque = estoque - :qtd WHERE id = :id", {"qtd": i['qtd'], "id": i['id']})
                
                # Financeiro
                run_query(
                    "INSERT INTO transacoes (data, tipo, descricao, valor) VALUES (:dt, 'Venda', :desc, :val)",
                    {"dt": dt, "desc": f"Venda #{id_ped} - {cli}", "val": total}
                )
                
                st.session_state.carrinho = []
                st.success("Venda Realizada!")
                st.rerun()
                
            if st.button("Limpar"):
                st.session_state.carrinho = []
                st.rerun()

def pagina_pedidos():
    st.header("Histórico")
    df = run_query("SELECT * FROM pedidos ORDER BY id DESC", fetch=True)
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        
        c_id, c_btn = st.columns([2,1])
        with c_id:
            sel_id = st.selectbox("ID para Cancelar", df['id'].tolist())
        with c_btn:
            st.write("")
            st.write("")
            if st.button("CANCELAR VENDA"):
                # Estorno Estoque
                itens = run_query(f"SELECT * FROM itens_pedido WHERE pedido_id = {sel_id}", fetch=True)
                for index, row in itens.iterrows():
                    run_query(
                        "UPDATE produtos SET estoque = estoque + :qtd WHERE id = :pid",
                        {"qtd": row['quantidade'], "pid": row['produto_id']}
                    )
                
                # Remover Financeiro, Itens e Pedido
                run_query(f"DELETE FROM transacoes WHERE descricao LIKE 'Venda #{sel_id}%'")
                run_query(f"DELETE FROM itens_pedido WHERE pedido_id = {sel_id}")
                run_query(f"DELETE FROM pedidos WHERE id = {sel_id}")
                
                st.success("Cancelado!")
                st.rerun()
    else:
        st.info("Sem vendas.")

def pagina_financeiro():
    st.header("Financeiro")
    df = run_query("SELECT * FROM transacoes ORDER BY id DESC", fetch=True)
    saldo = df['valor'].sum() if not df.empty else 0.0
    st.metric("Saldo", f"R$ {saldo:,.2f}")
    
    c1, c2 = st.columns(2)
    with c1:
        with st.form("in"):
            v = st.number_input("Entrada", 0.01)
            d = st.text_input("Motivo")
            if st.form_submit_button("Lançar"):
                run_query(
                    "INSERT INTO transacoes (data, tipo, descricao, valor) VALUES (:dt, 'Entrada', :d, :v)",
                    {"dt": datetime.now(), "d": d, "v": v}
                )
                st.rerun()
    with c2:
        with st.form("out"):
            v = st.number_input("Saída", 0.01)
            d = st.text_input("Motivo")
            if st.form_submit_button("Lançar"):
                run_query(
                    "INSERT INTO transacoes (data, tipo, descricao, valor) VALUES (:dt, 'Saída', :d, :v)",
                    {"dt": datetime.now(), "d": d, "v": -v}
                )
                st.rerun()
    
    st.dataframe(df, use_container_width=True)

# --- APP ---
def main():
    if not st.session_state.logado:
        verificar_login()
    else:
        init_db() # Garante tabelas no Postgres
        st.sidebar.title("ERP System")
        if st.sidebar.button("Sair"):
            st.session_state.logado = False
            st.rerun()
            
        menu = {
            "Dashboard": pagina_dashboard,
            "Estoque": pagina_estoque,
            "Vendas (PDV)": pagina_pdv,
            "Pedidos": pagina_pedidos,
            "Financeiro": pagina_financeiro
        }
        escolha = st.sidebar.radio("Menu", list(menu.keys()))
        menu[escolha]()

if __name__ == "__main__":
    main()