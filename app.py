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
    except Exception:
        return []

def save_to_wardrobe(item):
    wardrobe = load_wardrobe()
    wardrobe.append(item)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(wardrobe, f, ensure_ascii=False, indent=2)

def analyze_clothing(img: Image.Image, key: str):
    client = genai.Client(api_key=key)
    prompt = """
    Bu fotoğraftaki kıyafeti analiz et ve STRICT şekilde sadece aşağıdaki JSON formatında tek bir nesne olarak döndür:
    {
      "category": "Üst Giyim" | "Alt Giyim" | "Dış Giyim" | "Ayakkabı" | "Aksesuar",
      "item_name": "Kıyafetin kısa adı (örn: Kahverengi Ceket)",
      "color": "Ana renk",
      "style": "Streetwear" | "Casual" | "Smart Casual" | "Spor",
      "season": "Yazlık" | "Kışlık" | "Mevsimlik",
      "fit": "Oversize" | "Regular" | "Slim Fit" | "Baggy"
    }
    """
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=[img, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    raw = response.text.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.endswith("```"):
        raw = raw[:-3]
    parsed = json.loads(raw.strip())
    if isinstance(parsed, list) and len(parsed) > 0:
        parsed = parsed[0]
    return parsed if isinstance(parsed, dict) else {}

def generate_outfit(wardrobe_items: list, key: str, pinned_item_id: str = None, occasion: str = "Günlük", weather: str = "Ilıman"):
    client = genai.Client(api_key=key)
    
    # Modele sadece metin özetini yolluyoruz (sıfıra yakın maliyet ve hız için)
    clean_items = [
        {
            "id": it["id"],
            "name": it["item_name"],
            "category": it["category"],
            "color": it["color"],
            "style": it["style"],
            "season": it["season"],
            "fit": it["fit"]
        }
        for it in wardrobe_items
    ]
    
    prompt = f"""
    Sen uzman bir stil danışmanısın. Kullanıcının gardırobundaki parçaları kullanarak harika bir kombin yap.
    
    Mevcut Gardırop:
    {json.dumps(clean_items, ensure_ascii=False)}
    
    Kriterler:
    - Ortam/Etkinlik: {occasion}
    - Hava Durumu: {weather}
    - Kesinlikle Dahil Edilmesi Gereken Parça ID'si: {pinned_item_id if pinned_item_id else "Yok (tamamen serbestsin)"}
    
    Renk uyumuna, katmanlamaya ve kalıplara dikkat et.
    Sadece ve sadece aşağıdaki JSON formatında yanıt ver:
    {{
      "selected_item_ids": ["seçilen_parça_id_1", "seçilen_parça_id_2"],
      "explanation": "Bu kombini neden seçtiğinin, renk ve tarz uyumunun 2-3 cümlelik açıklaması."
    }}
    """
    
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    raw = response.text.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return json.loads(raw.strip())

st.title("Dijital Gardırop")

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    api_key = st.text_input("Gemini API Anahtarı", type="password")

if not api_key:
    st.info("Devam etmek için Gemini API anahtarınızı girin.")
    st.stop()

if "current_image" not in st.session_state:
    st.session_state["current_image"] = None
if "analyzed_data" not in st.session_state:
    st.session_state["analyzed_data"] = None

tab_add, tab_wardrobe, tab_outfit = st.tabs(["Kıyafet Ekle", "Gardırobum", "Kombin Yap"])

with tab_add:
    st.subheader("Yeni Kıyafet Yükle")
    uploaded_file = st.file_uploader("Fotoğraf seç veya çek", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        st.session_state["current_image"] = Image.open(uploaded_file)

    if st.session_state["current_image"] is not None:
        st.image(st.session_state["current_image"], caption="Yüklenen Parça", use_container_width=True)

        if st.button("Gemini ile Analiz Et", type="primary"):
            with st.spinner("Kıyafet analiz ediliyor..."):
                try:
                    res = analyze_clothing(st.session_state["current_image"], api_key)
                    st.session_state["analyzed_data"] = res
                except Exception as e:
                    st.error(f"Hata: {e}")

    if isinstance(st.session_state["analyzed_data"], dict) and st.session_state["current_image"] is not None:
        st.divider()
        st.subheader("Bilgileri Doğrula & Kaydet")
        data = st.session_state["analyzed_data"]

        categories = ["Dış Giyim", "Üst Giyim", "Alt Giyim", "Ayakkabı", "Aksesuar"]
        styles = ["Casual", "Streetwear", "Smart Casual", "Spor"]
        seasons = ["Mevsimlik", "Yazlık", "Kışlık"]
        fits = ["Regular", "Oversize", "Slim Fit", "Baggy"]

        raw_cat = str(data.get("category", ""))
        cat_idx = categories.index(raw_cat) if raw_cat in categories else 0

        raw_style = str(data.get("style", ""))
        style_idx = styles.index(raw_style) if raw_style in styles else 0

        raw_season = str(data.get("season", ""))
        season_idx = seasons.index(raw_season) if raw_season in seasons else 0

        raw_fit = str(data.get("fit", ""))
        fit_idx = fits.index(raw_fit) if raw_fit in fits else 0

        with st.form("save_form"):
            item_name = st.text_input("Parça İsmi", value=str(data.get("item_name", "Kıyafet")))
            col1, col2 = st.columns(2)
            with col1:
                category = st.selectbox("Kategori", categories, index=cat_idx)
                color = st.text_input("Ana Renk", value=str(data.get("color", "")))
                fit = st.selectbox("Kalıp", fits, index=fit_idx)
            with col2:
                style = st.selectbox("Tarz", styles, index=style_idx)
                season = st.selectbox("Mevsim", seasons, index=season_idx)

            save_btn = st.form_submit_button("Gardıroba Kaydet")

            if save_btn:
                os.makedirs("clothing_images", exist_ok=True)
                img_id = str(uuid.uuid4())[:8]
                saved_path = f"clothing_images/{img_id}.png"
                st.session_state["current_image"].save(saved_path)

                final_item = {
                    "id": img_id,
                    "item_name": item_name,
                    "category": category,
                    "color": color,
                    "style": style,
                    "season": season,
                    "fit": fit,
                    "image_path": saved_path
                }
                save_to_wardrobe(final_item)
                st.session_state["analyzed_data"] = None
                st.session_state["current_image"] = None
                st.success(f"'{item_name}' başarıyla gardıroba eklendi!")

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
                    st.markdown(f"**{it.get('item_name', '')}**")
                    st.caption(f"Kategori: {it.get('category', '')} | Renk: {it.get('color', '')}")
                    st.caption(f"Tarz: {it.get('style', '')} | Kalıp: {it.get('fit', '')} | Mevsim: {it.get('season', '')}")

with tab_outfit:
    st.subheader("Kişisel Kombin Önerisi")
    items = load_wardrobe()
    
    if len(items) < 2:
        st.info("Kombin üretebilmek için gardırobuna en az 2 farklı parça eklemelisin.")
    else:
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            occasion = st.selectbox("Ortam / Plan", ["Günlük / Okul", "Streetwear / Rahat", "Akşam Dışarı Çıkma", "Spor", "Şık / Randevu"])
        with col_opt2:
            weather = st.selectbox("Hava Durumu", ["Ilıman / Mevsimlik", "Sıcak / Güneşli", "Soğuk / Yağmurlu", "Rüzgarlı"])

        item_options = {"Seçim Yok (Hepsini AI seçsin)": None}
        for it in items:
            item_options[f"{it['item_name']} ({it['category']})"] = it["id"]

        pinned_choice = st.selectbox("Kombinde Kesinlikle Olmasını İstediğin Parça (Opsiyonel):", list(item_options.keys()))
        pinned_id = item_options[pinned_choice]

        if st.button("Kombin Üret", type="primary"):
            with st.spinner("Gardırobun taranıyor ve en uyumlu parçalar seçiliyor..."):
                try:
                    outfit_res = generate_outfit(items, api_key, pinned_id, occasion, weather)
                    selected_ids = outfit_res.get("selected_item_ids", [])
                    explanation = outfit_res.get("explanation", "")

                    st.markdown("### Önerilen Kombin")
                    st.write(f"💡 **Stil Yorumu:** {explanation}")

                    matched_items = [it for it in items if it["id"] in selected_ids]
                    
                    if matched_items:
                        cols = st.columns(len(matched_items))
                        for idx, m_item in enumerate(matched_items):
                            with cols[idx]:
                                if os.path.exists(m_item.get("image_path", "")):
                                    st.image(m_item["image_path"], use_container_width=True)
                                st.caption(f"**{m_item['item_name']}**")
                                st.caption(f"{m_item['category']} - {m_item['color']}")
                    else:
                        st.warning("Eşleşen parça görseli bulunamadı.")
                except Exception as e:
                    st.error(f"Kombin oluşturulurken hata: {e}")
