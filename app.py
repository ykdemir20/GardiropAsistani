import os
import io
import json
import uuid
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types
from supabase import create_client, Client

st.set_page_config(page_title="Gardırop Asistanı", layout="centered", initial_sidebar_state="collapsed")

# API ve Supabase Bağlantısı
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
supabase_url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")

if not api_key:
    st.error("GEMINI_API_KEY bulunamadı. Streamlit Secrets'a ekleyin.")
    st.stop()

if not supabase_url or not supabase_key:
    st.error("SUPABASE_URL veya SUPABASE_KEY bulunamadı. Streamlit Secrets'a ekleyin.")
    st.stop()

@st.cache_resource
def get_supabase() -> Client:
    return create_client(supabase_url, supabase_key)

supabase = get_supabase()

def load_wardrobe():
    try:
        res = supabase.table("wardrobe").select("*").order("created_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        st.error(f"Gardırop yüklenirken hata: {e}")
        return []

def save_to_wardrobe_batch(new_items):
    try:
        supabase.table("wardrobe").insert(new_items).execute()
    except Exception as e:
        st.error(f"Kayıt hatası: {e}")

def update_wardrobe_item(updated_item):
    try:
        supabase.table("wardrobe").update({
            "item_name": updated_item.get("item_name"),
            "category": updated_item.get("category"),
            "color": updated_item.get("color"),
            "style": updated_item.get("style"),
            "season": updated_item.get("season"),
            "fit": updated_item.get("fit")
        }).eq("id", updated_item.get("id")).execute()
    except Exception as e:
        st.error(f"Güncelleme hatası: {e}")

def delete_from_wardrobe(item_id, image_url):
    try:
        # Storage'dan görseli sil
        if image_url and "clothing-images/" in image_url:
            file_name = image_url.split("clothing-images/")[-1].split("?")[0]
            supabase.storage.from_("clothing-images").remove([file_name])
        # Tablodan sil
        supabase.table("wardrobe").delete().eq("id", item_id).execute()
    except Exception as e:
        st.error(f"Silme hatası: {e}")

def upload_image_to_supabase(img: Image.Image) -> str:
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()
    
    file_name = f"{uuid.uuid4().hex[:10]}.png"
    supabase.storage.from_("clothing-images").upload(
        path=file_name,
        file=img_bytes,
        file_options={"content-type": "image/png"}
    )
    return supabase.storage.from_("clothing-images").get_public_url(file_name)

def analyze_single_image(img: Image.Image, key: str, mode: str, known_items: list):
    client = genai.Client(api_key=key)
    
    known_summary = [
        f"- {it.get('category')}: {it.get('item_name')} ({it.get('color')}, {it.get('fit', '')})"
        for it in known_items
    ]
    known_str = "\n".join(known_summary) if known_summary else "Henüz kayıtlı parça yok."

    if mode == "Tek Parça":
        prompt = f"""
        Görseldeki MERKEZDE yer alan ANA KIYAFETİ analiz et.
        Arka plandaki mobilya, yatak, zemin, askılık gibi ilgisiz nesneleri KESİNLİKLE YOK SAY.

        MEVCUT GARDIROP VE YENİ TESPİT EDİLEN PARÇALAR:
        {known_str}

        KRİTİK KURAL (MÜKERRER KONTROLÜ):
        Fotoğraftaki kıyafet yukarıdaki listede yer alan bir parça ile AYNI veya ÇOK BENZER ise, bu kıyafeti listeye EKLEME ve boş liste [] döndür.
        Sadece ve sadece listede henüz OLMAYAN, YENİ bir parçaysa aşağıdaki JSON formatında tek elemanlı liste döndür:
        [
          {{
            "category": "Üst Giyim" | "Alt Giyim" | "Dış Giyim" | "Ayakkabı" | "Aksesuar",
            "item_name": "Kıyafetin kısa adı",
            "color": "Ana renk",
            "style": "Streetwear" | "Casual" | "Smart Casual" | "Spor",
            "season": "Yazlık" | "Kışlık" | "Mevsimlik",
            "fit": "Oversize" | "Regular" | "Slim Fit" | "Baggy"
          }}
        ]
        """
    else:
        prompt = f"""
        Bu fotoğrafta kişinin ÜZERİNDE GİYİLİ olan parçaları (Üst, Alt, Dış Giyim, Ayakkabı) analiz et.
        Arka plandaki oda eşyalarını, aynayı, mobilyaları ASLA kıyafet sanma. Sadece giyilen gerçek kıyafetleri al.

        MEVCUT GARDIROP VE YENİ TESPİT EDİLEN PARÇALAR:
        {known_str}

        KRİTİK KURAL (MÜKERRER KONTROLÜ):
        Kişinin üzerindeki parçalardan herhangi biri yukarıdaki listede zaten VARSA, onu TEKRAR DÖNDÜRME, ATLA.
        SADECE yukarıdaki listede henüz bulunmayan YENİ parçaları listeye ekle.
        Fotoğraftaki tüm parçalar zaten listede mevcutsa boş liste [] döndür.

        Yeni parçalar için format:
        [
          {{
            "category": "Üst Giyim" | "Alt Giyim" | "Dış Giyim" | "Ayakkabı" | "Aksesuar",
            "item_name": "Kıyafetin kısa adı",
            "color": "Ana renk",
            "style": "Streetwear" | "Casual" | "Smart Casual" | "Spor",
            "season": "Yazlık" | "Kışlık" | "Mevsimlik",
            "fit": "Oversize" | "Regular" | "Slim Fit" | "Baggy"
          }}
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

def generate_outfit_alternatives(wardrobe_items: list, key: str, pinned_item_id: str = None, occasion: str = "Günlük", weather: str = "Ilıman"):
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
    Sen uzman bir stil danışmanısın. Kullanıcının gardırobundaki parçaları kullanarak 3 FARKLI KOMBİN ALTERNATİFİ hazırla.
    
    Mevcut Gardırop:
    {json.dumps(clean_items, ensure_ascii=False)}
    
    Kriterler:
    - Ortam/Etkinlik: {occasion}
    - Hava Durumu: {weather}
    - Sabit Parça ID'si: {pinned_item_id if pinned_item_id else "Yok"}
    
    JSON Formatı:
    {{
      "outfits": [
        {{
          "title": "Kombin Başlığı",
          "selected_item_ids": ["id_1", "id_2"],
          "explanation": "Kombin yorumu."
        }}
      ]
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

if "detected_items" not in st.session_state:
    st.session_state["detected_items"] = []
if "editing_id" not in st.session_state:
    st.session_state["editing_id"] = None

categories = ["Üst Giyim", "Alt Giyim", "Dış Giyim", "Ayakkabı", "Aksesuar"]
styles = ["Casual", "Streetwear", "Smart Casual", "Spor"]
seasons = ["Mevsimlik", "Yazlık", "Kışlık"]
fits = ["Regular", "Oversize", "Slim Fit", "Baggy"]

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
            
            existing_items = load_wardrobe()
            known_pool = list(existing_items)
            
            prog = st.progress(0)
            status = st.empty()
            
            for idx, f in enumerate(uploaded_files):
                status.text(f"Analiz ediliyor ve buluta yükleniyor ({idx + 1}/{len(uploaded_files)})...")
                img = Image.open(f)
                
                try:
                    # Görseli direkt Supabase Storage'a atıp URL'ini alıyoruz
                    public_img_url = upload_image_to_supabase(img)
                    
                    res_list = analyze_single_image(img, api_key, mode_str, known_pool)
                    for item in res_list:
                        item["temp_id"] = uuid.uuid4().hex[:10]
                        item["image_url"] = public_img_url
                        st.session_state["detected_items"].append(item)
                        known_pool.append(item)
                except Exception as e:
                    st.error(f"Hata: {e}")
                
                prog.progress((idx + 1) / len(uploaded_files))
            
            status.text("Analiz tamamlandı!")

    if len(st.session_state["detected_items"]) > 0:
        st.divider()
        st.subheader(f"Onay Bekleyen Parçalar ({len(st.session_state['detected_items'])} yeni parça)")

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
                    if itm.get("image_url"):
                        st.image(itm["image_url"], use_container_width=True)

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
                    "image_url": itm["image_url"]
                })
            save_to_wardrobe_batch(final_save_list)
            st.session_state["detected_items"] = []
            st.success(f"{len(final_save_list)} parça Supabase'e kaydedildi!")
            st.rerun()

with tab_wardrobe:
    st.subheader("Kayıtlı Parçalar")
    items = load_wardrobe()
    if not items:
        st.write("Henüz eklenmiş bir kıyafet yok.")
    else:
        for it in items:
            with st.container(border=True):
                col_img, col_info, col_actions = st.columns([1, 2, 0.8])
                with col_img:
                    if it.get("image_url"):
                        st.image(it["image_url"], use_container_width=True)
                    else:
                        st.caption("Görsel yok")
                with col_info:
                    st.markdown(f"**{it.get('item_name', '')}**")
                    st.caption(f"Kategori: {it.get('category', '')} | Renk: {it.get('color', '')}")
                    st.caption(f"Tarz: {it.get('style', '')} | Kalıp: {it.get('fit', '')} | Mevsim: {it.get('season', '')}")
                with col_actions:
                    if st.session_state["editing_id"] == it.get("id"):
                        if st.button("Vazgeç", key=f"cancel_{it.get('id')}"):
                            st.session_state["editing_id"] = None
                            st.rerun()
                    else:
                        if st.button("Düzenle", key=f"edit_{it.get('id')}"):
                            st.session_state["editing_id"] = it.get("id")
                            st.rerun()

                    if st.button("Sil", key=f"del_{it.get('id')}"):
                        delete_from_wardrobe(it.get("id"), it.get("image_url"))
                        if st.session_state["editing_id"] == it.get("id"):
                            st.session_state["editing_id"] = None
                        st.rerun()

                if st.session_state["editing_id"] == it.get("id"):
                    st.divider()
                    st.markdown("✏️ **Parçayı Güncelle**")
                    
                    cur_cat = it.get("category", "")
                    cur_cat_idx = categories.index(cur_cat) if cur_cat in categories else 0
                    cur_style = it.get("style", "")
                    cur_style_idx = styles.index(cur_style) if cur_style in styles else 0
                    cur_season = it.get("season", "")
                    cur_season_idx = seasons.index(cur_season) if cur_season in seasons else 0
                    cur_fit = it.get("fit", "")
                    cur_fit_idx = fits.index(cur_fit) if cur_fit in fits else 0

                    with st.form(f"edit_form_{it.get('id')}"):
                        new_name = st.text_input("İsim", value=it.get("item_name", ""))
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            new_cat = st.selectbox("Kategori", categories, index=cur_cat_idx)
                            new_color = st.text_input("Renk", value=it.get("color", ""))
                            new_fit = st.selectbox("Kalıp", fits, index=cur_fit_idx)
                        with ec2:
                            new_style = st.selectbox("Tarz", styles, index=cur_style_idx)
                            new_season = st.selectbox("Mevsim", seasons, index=cur_season_idx)

                        if st.form_submit_button("Güncelle ve Kaydet", type="primary"):
                            updated_item = {
                                "id": it.get("id"),
                                "item_name": new_name,
                                "category": new_cat,
                                "color": new_color,
                                "style": new_style,
                                "season": new_season,
                                "fit": new_fit
                            }
                            update_wardrobe_item(updated_item)
                            st.session_state["editing_id"] = None
                            st.success("Kıyafet bilgileri güncellendi!")
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

        if st.button("Kombin Alternatifleri Üret", type="primary"):
            with st.spinner("Gardırobun inceleniyor ve 3 farklı alternatif kombin oluşturuluyor..."):
                try:
                    outfit_data = generate_outfit_alternatives(items, api_key, pinned_id, occasion, weather)
                    outfit_list = outfit_data.get("outfits", [])

                    if not outfit_list:
                        st.warning("Uygun kombin kombinasyonu bulunamadı.")
                    else:
                        st.markdown("### Önerilen Kombin Alternatifleri")
                        
                        for idx, outf in enumerate(outfit_list):
                            title = outf.get("title", f"Alternatif {idx + 1}")
                            exp = outf.get("explanation", "")
                            selected_ids = outf.get("selected_item_ids", [])

                            with st.container(border=True):
                                st.markdown(f"#### 👔 {idx + 1}. {title}")
                                st.write(f"💡 **Stil Yorumu:** {exp}")

                                matched = [it for it in items if it.get("id") in selected_ids]
                                if matched:
                                    img_cols = st.columns(min(len(matched), 4))
                                    for c_idx, m_item in enumerate(matched):
                                        with img_cols[c_idx % 4]:
                                            if m_item.get("image_url"):
                                                st.image(m_item["image_url"], use_container_width=True)
                                            st.caption(f"**{m_item.get('item_name')}**")
                                            st.caption(f"{m_item.get('category')} - {m_item.get('color')}")
                except Exception as e:
                    st.error(f"Hata: {e}")
