import streamlit as st
import pandas as pd
import openpyxl
from openpyxl.worksheet.datavalidation import DataValidation
from datetime import datetime, timedelta
import random
import io
import requests
import time

def generate_content_openai(prompt, api_key, model, max_tokens=80, temperature=0.7, retries=3, retry_delay=1):
    prompt = prompt.strip()
    if not prompt.endswith("Bitte antworte auf Deutsch."):
        prompt += " Bitte antworte auf Deutsch."
    endpoint = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    for attempt in range(retries):
        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()
            content = content.strip().strip('"').strip("'")
            return content
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(retry_delay)
            else:
                st.error(f"Fehler bei der OpenAI-Anfrage: {e}")
                return "Idee konnte nicht automatisch generiert werden."

def generate_date_range(start_date, num_days):
    return [start_date + timedelta(days=i) for i in range(num_days)]

def create_excel_calendar(df, customer):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Content Kalender"
    for col, header in enumerate(df.columns, 1):
        ws.cell(row=1, column=col).value = header
    for row, record in enumerate(df.itertuples(index=False), 2):
        for col, value in enumerate(record, 1):
            ws.cell(row=row, column=col).value = value
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

st.title("Content Kalender Generator (OpenAI, Deutsch, Plattformen editierbar)")

api_key = st.text_input("OpenAI API Key", type="password", help="Deinen API Key bekommst du unter https://platform.openai.com/api-keys")
model = st.selectbox("OpenAI Modell", ["gpt-3.5-turbo", "gpt-4o", "gpt-4"])
customer = st.text_input("Kundenname", "Raiffeisenbank Mainschleife-Steigerwald eG")
num_days = st.number_input("Zeitraum (Tage)", min_value=30, max_value=365, value=90)
start_date = st.date_input("Startdatum", value=datetime.today())

# --- Plattformen (editierbar) ---
st.markdown("### Plattformen")
if "platforms" not in st.session_state:
    st.session_state.platforms = ["Instagram", "Facebook", "TikTok"]

del_idx = None
platform_cols = st.columns([3, 1])
for i, p in enumerate(st.session_state.platforms):
    with platform_cols[0]:
        st.session_state.platforms[i] = st.text_input(f"Plattform {i+1}", value=p, key=f"pl_{i}")
    with platform_cols[1]:
        if st.button("❌", key=f"del_pl_{i}"):
            del_idx = i
if del_idx is not None:
    st.session_state.platforms.pop(del_idx)

if st.button("Plattform hinzufügen"):
    st.session_state.platforms.append("")

st.markdown("---")

# --- Themen & Beispiele ---
st.markdown("### Themen & Beispiele")
if "themes" not in st.session_state:
    st.session_state.themes = [
        {"name": "Volkach", "prompt": "Erstelle eine kreative Content-Idee für die Region Volkach für {platform} als {post_type}.", "examples": ["Führung Volkach", "Wanderroute Prichsenstadt"]}
    ]

del_theme_idx = None
for i, theme in enumerate(st.session_state.themes):
    cols = st.columns([3,3,3,1])
    theme["name"] = cols[0].text_input(f"Themenname {i+1}", value=theme["name"], key=f"name_{i}")
    theme["prompt"] = cols[1].text_area(f"Prompt {i+1}", value=theme["prompt"], key=f"prompt_{i}", height=60)
    theme["examples"] = cols[2].text_area(f"Beispiel-Ideen {i+1} (kommagetrennt)", value=", ".join(theme["examples"]), key=f"ex_{i}").split(",")
    if cols[3].button("❌", key=f"del_theme_{i}"):
        del_theme_idx = i
if del_theme_idx is not None:
    st.session_state.themes.pop(del_theme_idx)

if st.button("Thema hinzufügen"):
    st.session_state.themes.append({"name": "", "prompt": "", "examples": [""]})

st.markdown("---")

# --- Frequenzen pro Plattform ---
st.markdown("### Wöchentliche Frequenz je Plattform")
frequencies = {}
cols = st.columns(len(st.session_state.platforms))
for idx, p in enumerate(st.session_state.platforms):
    default_freq = 2
    frequencies[p] = cols[idx].number_input(f"{p}", min_value=0, max_value=7, value=default_freq, key=f"freq_{p}")

# --- Kalender generieren ---
if st.button("Kalender generieren"):
    st.info("Bitte warte. Die Content-Ideen werden jetzt per OpenAI generiert ...")
    date_list = generate_date_range(start_date, num_days)
    rows = []
    for p in st.session_state.platforms:
        freq = frequencies[p]
        if freq == 0: continue
        days = [d for d in date_list if d.weekday() < 5]
        n_posts = freq * (num_days // 7)
        if n_posts == 0: continue
        selected_days = days[::max(1, len(days)//n_posts)][:n_posts]
        for idx, date in enumerate(selected_days):
            theme = random.choice(st.session_state.themes)
            post_type = "Beitrag"
            prompt = theme["prompt"].replace("{platform}", p).replace("{post_type}", post_type)
            if api_key.strip():
                content = generate_content_openai(prompt, api_key, model)
            else:
                content = random.choice([e for e in theme["examples"] if e.strip()])
            rows.append([
                date.strftime("%d.%m.%Y"),
                date.isocalendar()[1],
                date.strftime("%A"),
                p,
                theme["name"],
                post_type,
                content,
                "in Planung"
            ])
    if not rows:
        st.warning("Keine Einträge erzeugt. Bitte prüfe Plattformen, Frequenzen und Zeitraum.")
    else:
        df = pd.DataFrame(rows, columns=["Datum","KW","Tag","Plattform","Thema","Art des Posts","Inhalt","Status"])
        st.success("Fertig! Du kannst die Tabelle als Excel exportieren.")
        st.dataframe(df)
        excel_file = create_excel_calendar(df, customer)
        st.download_button(
            label="Content Kalender als Excel herunterladen",
            data=excel_file,
            file_name=f"Content_Kalender_{customer}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
