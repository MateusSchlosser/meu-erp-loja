import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

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

# --- CREDENCIAIS DE ACESSO ---
# Você pode alterar seu login e senha aqui
USUARIO_SISTEMA = "MateusDeLorenzi"
SENHA_SISTEMA = "Ms100468$"

# --- GERENCIAMENTO DE ESTADO E LOGIN ---
if 'logado' not in st.session_state:
    st.session_state.logado = False

if 'carrinho' not in st.session_state:
    st.session_state.carrinho = []

# --- FUNÇÃO DE LOGIN ---
def verificar_login():
    st.title("Acesso Restrito")
    st.write("Por favor, faça login para acessar o sistema ERP.")
    
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        with st.form("login_form"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar no Sistema")
            
            if submit:
                if usuario == USUARIO_SISTEMA and senha == SENHA_SISTEMA:
                    st.session_state.logado = True
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

# --- BANCO DE DADOS ---
DB_NAME = "erp_database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Produtos
    c.execute('''CREATE TABLE IF NOT EXISTS produtos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  nome TEXT, 
                  categoria TEXT, 
                  tamanho TEXT,
                  preco_custo REAL, 
                  preco_venda REAL, 
                  estoque INTEGER)''')
    
    # Pedidos
    c.execute('''CREATE TABLE IF NOT EXISTS pedidos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  data TEXT, 
                  cliente TEXT,
                  canal TEXT,
                  total_venda REAL, 
                  lucro_total REAL,
                  status TEXT,
                  forma_pagamento TEXT)''')
    
    # Itens do Pedido
    c.execute('''CREATE TABLE IF NOT EXISTS itens_pedido
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  pedido_id INTEGER, 
                  produto_id INTEGER,
                  produto_nome TEXT,
                  tamanho TEXT,
                  quantidade INTEGER, 
                  preco_unitario REAL,
                  preco_custo REAL,
                  FOREIGN KEY(pedido_id) REFERENCES pedidos(id))''')

    # Financeiro
    c.execute('''CREATE TABLE IF NOT EXISTS transacoes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  data TEXT, 
                  tipo TEXT, 
                  descricao TEXT, 
                  valor REAL)''')
    
    conn.commit()
    conn.close()

def run_query(query, params=(), fetch=False):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute(query, params)
        if fetch:
            data = c.fetchall()
            columns = [description[0] for description in c.description]
            df = pd.DataFrame(data, columns=columns)
            return df
        conn.commit()
    except Exception as e:
        st.error(f"Erro no Banco de Dados: {e}")
    finally:
        conn.close()

# --- MÓDULOS ---

def pagina_dashboard():
    st.header("Painel Gerencial")
    
    df_pedidos = run_query("SELECT * FROM pedidos", fetch=True)
    df_produtos = run_query("SELECT * FROM produtos", fetch=True)
    df_transacoes = run_query("SELECT * FROM transacoes", fetch=True)
    
    saldo_atual = df_transacoes['valor'].sum() if not df_transacoes.empty else 0.0
    faturamento = df_pedidos['total_venda'].sum() if not df_pedidos.empty else 0.0
    lucro = df_pedidos['lucro_total'].sum() if not df_pedidos.empty else 0.0
    estoque_qtd = df_produtos['estoque'].sum() if not df_produtos.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Saldo Caixa", f"R$ {saldo_atual:,.2f}")
    col2.metric("Faturamento", f"R$ {faturamento:,.2f}")
    col3.metric("Lucro Líquido", f"R$ {lucro:,.2f}")
    col4.metric("Peças Estoque", estoque_qtd)

    st.markdown("---")

    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.subheader("Vendas por Canal")
        if not df_pedidos.empty:
            df_canal = df_pedidos.groupby('canal')['total_venda'].sum().reset_index()
            fig = px.pie(df_canal, values='total_venda', names='canal', hole=0.5)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados.")

    with col_g2:
        st.subheader("Top Produtos")
        df_itens = run_query("SELECT produto_nome, SUM(quantidade) as qtd FROM itens_pedido GROUP BY produto_nome", fetch=True)
        if not df_itens.empty:
            fig2 = px.bar(df_itens, x='produto_nome', y='qtd')
            st.plotly_chart(fig2, use_container_width=True)

def pagina_estoque():
    st.header("Controle de Estoque")
    
    with st.expander("Cadastrar Nova Grade", expanded=False):
        with st.form("form_add_prod", clear_on_submit=True):
            st.subheader("Dados do Produto")
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome (ex: Camiseta)")
            cat = c2.selectbox("Categoria", ["Roupas", "Acessórios", "Outros"])
            
            c3, c4 = st.columns(2)
            custo = c3.number_input("Custo (R$)", min_value=0.00, step=0.01, format="%.2f")
            venda = c4.number_input("Venda (R$)", min_value=0.00, step=0.01, format="%.2f")
            
            st.markdown("### Grade")
            tamanhos = ["PP", "P", "M", "G", "GG", "XG", "Único"]
            qtds = {}
            cols = st.columns(7)
            for i, t in enumerate(tamanhos):
                with cols[i]:
                    qtds[t] = st.number_input(f"{t}", min_value=0, step=1)
            
            if st.form_submit_button("Salvar Grade"):
                if nome and venda > 0:
                    for t, q in qtds.items():
                        if q > 0:
                            run_query("INSERT INTO produtos (nome, categoria, tamanho, preco_custo, preco_venda, estoque) VALUES (?,?,?,?,?,?)",
                                      (nome, cat, t, custo, venda, q))
                    st.success("Cadastrado!")
                    st.rerun()
                else:
                    st.error("Preencha nome e valor de venda.")

    st.markdown("---")
    
    df = run_query("SELECT * FROM produtos", fetch=True)
    if not df.empty:
        # Agrupamento Visual
        df_view = df.groupby(['nome', 'categoria', 'preco_venda']).apply(
            lambda x: pd.Series({
                'Total': x['estoque'].sum(),
                'Grade': ' | '.join([f"{row['tamanho']}: {row['estoque']}" for i, row in x.iterrows()])
            })
        ).reset_index()
        
        st.dataframe(df_view, use_container_width=True, column_config={"preco_venda": st.column_config.NumberColumn("Preço", format="R$ %.2f")})
        
        # Edição
        st.markdown("### Ajuste Individual")
        c_sel, c_act = st.columns([2, 1])
        with c_sel:
            opts = [f"ID {r.id} | {r.nome} ({r.tamanho})" for i, r in df.iterrows()]
            sel = st.selectbox("Item", opts)
            id_sel = int(sel.split("|")[0].replace("ID ", "").strip())
        
        with c_act:
            new_stock = st.number_input("Nova Qtd", min_value=0)
            if st.button("Atualizar Estoque"):
                run_query("UPDATE produtos SET estoque = ? WHERE id = ?", (new_stock, id_sel))
                st.success("Atualizado!")
                st.rerun()

def pagina_pdv():
    st.header("Frente de Caixa (PDV)")
    
    df_prod = run_query("SELECT * FROM produtos WHERE estoque > 0", fetch=True)
    if df_prod.empty:
        st.warning("Sem estoque.")
        return

    col_prod, col_cart = st.columns([2, 1])
    
    with col_prod:
        st.subheader("1. Adicionar Itens")
        df_prod['display'] = df_prod.apply(lambda x: f"{x['nome']} ({x['tamanho']}) | R$ {x['preco_venda']:.2f}", axis=1)
        sel_prod = st.selectbox("Buscar Produto", df_prod['display'].tolist())
        data_prod = df_prod[df_prod['display'] == sel_prod].iloc[0]
        
        st.caption(f"Estoque Disponível: {data_prod['estoque']}")
        qtd = st.number_input("Quantidade", 1, int(data_prod['estoque']), 1)
        
        if st.button("Adicionar ao Carrinho"):
            st.session_state.carrinho.append({
                "id": int(data_prod['id']),
                "nome": data_prod['nome'],
                "tamanho": data_prod['tamanho'],
                "qtd": qtd,
                "unit": float(data_prod['preco_venda']),
                "custo": float(data_prod['preco_custo']),
                "total": qtd * float(data_prod['preco_venda'])
            })
            st.success("Item adicionado.")

    with col_cart:
        st.subheader("2. Fechamento")
        if st.session_state.carrinho:
            df_c = pd.DataFrame(st.session_state.carrinho)
            st.dataframe(df_c[['nome', 'tamanho', 'qtd', 'total']], hide_index=True)
            
            total_venda = df_c['total'].sum()
            st.markdown(f"### Total: R$ {total_venda:.2f}")
            st.markdown("---")
            
            c_date, c_pgto = st.columns(2)
            data_venda = c_date.date_input("Data da Venda", datetime.now())
            pgto = c_pgto.selectbox("Pagamento", ["Pix", "Dinheiro", "Crédito", "Débito"])
            
            cliente = st.text_input("Nome Cliente", "Consumidor Final")
            canal = st.selectbox("Canal de Venda", ["Presencial (Loja)", "Site / Instagram", "WhatsApp"])
            
            if st.button("CONCLUIR VENDA", type="primary"):
                custo_tot = sum(i['qtd'] * i['custo'] for i in st.session_state.carrinho)
                lucro = total_venda - custo_tot
                data_str = data_venda.strftime("%Y-%m-%d")
                
                run_query("INSERT INTO pedidos (data, cliente, canal, total_venda, lucro_total, status, forma_pagamento) VALUES (?,?,?,?,?,?,?)",
                          (data_str, cliente, canal, total_venda, lucro, "Concluído", pgto))
                id_ped = run_query("SELECT seq FROM sqlite_sequence WHERE name='pedidos'", fetch=True).iloc[0,0]
                
                for i in st.session_state.carrinho:
                    run_query("INSERT INTO itens_pedido (pedido_id, produto_id, produto_nome, tamanho, quantidade, preco_unitario, preco_custo) VALUES (?,?,?,?,?,?,?)",
                              (id_ped, i['id'], i['nome'], i['tamanho'], i['qtd'], i['unit'], i['custo']))
                    run_query("UPDATE produtos SET estoque = estoque - ? WHERE id = ?", (i['qtd'], i['id']))
                
                run_query("INSERT INTO transacoes (data, tipo, descricao, valor) VALUES (?,?,?,?)",
                          (data_str, "Venda", f"Venda #{id_ped} - {cliente}", total_venda))
                
                st.session_state.carrinho = []
                st.success("Venda registrada!")
                st.rerun()
                
            if st.button("Limpar Tudo"):
                st.session_state.carrinho = []
                st.rerun()

def pagina_pedidos():
    st.header("Gerenciar Vendas")
    
    df = run_query("SELECT * FROM pedidos ORDER BY id DESC", fetch=True)
    
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        
        st.markdown("---")
        st.subheader("Cancelamento / Estorno")
        
        col_canc_id, col_canc_btn = st.columns([2, 1])
        with col_canc_id:
            lista_ids = df['id'].tolist()
            id_cancelar = st.selectbox("Selecione o ID da Venda para Cancelar", lista_ids)
        
        with col_canc_btn:
            st.write("") 
            st.write("") 
            if st.button("ESTORNAR VENDA SELECIONADA"):
                itens = run_query("SELECT * FROM itens_pedido WHERE pedido_id = ?", (id_cancelar,), fetch=True)
                for index, item in itens.iterrows():
                    run_query("UPDATE produtos SET estoque = estoque + ? WHERE id = ?", (item['quantidade'], item['produto_id']))
                
                run_query("DELETE FROM transacoes WHERE descricao LIKE ?", (f"Venda #{id_cancelar}%",))
                run_query("DELETE FROM itens_pedido WHERE pedido_id = ?", (id_cancelar,))
                run_query("DELETE FROM pedidos WHERE id = ?", (id_cancelar,))
                
                st.success(f"Venda #{id_cancelar} estornada! Itens devolvidos ao estoque e valor removido do caixa.")
                st.rerun()

    else:
        st.info("Nenhuma venda encontrada.")

def pagina_financeiro():
    st.header("Fluxo de Caixa")
    
    df = run_query("SELECT * FROM transacoes ORDER BY id DESC", fetch=True)
    saldo = df['valor'].sum() if not df.empty else 0.0
    
    st.metric("Saldo Disponível", f"R$ {saldo:,.2f}")
    
    c1, c2 = st.columns(2)
    with c1:
        with st.form("in"):
            v = st.number_input("Entrada (R$)", min_value=0.01, format="%.2f")
            d = st.text_input("Motivo")
            if st.form_submit_button("Lançar Entrada"):
                run_query("INSERT INTO transacoes (data, tipo, descricao, valor) VALUES (?,?,?,?)",
                          (datetime.now().strftime("%Y-%m-%d"), "Entrada", d, v))
                st.rerun()
    with c2:
        with st.form("out"):
            v = st.number_input("Saída (R$)", min_value=0.01, format="%.2f")
            d = st.text_input("Motivo")
            if st.form_submit_button("Lançar Saída"):
                run_query("INSERT INTO transacoes (data, tipo, descricao, valor) VALUES (?,?,?,?)",
                          (datetime.now().strftime("%Y-%m-%d"), "Saída", d, -v))
                st.rerun()
    
    st.markdown("---")
    if not df.empty:
        st.dataframe(df, use_container_width=True)

# --- APP PRINCIPAL ---
def main():
    init_db()
    
    # VERIFICAÇÃO DE LOGIN
    if not st.session_state.logado:
        verificar_login()
    else:
        st.sidebar.title("ERP System")
        if st.sidebar.button("Sair / Logout"):
            st.session_state.logado = False
            st.rerun()
            
        menu = {
            "Dashboard": pagina_dashboard,
            "Estoque": pagina_estoque,
            "Vendas (PDV)": pagina_pdv,
            "Pedidos": pagina_pedidos,
            "Financeiro": pagina_financeiro
        }
        
        escolha = st.sidebar.radio("Navegação", list(menu.keys()))
        menu[escolha]()

if __name__ == "__main__":
    main()