import streamlit as st
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import html
import re
import urllib.parse
import base64
import io
from pypdf import PdfWriter, PdfReader

st.set_page_config(page_title="Test Paper Generator", layout="wide")
st.title("📄 Dynamic Test Paper Generator")

# --- PERFORMANCE OPTIMIZATION: CACHING & DATA PROCESSING ---
@st.cache_data
def process_data(file_data):
    df = pd.read_csv(file_data)
    df.fillna("", inplace=True) 
    
    prefixes = []
    for col in df.columns:
        if col.endswith('_question_text'):
            prefix = col.replace('_question_text', '')
            if prefix and prefix not in prefixes:
                prefixes.append(prefix)
                
    is_bilingual = len(prefixes) >= 2
    
    cols_to_clean = [col for col in df.columns if 'question_text' in col or 'option_' in col]
    for col in cols_to_clean:
        df[col] = df[col].apply(clean_html_content)

    group_col = f"{prefixes[0]}_chapter" if is_bilingual and f"{prefixes[0]}_chapter" in df.columns else 'chapter'
    grouped = df.groupby(group_col, sort=False)
    
    chapters = []
    for chapter_name, group in grouped:
        rows = []
        for _, row in group.iterrows():
            if is_bilingual:
                p1, p2 = prefixes[0], prefixes[1]
                tag1 = row.get(f"{p1}_exam_tag", row.get("exam_tag", ""))
                tag2 = row.get(f"{p2}_exam_tag", row.get("exam_tag", ""))
                
                qt1 = str(row[f"{p1}_question_text"]) + (f" &nbsp;<span style='color:#2563EB; font-size:0.9em;'><b>[{tag1}]</b></span>" if str(tag1).strip() else "")
                qt2 = str(row[f"{p2}_question_text"]) + (f" &nbsp;<span style='color:#2563EB; font-size:0.9em;'><b>[{tag2}]</b></span>" if str(tag2).strip() else "")
                
                rows.append({
                    'q_num': row.get(f"{p1}_question_number", row.get("question_number", "")),
                    'q1': qt1, 'A1': row.get(f"{p1}_option_A", ""), 'B1': row.get(f"{p1}_option_B", ""), 'C1': row.get(f"{p1}_option_C", ""), 'D1': row.get(f"{p1}_option_D", ""),
                    'q2': qt2, 'A2': row.get(f"{p2}_option_A", ""), 'B2': row.get(f"{p2}_option_B", ""), 'C2': row.get(f"{p2}_option_C", ""), 'D2': row.get(f"{p2}_option_D", ""),
                    'ans': row.get(f"{p1}_correct_answer", row.get("correct_answer", ""))
                })
            else:
                tag = row.get("exam_tag", "")
                qt = str(row.get("question_text", "")) + (f" &nbsp;<span style='color:#2563EB; font-size:0.9em;'><b>[{tag}]</b></span>" if str(tag).strip() else "")
                
                rows.append({
                    'q_num': row.get("question_number", ""),
                    'q1': qt, 'A1': row.get("option_A", ""), 'B1': row.get("option_B", ""), 'C1': row.get("option_C", ""), 'D1': row.get("option_D", ""),
                    'ans': row.get("correct_answer", "")
                })
                
        chapters.append({
            'name': str(chapter_name),
            'count': len(rows),
            'rows': rows
        })
    return df, chapters, is_bilingual

# --- SIRF YAHI FUNCTION CHANGE KIYA HAI LINE BREAKS KE LIYE ---
def clean_html_content(text):
    if not isinstance(text, str): return text
    
    # 1. Locked HTML ko asli HTML mein badalna
    text = html.unescape(text)
    
    # 2. Paragraphs aur Enters ko Line Breaks (<br>) mein badalna
    text = text.replace('</p>', '<br><br>')
    text = text.replace('<p>', '')
    text = text.replace('\n', '<br>')
    
    # 3. Faltu ke bade gaps ko theek karna
    text = re.sub(r'(<br\s*/?>\s*){3,}', '<br><br>', text)
    
    # 4. Question ke shuru aur aakhiri ka faltu space/break hatana
    text = text.strip()
    text = re.sub(r'^(<br\s*/?>\s*)+', '', text)
    text = re.sub(r'(<br\s*/?>\s*)+$', '', text)
    
    # 5. Image links theek karna
    text = text.replace('src="//', 'src="https://')

    # 6. Maths (LaTeX) code theek karna
    def replace_math(match):
        encoded = urllib.parse.quote("\\Large " + match.group(1).strip())
        return f'<img src="https://latex.codecogs.com/svg.image?{encoded}" style="vertical-align: middle; border: none; margin: 0 2px;" />'

    return re.sub(r'\\\((.*?)\\\)', replace_math, text)
# --------------------------------------------------------------

def get_base64_image(uploaded_file):
    if uploaded_file is not None:
        return f"data:{uploaded_file.type};base64,{base64.b64encode(uploaded_file.getvalue()).decode()}"
    return None

# --- UI FOR SETTINGS (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Promotion Setup")
    promo_tier = st.radio("Promotion Tier", ["Without Promotions", "With Promotions"])
    
    header_left_b64 = header_right_b64 = footer_b64 = watermark_b64 = None
    header_left_link = header_right_link = footer_link = "https://testbook.com"
    header_height = footer_height = 60
    header_logo_width = 45 
    watermark_opacity = 0.15
    watermark_angle = -45
    promo_layout = "Only Header"

    if promo_tier == "With Promotions":
        promo_layout = st.radio("Promotion Layout", ["Only Header", "Both Header & Footer"])
        
        st.divider()
        st.header("🖼️ Split Header Settings")
        header_height = st.slider("Header Size (px)", 30, 150, 60)
        header_logo_width = st.slider("Header Logo Width (%)", 10, 100, 45)

        col_hl, col_hr = st.columns(2)
        with col_hl:
            header_left_img = st.file_uploader("Left Header", type=['png', 'jpg', 'jpeg'])
            header_left_link = st.text_input("Left Link", "https://testbook.com")
            header_left_b64 = get_base64_image(header_left_img)
        with col_hr:
            header_right_img = st.file_uploader("Right Header", type=['png', 'jpg', 'jpeg'])
            header_right_link = st.text_input("Right Link", "https://testbook.com")
            header_right_b64 = get_base64_image(header_right_img)

        if "Footer" in promo_layout:
            st.divider()
            st.header("🖼️ Footer Settings")
            footer_height = st.slider("Footer Size (px)", 30, 150, 60)
            footer_img_file = st.file_uploader("Footer Image", type=['png', 'jpg', 'jpeg'])
            footer_link = st.text_input("Footer Link", "https://testbook.com")
            footer_b64 = get_base64_image(footer_img_file)
        else:
            footer_height = 0

        st.divider()
        st.header("©️ Watermark")
        watermark_img_file = st.file_uploader("Watermark Image", type=['png', 'jpg', 'jpeg'])
        watermark_opacity = st.slider("Watermark Opacity", 0.0, 1.0, 0.15)
        watermark_angle = st.slider("Watermark Angle", -90, 90, -45)
        watermark_b64 = get_base64_image(watermark_img_file)

    st.divider()
    st.header("🎨 Styling & Branding")
    
    question_style = st.radio("Question Box Style", ["Plain Text", "Colorful Strip", "Grey Box"])
    answer_key_format = st.radio("Answer Key Format", ["End of Chapter", "Below Every Question", "Both Places"])
    
    selected_font_size = st.slider("Font Size (pt)", min_value=8, max_value=16, value=11)
    selected_color = st.color_picker("Primary Color (Chapters, Index & Inline Answer)", "#00d1ff")

    # --- NEW FEATURE: COVER & LAST PAGE PDF ATTACHMENT ---
    st.divider()
    st.header("📄 PDF Attachments")
    st.caption("Optional: Attach A4 PDF pages to the start and end of your test paper.")
    front_page_pdf = st.file_uploader("Upload Cover Page (PDF)", type=["pdf"])
    last_page_pdf = st.file_uploader("Upload Last Page (PDF)", type=["pdf"])

# --- MAIN EXECUTION ---
uploaded_file = st.file_uploader("Upload your Questions CSV", type=["csv"])

if uploaded_file is not None:
    df, chapters_data, is_bilingual = process_data(uploaded_file)

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("📝 Edit Data")
        st.data_editor(df, num_rows="dynamic", use_container_width=True)
        st.info("💡 Generating PDF with cached data for faster previews.")

        try:
            env = Environment(loader=FileSystemLoader('.'))
            template = env.get_template('template.html')

            html_out = template.render(
                chapters=chapters_data,
                is_bilingual=is_bilingual, 
                promotion_tier=promo_tier,
                promo_layout=promo_layout,
                question_style=question_style,
                answer_key_format=answer_key_format,
                user_font_size=selected_font_size,
                user_color=selected_color,
                header_left_b64=header_left_b64,
                header_left_link=header_left_link,
                header_right_b64=header_right_b64,
                header_right_link=header_right_link,
                header_height=header_height,
                header_logo_width=header_logo_width,
                footer_b64=footer_b64,
                footer_link=footer_link,
                footer_height=footer_height,
                watermark_b64=watermark_b64,
                watermark_opacity=watermark_opacity,
                watermark_angle=watermark_angle
            )

            # Generate original PDF from HTML
            pdf_bytes = HTML(string=html_out).write_pdf()

            # --- PDF MERGING LOGIC ---
            if front_page_pdf is not None or last_page_pdf is not None:
                merger = PdfWriter()
                
                # 1. Add Front Page if uploaded
                if front_page_pdf is not None:
                    merger.append(PdfReader(front_page_pdf))
                
                # 2. Add Main Generated Test Paper
                merger.append(PdfReader(io.BytesIO(pdf_bytes)))
                
                # 3. Add Last Page if uploaded
                if last_page_pdf is not None:
                    merger.append(PdfReader(last_page_pdf))
                    
                # Save the merged result
                output_stream = io.BytesIO()
                merger.write(output_stream)
                pdf_bytes = output_stream.getvalue()
                merger.close()

            st.divider()
            st.download_button(
                label="📥 Download Final PDF",
                data=pdf_bytes,
                file_name="Test_Paper.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"An error occurred: {e}")

    if "pdf_bytes" in locals():
        with col2:
            st.subheader("👁️ Live Preview")
            base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}#toolbar=0" width="100%" height="800px" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
