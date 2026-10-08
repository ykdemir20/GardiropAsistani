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

def save_to_wardrobe_batch(new_items):
    wardrobe = load_wardrobe()
    wardrobe.extend(new_items)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(wardrobe, f, ensure_ascii=False, indent=2)

def delete_from_wardrobe(item_id):
    wardrobe = load_wardrobe()
    item_to_remove = next((it for it in wardrobe if it.get("id") == item_id), None)
    if item_to_remove:
        img_path = item_to_remove.get("image_path", "")
        if img_path and os.path.exists(img_path):
            try:
                os.remove(img_path)
            except Exception:
                pass
        updated = [it for it in wardrobe if it.get("id") != item_id]
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(updated, f, ensure_ascii=False, indent=2)

def analyze_single_image(img: Image.Image, key: str, mode: str):
    client = genai.Client(api_key=key)
    
    if mode == "Tek Parça":
        prompt = """
        Görseldeki MERKEZDE yer alan ANA KIYAFETİ analiz et.
        Arka plandaki zemin, mobilya, askılık gibi nesneleri KESİNLİKLE YOK SAY.
        Yanıtı STRICT şekilde bir JSON listesi olarak döndür:
        [
          {
            "category": "Üst Giyim" | "Alt Giyim" | "Dış Giyim" | "Ayakkabı" | "Aksesuar",
            "item_name": "Kıyafetin kısa adı",
            "color": "Ana renk",
            "style": "Streetwear" | "Casual" | "Smart Casual" | "Spor",
            "season": "Yazlık" | "Kışlık" | "Mevsimlik",
            "fit": "Oversize" | "Regular" | "Slim Fit" | "Baggy"
          }
        ]
        """
    else:
        prompt = """
        Bu fotoğrafta kişinin ÜZERİNDE GİYİLİ olan parçaları (Üst, Alt, Dış Giyim, Ayakkabı) tespit et.
        Arka plandaki oda eşyalarını, mobilyaları ASLA alma. Sadece giyilen gerçek kıyafetleri al.
        Her parçayı STRICT şekilde JSON listesi olarak döndür:
        [
          {
            "category": "Üst Giyim" | "Alt Giyim" | "Dış Giyim" | "Ayakkabı" | "Aksesuar",
            "item_name": "Kıyafetin kısa adı",
            "color": "Ana renk",
            "style": "Streetwear" | "Casual" | "Smart Casual" | "Spor",
            "season": "Yazlık" | "Kışlık" | "Mevsimlik",
            "fit": "Oversize" | "Regular" | "Slim Fit" | "Baggy"
          }
        ]
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
    
    if isinstance(parsed, dict):
        return [parsed]
    elif isinstance(parsed, list):
        return parsed
    return []

def generate_outfit(wardrobe_items: list, key: str, pinned_item_id: str = None, occasion: str = "Günlük", weather: str = "Ilıman"):
    client = genai.Client(api_key=key)
    clean_items = [
        {
            "id": it.get("id"),
            "name": it.get("item_name"),
            "category": it.get("category"),
            "color": it.get("color"),
            "style": it.get("style"),
            "season": it.get("season"),
            "fit": it.get("fit")
        }
        for it in wardrobe_items
    ]
    
    prompt = f"""
    Sen uzman bir stil danışmanısın. Kullanıcının gardırobundaki parçaları kullanarak uyumlu bir kombin yap.
    
    Mevcut Gardırop:
    {json.dumps(clean_items, ensure_ascii=False)}
    
    Kriterler:
    - Ortam/Etkinlik: {occasion}
    - Hava Durumu: {weather}
    - Kesinlikle Dahil Edilmesi Gereken Parça ID'si: {pinned_item_id if pinned_item_id else "Yok"}
    
    Renk uyumuna ve kalıplara dikkat et.
    Sadece ve sadece aşağıdaki JSON formatında yanıt ver:
    {{
      "selected_item_ids": ["parca_id_1", "parca_id_2"],
      "explanation": "Kombinin neden uyumlu olduğunun kısa açıklaması."
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

api_key = None
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
elif "GEMINI_API_KEY" in os.environ:
    api_key = os.environ["GEMINI_API_KEY"]
else:
    api_key = st.text_input("Gemini API Anahtarı", type="password")

if not api_key:
    st.info("Devam etmek için Gemini API anahtarınızı girin.")
    st.stop()

if "detected_items" not in st.session_state:
    st.session_state["detected_items"] = []

tab_add, tab_wardrobe, tab_outfit = st.tabs(["Kıyafet Ekle", "Gardırobum", "Kombin Yap"])

with tab_add:
    st.subheader("Fotoğraf Yükleme")
    
    mode_choice = st.radio("Fotoğraf Tipi:", ["Tek Parça (Zemin/Askı)", "Kombin / Boydan Görsel"], horizontal=True)
    mode_str = "Tek Parça" if "Tek Parça" in mode_choice else "Kombin"

    uploaded_files = st.file_uploader(
        "Fotoğrafları seçin (Tek veya çoklu seçim yapabilirsiniz)", 
        type=["jpg", "jpeg", "png"], 
        accept_multiple_files=True
    )

    if uploaded_files:
        st.write(f"📁 {len(uploaded_files)} adet fotoğraf seçildi.")
        
        if st.button("Fotoğrafları Analiz Et", type="primary"):
            st.session_state["detected_items"] = []
            os.makedirs("clothing_images", exist_ok=True)
            
            prog = st.progress(0)
            status = st.empty()
            
            for idx, f in enumerate(uploaded_files):
                status.text(f"Analiz ediliyor ({idx + 1}/{len(uploaded_files)})...")
                img = Image.open(f)
                
                img_id = str(uuid.uuid4())[:8]
                saved_path = f"clothing_images/{img_id}.png"
                img.save(saved_path)
                
                try:
                    res_list = analyze_single_image(img, api_key, mode_str)
                    for item in res_list:
                        item["temp_id"] = str(uuid.uuid4())[:8]
                        item["image_path"] = saved_path
                        st.session_state["detected_items"].append(item)
                except Exception as e:
                    st.error(f"Hata: {e}")
                
                prog.progress((idx + 1) / len(uploaded_files))
            
            status.text("Analiz tamamlandı!")

    if len(st.session_state["detected_items"]) > 0:
        st.divider()
        st.subheader(f"Onay Bekleyen Parçalar ({len(st.session_state['detected_items'])} adet)")
        st.caption("Yanlış veya gereksiz algılanan parçaları 'Bu Parçayı Çıkar' butonuyla silebilirsin.")

        categories = ["Üst Giyim", "Alt Giyim", "Dış Giyim", "Ayakkabı", "Aksesuar"]
        styles = ["Casual", "Streetwear", "Smart Casual", "Spor"]
        seasons = ["Mevsimlik", "Yazlık", "Kışlık"]
        fits = ["Regular", "Oversize", "Slim Fit", "Baggy"]

        # Her parçayı kart içinde gösterip anında çıkarma imkanı tanıyoruz
        items_to_remove = []
        for i, itm in enumerate(st.session_state["detected_items"]):
            with st.container(border=True):
                col_head, col_btn = st.columns([3, 1])
                with col_head:
                    st.markdown(f"**Parça #{i+1}**")
                with col_btn:
                    if st.button("❌ Çıkar", key=f"discard_{itm['temp_id']}"):
                        items_to_remove.append(itm["temp_id"])

                col_prev, col_inputs = st.columns([1, 3])
                with col_prev:
                    if os.path.exists(itm.get("image_path", "")):
                        st.image(itm["image_path"], use_container_width=True)

                with col_inputs:
                    raw_cat = str(itm.get("category", ""))
                    cat_idx = categories.index(raw_cat) if raw_cat in categories else 0
                    raw_style = str(itm.get("style", ""))
                    style_idx = styles.index(raw_style) if raw_style in styles else 0
                    raw_season = str(itm.get("season", ""))
                    season_idx = seasons.index(raw_season) if raw_season in seasons else 0
                    raw_fit = str(itm.get("fit", ""))
                    fit_idx = fits.index(raw_fit) if raw_fit in fits else 0

                    c1, c2 = st.columns(2)
                    with c1:
                        itm["item_name"] = st.text_input("İsim", value=str(itm.get("item_name", "Kıyafet")), key=f"n_{itm['temp_id']}")
                        itm["category"] = st.selectbox("Kategori", categories, index=cat_idx, key=f"c_{itm['temp_id']}")
                        itm["color"] = st.text_input("Renk", value=str(itm.get("color", "")), key=f"cl_{itm['temp_id']}")
                    with c2:
                        itm["style"] = st.selectbox("Tarz", styles, index=style_idx, key=f"s_{itm['temp_id']}")
                        itm["season"] = st.selectbox("Mevsim", seasons, index=season_idx, key=f"se_{itm['temp_id']}")
                        itm["fit"] = st.selectbox("Kalıp", fits, index=fit_idx, key=f"f_{itm['temp_id']}")

        # Çıkarılan parçaları listeden düş ve ekranı yenile
        if items_to_remove:
            st.session_state["detected_items"] = [
                it for it in st.session_state["detected_items"] if it["temp_id"] not in items_to_remove
            ]
            st.rerun()

        st.write("")
        if st.button("✅ Kalan Parçaları Gardıroba Ekle", type="primary", use_container_width=True):
            final_save_list = []
            for itm in st.session_state["detected_items"]:
                final_save_list.append({
                    "id": itm["temp_id"],
                    "item_name": itm["item_name"],
                    "category": itm["category"],
                    "color": itm["color"],
                    "style": itm["style"],
                    "season": itm["season"],
                    "fit": itm["fit"],
                    "image_path": itm["image_path"]
                })
            save_to_wardrobe_batch(final_save_list)
            st.session_state["detected_items"] = []
            st.success(f"{len(final_save_list)} parça gardıroba başarıyla kaydedildi!")
            st.rerun()

with tab_wardrobe:
    st.subheader("Kayıtlı Parçalar")
    items = load_wardrobe()
    if not items:
        st.write("Henüz eklenmiş bir kıyafet yok.")
    else:
        for it in reversed(items):
            with st.container(border=True):
                col_img, col_info, col_del = st.columns([1, 2, 0.7])
                with col_img:
                    if os.path.exists(it.get("image_path", "")):
                        st.image(it["image_path"], use_container_width=True)
                    else:
                        st.caption("Görsel yok")
                with col_info:
                    st.markdown(f"**{it.get('item_name', '')}**")
                    st.caption(f"Kategori: {it.get('category', '')} | Renk: {it.get('color', '')}")
                    st.caption(f"Tarz: {it.get('style', '')} | Kalıp: {it.get('fit', '')} | Mevsim: {it.get('season', '')}")
                with col_del:
                    if st.button("Sil", key=f"del_{it.get('id')}"):
                        delete_from_wardrobe(it.get("id"))
                        st.rerun()

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
            item_options[f"{it.get('item_name')} ({it.get('category')})"] = it.get("id")

        pinned_choice = st.selectbox("Kombinde Kesinlikle Olmasını İstediğin Parça (Opsiyonel):", list(item_options.keys()))
        pinned_id = item_options[pinned_choice]

        if st.button("Kombin Üret", type="primary"):
            with st.spinner("Kombin oluşturuluyor..."):
                try:
                    outfit_res = generate_outfit(items, api_key, pinned_id, occasion, weather)
                    selected_ids = outfit_res.get("selected_item_ids", [])
                    explanation = outfit_res.get("explanation", "")

                    st.markdown("### Önerilen Kombin")
                    st.write(f"💡 **Stil Yorumu:** {explanation}")

                    matched_items = [it for it in items if it.get("id") in selected_ids]
                    
                    if matched_items:
                        cols = st.columns(len(matched_items))
                        for idx, m_item in enumerate(matched_items):
                            with cols[idx]:
                                if os.path.exists(m_item.get("image_path", "")):
                                    st.image(m_item["image_path"], use_container_width=True)
                                st.caption(f"**{m_item.get('item_name')}**")
                                st.caption(f"{m_item.get('category')} - {m_item.get('color')}")
                    else:
                        st.warning("Eşleşen parça görseli bulunamadı.")
                except Exception as e:
                    st.error(f"Hata: {e}")
