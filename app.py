import os
import json
import uuid
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

st.set_page_config(page_title="Gardırop Asistanı", layout="centered", initial_sidebar_state="collapsed")

DATA_FILE = "wardrobe.json"

def load_wardrobe():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_to_wardrobe(item):
    wardrobe = load_wardrobe()
    wardrobe.append(item)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(wardrobe, f, ensure_ascii=False, indent=2)

def analyze_clothing(image: Image.Image, api_key: str):
    client = genai.Client(api_key=api_key)
    prompt = """
    Bu fotoğraftaki kıyafeti analiz et ve STRICT şekilde aşağıdaki JSON formatında döndür:
    {
      "category": "Üst Giyim" | "Alt Giyim" | "Dış Giyim" | "Ayakkabı" | "Aksesuar",
      "item_name": "Kıyafetin kısa adı (örn: Kahverengi Fermuarlı Ceket)",
      "color": "Ana renk",
      "style": "Streetwear" | "Casual" | "Smart Casual" | "Spor",
      "season": "Yazlık" | "Kışlık" | "Mevsimlik",
      "fit": "Oversize" | "Regular" | "Slim Fit" | "Baggy"
    }
    """
    response = client.models.generate_content(
        model="gemini-3.7-flash",
        contents=[image, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    return json.loads(response.text)



st.title("Dijital Gardırop")

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    api_key = st.text_input("Gemini API Anahtarı", type="password", help="aistudio.google.com üzerinden alabilirsiniz.")

if not api_key:
    st.info("Devam etmek için Gemini API anahtarınızı girin.")
    st.stop()

tab_add, tab_wardrobe = st.tabs(["Kıyafet Ekle", "Gardırobum"])

with tab_add:
    st.subheader("Yeni Kıyafet Yükle")
    uploaded_file = st.file_uploader("Fotoğraf seç veya çek", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Yüklenen Parça", use_container_width=True)

        if st.button("Gemini ile Analiz Et", type="primary"):
            with st.spinner("Kıyafet taranıyor ve analiz ediliyor..."):
                try:
                    result = analyze_clothing(image, api_key)
                    st.session_state["analyzed_data"] = result
                    st.session_state["analyzed_image_name"] = uploaded_file.name
                    st.success("Analiz tamamlandı! Aşağıdaki bilgileri kontrol edip onaylayın.")
                except Exception as e:
                    st.error(f"Analiz sırasında hata oluştu: {e}")

    if "analyzed_data" in st.session_state:
        st.divider()
        st.subheader("Bilgileri Doğrula & Kaydet")
        data = st.session_state["analyzed_data"]

        with st.form("verify_form"):
            col1, col2 = st.columns(2)
            categories = ["Üst Giyim", "Alt Giyim", "Dış Giyim", "Ayakkabı", "Aksesuar"]
            styles = ["Streetwear", "Casual", "Smart Casual", "Spor"]
            seasons = ["Yazlık", "Kışlık", "Mevsimlik"]
            fits = ["Oversize", "Regular", "Slim Fit", "Baggy"]

            cat_idx = categories.index(data.get("category")) if data.get("category") in categories else 0
            style_idx = styles.index(data.get("style")) if data.get("style") in styles else 0
            season_idx = seasons.index(data.get("season")) if data.get("season") in seasons else 0
            fit_idx = fits.index(data.get("fit")) if data.get("fit") in fits else 0

            item_name = st.text_input("Parça İsmi", value=data.get("item_name", ""))
            with col1:
                category = st.selectbox("Kategori", categories, index=cat_idx)
                color = st.text_input("Ana Renk", value=data.get("color", ""))
                fit = st.selectbox("Kalıp", fits, index=fit_idx)
            with col2:
                style = st.selectbox("Tarz", styles, index=style_idx)
                season = st.selectbox("Mevsim", seasons, index=season_idx)

            submit = st.form_submit_button("Gardıroba Kaydet")

            if submit:
                os.makedirs("clothing_images", exist_ok=True)
                img_id = str(uuid.uuid4())[:8]
                saved_img_path = f"clothing_images/{img_id}_{st.session_state.get('analyzed_image_name', 'item.png')}"
                image.save(saved_img_path)

                final_item = {
                    "id": img_id,
                    "item_name": item_name,
                    "category": category,
                    "color": color,
                    "style": style,
                    "season": season,
                    "fit": fit,
                    "image_path": saved_img_path
                }
                save_to_wardrobe(final_item)
                st.success(f"'{item_name}' gardıroba başarıyla eklendi!")
                del st.session_state["analyzed_data"]
                st.rerun()

with tab_wardrobe:
    st.subheader("Kayıtlı Parçalar")
    items = load_wardrobe()
    if not items:
        st.write("Henüz eklenmiş bir kıyafet yok.")
    else:
        for it in reversed(items):
            with st.container(border=True):
                col_img, col_info = st.columns([1, 2])
                with col_img:
                    if os.path.exists(it.get("image_path", "")):
                        st.image(it["image_path"], use_container_width=True)
                    else:
                        st.caption("Görsel bulunamadı")
                with col_info:
                    st.markdown(f"**{it['item_name']}**")
                    st.caption(f"Kategori: {it['category']} | Renk: {it['color']}")
                    st.caption(f"Tarz: {it['style']} | Kalıp: {it['fit']} | Mevsim: {it['season']}")
