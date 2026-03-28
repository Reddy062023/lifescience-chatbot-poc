import streamlit as st
import snowflake.connector
import pandas as pd
import numpy as np
import os, io, base64, urllib.parse
from dotenv import load_dotenv
from datetime import date, datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors as rl_colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.enums import TA_CENTER, TA_LEFT

load_dotenv()

# ── Page config ────────────────────────────────────────────────
st.set_page_config(page_title='Life Science Chatbot', page_icon='🧬', layout='wide')
st.title('🧬 Life Science Data Chatbot')
st.caption(f"Powered by Snowflake Cortex  |  {date.today().strftime('%B %d, %Y')}")
st.divider()

sns.set_theme(style="whitegrid")
COLORS = ["#2E75B6","#0F6E56","#BA7517","#534AB7","#A32D2D",
          "#1B3A6B","#3B6D11","#D85A30","#1D9E75","#185FA5"]

# ── Schema ─────────────────────────────────────────────────────
SCHEMA = '''You are a Snowflake SQL expert for a Life Science medical device company.
Today: {today}. Database: CHATBOT_POC_DB  Schema: SALES_DATA

TABLE 1: REVENUE_TBL(REVENUE_ID, DATE, DIVISION, PRODUCT, REVENUE_USD, REGION)
  Divisions: Urology, Cardiology, Oncology, Orthopedics, Neurology

TABLE 2: SALES_TBL(ORDER_ID, ORDER_DATE, SALES_REP, DIVISION, PRODUCT,
                   QUANTITY, UNIT_PRICE, TOTAL_AMOUNT, CUSTOMER, STATUS)
  Reps: Sarah Johnson, Michael Chen, Lisa Patel, James Williams, Amanda Torres,
        Robert Kim, Emily Davis, Marcus Brown, Jennifer Lee, David Martinez

TABLE 3: INVOICE_TBL(INVOICE_ID, INVOICE_DATE, DUE_DATE, CUSTOMER,
                     DIVISION, SALES_REP, AMOUNT, STATUS)
  Status values: Paid, Pending, Overdue

DATE FUNCTIONS:
  Yesterday:    DATEADD('day',-1,CURRENT_DATE())
  This month:   DATE_TRUNC('month',CURRENT_DATE())
  Last month:   DATE_TRUNC('month',DATEADD('month',-1,CURRENT_DATE()))
  This quarter: DATE_TRUNC('quarter',CURRENT_DATE())
  Year to date: DATE_TRUNC('year',CURRENT_DATE())
  Last 7 days:  DATEADD('day',-7,CURRENT_DATE())
  Last 30 days: DATEADD('day',-30,CURRENT_DATE())

RULES:
  1. Return ONLY the SQL — no explanation, no markdown, no backticks
  2. Qualify: CHATBOT_POC_DB.SALES_DATA.TABLE_NAME
  3. End with semicolon. Limit 50 rows.

EXAMPLES:
Q: Total revenue yesterday?
A: SELECT SUM(REVENUE_USD) AS TOTAL_REVENUE FROM CHATBOT_POC_DB.SALES_DATA.REVENUE_TBL WHERE DATE=DATEADD('day',-1,CURRENT_DATE());
Q: Compare revenue by division this month?
A: SELECT DIVISION, SUM(REVENUE_USD) AS TOTAL_REVENUE FROM CHATBOT_POC_DB.SALES_DATA.REVENUE_TBL WHERE DATE>=DATE_TRUNC('month',CURRENT_DATE()) GROUP BY DIVISION ORDER BY TOTAL_REVENUE DESC;
Q: Revenue trend last 30 days?
A: SELECT DATE, SUM(REVENUE_USD) AS DAILY_REVENUE FROM CHATBOT_POC_DB.SALES_DATA.REVENUE_TBL WHERE DATE>=DATEADD('day',-30,CURRENT_DATE()) GROUP BY DATE ORDER BY DATE;
Q: Top 5 reps by revenue this month?
A: SELECT SALES_REP, SUM(TOTAL_AMOUNT) AS TOTAL_SALES FROM CHATBOT_POC_DB.SALES_DATA.SALES_TBL WHERE ORDER_DATE>=DATE_TRUNC('month',CURRENT_DATE()) GROUP BY SALES_REP ORDER BY TOTAL_SALES DESC LIMIT 5;
Q: Invoice status breakdown?
A: SELECT STATUS, COUNT(*) AS COUNT FROM CHATBOT_POC_DB.SALES_DATA.INVOICE_TBL GROUP BY STATUS ORDER BY COUNT DESC;
Q: Orders by Sarah Johnson this month?
A: SELECT ORDER_DATE, PRODUCT, QUANTITY, TOTAL_AMOUNT, CUSTOMER FROM CHATBOT_POC_DB.SALES_DATA.SALES_TBL WHERE SALES_REP='Sarah Johnson' AND ORDER_DATE>=DATE_TRUNC('month',CURRENT_DATE());
Q: How many invoices are overdue?
A: SELECT COUNT(*) AS OVERDUE_COUNT FROM CHATBOT_POC_DB.SALES_DATA.INVOICE_TBL WHERE STATUS='Overdue';
Q: Urology revenue this month?
A: SELECT SUM(REVENUE_USD) AS UROLOGY_REVENUE FROM CHATBOT_POC_DB.SALES_DATA.REVENUE_TBL WHERE DIVISION='Urology' AND DATE>=DATE_TRUNC('month',CURRENT_DATE());
'''

# ── Snowflake ──────────────────────────────────────────────────
def get_conn():
    return snowflake.connector.connect(
        account=os.getenv('SNOWFLAKE_ACCOUNT'),   user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),  database=os.getenv('SNOWFLAKE_DATABASE'),
        schema=os.getenv('SNOWFLAKE_SCHEMA'),      warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        role=os.getenv('SNOWFLAKE_ROLE'),
    )

def ask_cortex(question):
    ctx    = SCHEMA.replace('{today}', date.today().isoformat())
    prompt = f"{ctx}\n\nQ: {question}\nA:"
    esc    = prompt.replace("'", "\\'")
    sql    = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3-70b','{esc}') AS Q;"
    try:
        conn=get_conn(); cur=conn.cursor()
        cur.execute(sql); row=cur.fetchone()
        cur.close(); conn.close()
        if row and row[0]:
            r=row[0].strip().replace('```sql','').replace('```','').strip()
            return r if len(r)>10 else 'ERROR: Empty response. Try again.'
        return 'ERROR: No response from Cortex.'
    except Exception as e: return f'ERROR: {str(e)}'

def run_query(sql):
    if sql.startswith('ERROR'): return None, sql
    try:
        conn=get_conn(); cur=conn.cursor()
        cur.execute(sql); rows=cur.fetchall()
        cols=[d[0] for d in cur.description]
        cur.close(); conn.close()
        return pd.DataFrame(rows, columns=cols), None
    except Exception as e: return None, str(e)

# ══════════════════════════════════════════════════════════════
# EXPORT FUNCTIONS
# ══════════════════════════════════════════════════════════════

def to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def to_excel(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        df.to_excel(w, index=False, sheet_name='Results')
        ws = w.sheets['Results']
        for col in ws.columns:
            w = max(len(str(c.value or '')) for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(w+4, 40)
    return buf.getvalue()

def fig_to_png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    buf.seek(0)
    return buf.getvalue()

def metric_to_png(label, value):
    fig, ax = plt.subplots(figsize=(5, 2.5))
    ax.axis('off')
    fig.patch.set_facecolor('#F1EFE8')
    ax.text(0.5, 0.75, label,  ha='center', fontsize=13, color='#5F5E5A', transform=ax.transAxes)
    ax.text(0.5, 0.42, value,  ha='center', fontsize=30, fontweight='bold', color='#1B3A6B', transform=ax.transAxes)
    ax.text(0.5, 0.10, f'Life Science Chatbot  |  {date.today().strftime("%B %d, %Y")}',
            ha='center', fontsize=8, color='#AAAAAA', transform=ax.transAxes)
    plt.tight_layout()
    png = fig_to_png(fig)
    plt.close(fig)
    return png

def to_pdf(question, df, fig=None, metric_label=None, metric_value=None):
    """Generate a professional PDF report with chart (if any) + data table."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            leftMargin=1.5*cm, rightMargin=1.5*cm)
    styles = getSampleStyleSheet()
    navy   = rl_colors.HexColor('#1B3A6B')
    teal   = rl_colors.HexColor('#0F6E56')
    lgray  = rl_colors.HexColor('#F1EFE8')
    blue   = rl_colors.HexColor('#2E75B6')
    white  = rl_colors.white

    title_style = ParagraphStyle('title', fontSize=18, textColor=navy,
                                 fontName='Helvetica-Bold', alignment=TA_LEFT, spaceAfter=4)
    sub_style   = ParagraphStyle('sub',   fontSize=10, textColor=rl_colors.HexColor('#5F5E5A'),
                                 fontName='Helvetica', alignment=TA_LEFT, spaceAfter=2)
    q_style     = ParagraphStyle('q',     fontSize=11, textColor=teal,
                                 fontName='Helvetica-Bold', alignment=TA_LEFT,
                                 spaceBefore=8, spaceAfter=8)

    story = []

    # ── Header ─────────────────────────────────────────────────
    story.append(Paragraph('🧬 Life Science Data Chatbot', title_style))
    story.append(Paragraph(f'Report generated: {datetime.now().strftime("%B %d, %Y  %H:%M")}', sub_style))
    story.append(Paragraph('Powered by Snowflake Cortex', sub_style))
    story.append(Spacer(1, 0.4*cm))

    # Divider line
    from reportlab.platypus import HRFlowable
    story.append(HRFlowable(width='100%', thickness=2, color=blue, spaceAfter=8))

    # ── Question ───────────────────────────────────────────────
    story.append(Paragraph(f'Question:  {question}', q_style))

    # ── Metric card ────────────────────────────────────────────
    if metric_label and metric_value:
        metric_data = [[metric_label], [metric_value]]
        mt = Table(metric_data, colWidths=[16*cm])
        mt.setStyle(TableStyle([
            ('BACKGROUND',   (0,0),(0,0), navy),
            ('TEXTCOLOR',    (0,0),(0,0), white),
            ('FONTNAME',     (0,0),(0,0), 'Helvetica'),
            ('FONTSIZE',     (0,0),(0,0), 11),
            ('ALIGN',        (0,0),(-1,-1), 'CENTER'),
            ('BACKGROUND',   (0,1),(0,1), lgray),
            ('FONTNAME',     (0,1),(0,1), 'Helvetica-Bold'),
            ('FONTSIZE',     (0,1),(0,1), 22),
            ('TEXTCOLOR',    (0,1),(0,1), navy),
            ('TOPPADDING',   (0,0),(-1,-1), 10),
            ('BOTTOMPADDING',(0,0),(-1,-1), 10),
        ]))
        story.append(mt)
        story.append(Spacer(1, 0.4*cm))

    # ── Chart image ────────────────────────────────────────────
    if fig is not None:
        png_bytes = fig_to_png(fig)
        img_buf   = io.BytesIO(png_bytes)
        img       = RLImage(img_buf, width=16*cm, height=8*cm)
        story.append(img)
        story.append(Spacer(1, 0.4*cm))

    # ── Data table ─────────────────────────────────────────────
    if df is not None and len(df) > 0:
        story.append(Paragraph('Data', ParagraphStyle('dh', fontSize=11,
                     fontName='Helvetica-Bold', textColor=navy, spaceBefore=6, spaceAfter=4)))

        # Build table data
        col_count  = len(df.columns)
        col_w      = 16*cm / col_count
        table_data = [list(df.columns)]
        for _, row in df.iterrows():
            table_data.append([str(v) if v is not None else '' for v in row])

        tbl = Table(table_data, colWidths=[col_w]*col_count, repeatRows=1)
        tbl.setStyle(TableStyle([
            # Header row
            ('BACKGROUND',    (0,0), (-1,0),  navy),
            ('TEXTCOLOR',     (0,0), (-1,0),  white),
            ('FONTNAME',      (0,0), (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,0),  9),
            ('ALIGN',         (0,0), (-1,0),  'CENTER'),
            # Data rows
            ('FONTNAME',      (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE',      (0,1), (-1,-1), 8),
            ('ALIGN',         (0,1), (-1,-1), 'LEFT'),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [white, rl_colors.HexColor('#F8F8F5')]),
            # Grid
            ('GRID',          (0,0), (-1,-1), 0.4, rl_colors.HexColor('#CCCCCC')),
            ('TOPPADDING',    (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ]))
        story.append(tbl)

    # ── Footer ─────────────────────────────────────────────────
    story.append(Spacer(1, 0.6*cm))
    story.append(HRFlowable(width='100%', thickness=1, color=rl_colors.HexColor('#CCCCCC')))
    story.append(Paragraph(
        'Confidential — Life Science Division  |  Generated by Life Science Data Chatbot  |  Powered by Snowflake Cortex',
        ParagraphStyle('footer', fontSize=7, textColor=rl_colors.HexColor('#999999'),
                       fontName='Helvetica', alignment=TA_CENTER, spaceBefore=4)
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()

def make_email_link(question, df, metric_label=None, metric_value=None):
    """Create a mailto: link that opens Outlook with data pre-filled."""
    subject = f"Life Science Report — {question[:60]}"
    today   = date.today().strftime('%B %d, %Y')

    if metric_label and metric_value:
        body_data = f"{metric_label}: {metric_value}"
    elif df is not None and len(df) > 0:
        # Build a simple text table
        lines = ['\t'.join(str(c) for c in df.columns)]
        for _, row in df.iterrows():
            lines.append('\t'.join(str(v) for v in row))
        body_data = '\n'.join(lines[:20])  # max 20 rows in email
        if len(df) > 20:
            body_data += f'\n... and {len(df)-20} more rows (download full data as CSV or Excel)'
    else:
        body_data = 'No data'

    body = (
        f"Hi,\n\n"
        f"Here are the results from the Life Science Data Chatbot:\n\n"
        f"Question: {question}\n"
        f"Date: {today}\n\n"
        f"{'─'*40}\n"
        f"{body_data}\n"
        f"{'─'*40}\n\n"
        f"Powered by Snowflake Cortex\n"
        f"Life Science Data Chatbot\n"
    )
    return f"mailto:?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"

def clipboard_tsv(df):
    return df.to_csv(index=False, sep='\t')

# ══════════════════════════════════════════════════════════════
# DOWNLOAD BAR — shown under every result
# ══════════════════════════════════════════════════════════════
def download_bar(question, df, fig=None,
                 metric_label=None, metric_value=None,
                 fname_prefix="result"):
    """6 export options: CSV | Excel | PNG | PDF | Email | Copy"""
    ts    = datetime.now().strftime('%Y%m%d_%H%M%S')
    fname = f"LifeScience_{fname_prefix}_{ts}"

    st.markdown("---")
    st.markdown("**📤 Export & Share:**")
    c1, c2, c3, c4, c5, c6 = st.columns(6)

    # 1. CSV ───────────────────────────────────────────────────
    with c1:
        export_df = df if df is not None and len(df)>0 else \
                    pd.DataFrame({'Metric':[metric_label],'Value':[metric_value]})
        st.download_button(
            label="📄 CSV",
            data=to_csv(export_df),
            file_name=f"{fname}.csv",
            mime="text/csv",
            use_container_width=True,
            help="Download as CSV — opens in Excel"
        )

    # 2. Excel ─────────────────────────────────────────────────
    with c2:
        try:
            st.download_button(
                label="📊 Excel",
                data=to_excel(export_df),
                file_name=f"{fname}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                help="Download as Excel (.xlsx)"
            )
        except Exception:
            st.button("📊 Excel", disabled=True, use_container_width=True)

    # 3. PNG ───────────────────────────────────────────────────
    with c3:
        if fig is not None:
            png = fig_to_png(fig)
        elif metric_label and metric_value:
            png = metric_to_png(metric_label, metric_value)
        else:
            png = None

        if png:
            st.download_button(
                label="🖼 PNG",
                data=png,
                file_name=f"{fname}.png",
                mime="image/png",
                use_container_width=True,
                help="Download as image — paste into PowerPoint or email"
            )
        else:
            st.button("🖼 PNG", disabled=True, use_container_width=True,
                      help="PNG not available for plain tables")

    # 4. PDF ───────────────────────────────────────────────────
    with c4:
        try:
            pdf_bytes = to_pdf(
                question, export_df, fig=fig,
                metric_label=metric_label, metric_value=metric_value
            )
            st.download_button(
                label="📑 PDF",
                data=pdf_bytes,
                file_name=f"{fname}.pdf",
                mime="application/pdf",
                use_container_width=True,
                help="Download as PDF report with chart + data table"
            )
        except Exception as e:
            st.button("📑 PDF", disabled=True, use_container_width=True,
                      help=f"PDF error: {str(e)[:60]}")

    # 5. Email ─────────────────────────────────────────────────
    with c5:
        mailto = make_email_link(question, export_df, metric_label, metric_value)
        st.markdown(
            f'<a href="{mailto}" target="_blank">'
            f'<button style="width:100%;padding:0.4rem 0;border-radius:6px;'
            f'border:1px solid #ccc;background:#fff;cursor:pointer;font-size:14px;">'
            f'📧 Email</button></a>',
            unsafe_allow_html=True
        )

    # 6. Copy ──────────────────────────────────────────────────
    with c6:
        copy_key = f'copy_{fname_prefix}_{ts}'
        if st.button("📋 Copy", use_container_width=True,
                     help="Click to expand — then Ctrl+A, Ctrl+C",
                     key=copy_key):
            st.session_state[f'show_{copy_key}'] = True

    if st.session_state.get(f'show_{copy_key}', False):
        if metric_label and metric_value:
            tsv = f"{metric_label}\t{metric_value}"
        else:
            tsv = clipboard_tsv(export_df)
        st.text_area("Select all → Ctrl+A → Ctrl+C:", value=tsv,
                     height=100, key=f'area_{copy_key}')

# ══════════════════════════════════════════════════════════════
# CHART DETECTION
# ══════════════════════════════════════════════════════════════
def detect_chart(df, question):
    if df is None or len(df) == 0: return 'empty'
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='ignore')
    rows      = len(df)
    cols      = len(df.columns)
    q         = question.lower()
    col_lower = [c.lower() for c in df.columns]

    if rows == 1 and cols == 1: return 'metric'
    has_date = any('date' in c or 'day' in c for c in col_lower)
    if has_date and cols == 2 and rows > 3: return 'line'
    has_status = 'status' in col_lower or any(
        w in q for w in ['status','breakdown','paid','overdue','pending','invoice status'])
    if has_status and cols == 2 and rows <= 10: return 'pie'
    is_ranked = any(w in q for w in ['top','rank','best','highest','most','leading'])
    if is_ranked and cols == 2 and rows <= 15: return 'ranked_bar'
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if cols == 2 and len(num_cols) == 1 and rows <= 20: return 'bar'
    return 'table'

# ══════════════════════════════════════════════════════════════
# CHART FUNCTIONS
# ══════════════════════════════════════════════════════════════
def fmt(v):
    if v >= 1_000_000: return f'${v/1_000_000:.1f}M'
    if v >= 1_000:     return f'${v/1_000:.0f}K'
    return f'{v:.0f}'

def bar_chart(df):
    lc,vc = df.columns[0], df.columns[1]
    d = df.sort_values(vc, ascending=True).copy()
    fig,ax = plt.subplots(figsize=(8, max(3, len(d)*0.7)))
    bars = ax.barh(d[lc].astype(str), d[vc], color=COLORS[:len(d)],
                   edgecolor='white', linewidth=0.8, height=0.6)
    for b in bars:
        w=b.get_width()
        ax.text(w*1.01, b.get_y()+b.get_height()/2, fmt(w), va='center', ha='left', fontsize=9)
    ax.set_xlabel(vc.replace('_',' ').title(), fontsize=10)
    ax.set_title(vc.replace('_',' ').title(), fontsize=13, fontweight='bold', color='#1B3A6B', pad=10)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: fmt(x)))
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    plt.tight_layout(); return fig

def line_chart(df):
    dc = [c for c in df.columns if 'date' in c.lower() or 'day' in c.lower()][0]
    vc = [c for c in df.columns if c != dc][0]
    d  = df.sort_values(dc).copy(); d[dc] = pd.to_datetime(d[dc])
    fig,ax = plt.subplots(figsize=(9, 4))
    ax.plot(d[dc], d[vc], color='#2E75B6', linewidth=2.5, marker='o', markersize=4)
    ax.fill_between(d[dc], d[vc], alpha=0.1, color='#2E75B6')
    ax.set_title(f'{vc.replace("_"," ").title()} Over Time',
                 fontsize=13, fontweight='bold', color='#1B3A6B', pad=10)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: fmt(x)))
    plt.xticks(rotation=30, ha='right', fontsize=8)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    plt.tight_layout(); return fig

def ranked_bar_chart(df):
    lc,vc = df.columns[0], df.columns[1]
    d = df.sort_values(vc, ascending=False).head(10).copy()
    fig,ax = plt.subplots(figsize=(9, 4))
    x = range(len(d))
    bars = ax.bar(x, d[vc], color=COLORS[:len(d)], edgecolor='white', linewidth=0.8, width=0.65)
    for b in bars:
        h=b.get_height()
        ax.text(b.get_x()+b.get_width()/2, h*1.01, fmt(h), ha='center', va='bottom', fontsize=8)
    labels=[str(n).split(' ')[0] if len(str(n))>10 else str(n) for n in d[lc]]
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=20, ha='right', fontsize=9)
    ax.set_title(f'Top {lc.replace("_"," ").title()} Ranking',
                 fontsize=13, fontweight='bold', color='#1B3A6B', pad=10)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: fmt(x)))
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    plt.tight_layout(); return fig

def pie_chart(df):
    lc,vc = df.columns[0], df.columns[1]
    pie_colors = ['#2E75B6','#EAF3DE','#FCEBEB','#FAEEDA','#EEEDFE'][:len(df)]
    fig,ax = plt.subplots(figsize=(6, 5))
    wedges,texts,autotexts = ax.pie(
        df[vc], labels=df[lc], autopct='%1.1f%%', colors=pie_colors,
        startangle=90, wedgeprops={'edgecolor':'white','linewidth':2})
    for t in texts:      t.set_fontsize(11)
    for at in autotexts: at.set_fontsize(10); at.set_color('#2C2C2A')
    ax.set_title(f'{lc.replace("_"," ").title()} Breakdown',
                 fontsize=13, fontweight='bold', color='#1B3A6B', pad=10)
    plt.tight_layout(); return fig

# ══════════════════════════════════════════════════════════════
# MAIN SHOW FUNCTION
# ══════════════════════════════════════════════════════════════
def show(item):
    df       = item['df']
    err      = item['err']
    question = item['q']
    sql      = item['sql']

    if err:
        st.error(err)
        with st.expander('🔍 View generated SQL'): st.code(sql, language='sql')
        return
    if df is None or len(df) == 0:
        st.info('No data found. Try a different date range.')
        with st.expander('🔍 View generated SQL'): st.code(sql, language='sql')
        return

    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='ignore')

    chart = detect_chart(df, question)

    # ── Metric ─────────────────────────────────────────────────
    if chart == 'metric':
        val   = df.iloc[0, 0]
        label = df.columns[0].replace('_',' ').title()
        if val is None: st.info('No data for that period.'); return
        if isinstance(val, float): disp = f'${val:,.2f}'
        elif isinstance(val, int): disp = f'{val:,}'
        else:                      disp = str(val)
        st.metric(label=label, value=disp)
        with st.expander('🔍 View generated SQL'): st.code(sql, language='sql')
        download_bar(question, df, metric_label=label, metric_value=disp,
                     fname_prefix="metric")

    # ── Bar chart ──────────────────────────────────────────────
    elif chart == 'bar':
        fig = bar_chart(df)
        st.pyplot(fig, use_container_width=True)
        with st.expander(f'📋 View table ({len(df)} rows)'):
            st.dataframe(df, use_container_width=True, hide_index=True)
        with st.expander('🔍 View generated SQL'): st.code(sql, language='sql')
        download_bar(question, df, fig=fig, fname_prefix="bar_chart")
        plt.close(fig)

    # ── Line chart ─────────────────────────────────────────────
    elif chart == 'line':
        fig = line_chart(df)
        st.pyplot(fig, use_container_width=True)
        with st.expander(f'📋 View table ({len(df)} rows)'):
            st.dataframe(df, use_container_width=True, hide_index=True)
        with st.expander('🔍 View generated SQL'): st.code(sql, language='sql')
        download_bar(question, df, fig=fig, fname_prefix="line_chart")
        plt.close(fig)

    # ── Ranked bar ─────────────────────────────────────────────
    elif chart == 'ranked_bar':
        fig = ranked_bar_chart(df)
        st.pyplot(fig, use_container_width=True)
        with st.expander(f'📋 View table ({len(df)} rows)'):
            st.dataframe(df, use_container_width=True, hide_index=True)
        with st.expander('🔍 View generated SQL'): st.code(sql, language='sql')
        download_bar(question, df, fig=fig, fname_prefix="ranked_chart")
        plt.close(fig)

    # ── Pie chart ──────────────────────────────────────────────
    elif chart == 'pie':
        col1,col2 = st.columns([1,1])
        with col1:
            fig = pie_chart(df)
            st.pyplot(fig, use_container_width=True)
        with col2:
            st.dataframe(df, use_container_width=True, hide_index=True)
        with st.expander('🔍 View generated SQL'): st.code(sql, language='sql')
        download_bar(question, df, fig=fig, fname_prefix="pie_chart")
        plt.close(fig)

    # ── Table ──────────────────────────────────────────────────
    else:
        st.caption(f'{len(df)} rows returned')
        st.dataframe(df, use_container_width=True, hide_index=True)
        with st.expander('🔍 View generated SQL'): st.code(sql, language='sql')
        download_bar(question, df, fname_prefix="table")

# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    st.header('📋 Try These Questions')
    qs = {
        '💰 Metric': [
            'What was total revenue yesterday?',
            'What is Urology revenue this month?',
            'How many invoices are overdue?',
            'What is total pending invoice amount?',
        ],
        '📊 Bar Chart': [
            'Compare revenue by division this month',
            'Compare all divisions revenue this quarter',
        ],
        '🏆 Ranked Bar': [
            'Show top 10 reps by revenue this quarter',
            'Who are the top 5 reps by total amount this month?',
            'How many orders did each rep place this month?',
        ],
        '📈 Line Chart': [
            'Show revenue trend for last 30 days',
            'Show daily revenue trend this month',
        ],
        '🥧 Pie Chart': [
            'Show invoice status breakdown',
            'Show order status breakdown',
        ],
        '📋 Table': [
            'What orders did Sarah Johnson place this month?',
            'Show overdue invoices for Cardiology',
        ],
    }
    for cat, qlist in qs.items():
        st.markdown(f'**{cat}**')
        for q in qlist:
            if st.button(q, use_container_width=True, key=q):
                st.session_state.pending = q
        st.markdown('')

# ══════════════════════════════════════════════════════════════
# SESSION STATE & CHAT
# ══════════════════════════════════════════════════════════════
if 'history' not in st.session_state: st.session_state.history = []
if 'pending' not in st.session_state: st.session_state.pending = None

question = st.chat_input('Ask about revenue, sales, reps or invoices...')
if st.session_state.pending:
    question = st.session_state.pending
    st.session_state.pending = None

if question:
    with st.spinner(f'Thinking about: "{question}"...'):
        sql = ask_cortex(question)
        df, err = run_query(sql)
    st.session_state.history.append({
        'q': question, 'sql': sql, 'df': df,
        'err': err, 'time': datetime.now().strftime('%H:%M:%S')
    })

if not st.session_state.history:
    st.info('👆 Type a question above or click one from the sidebar!')

for item in reversed(st.session_state.history):
    with st.chat_message('user'):
        st.markdown(f"**{item['q']}**")
        st.caption(f"Asked at {item['time']}")
    with st.chat_message('assistant', avatar='🧬'):
        show(item)
