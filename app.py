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
    item_to_remove = next((it for it in wardrobe if it["id"] == item_id), None)
    if item_to_remove:
        img_path = item_to_remove.get("image_path", "")
        if img_path and os.path.exists(img_path):
            try:
                os.remove(img_path)
            except Exception:
                pass
        updated = [it for it in wardrobe if it["id"] != item_id]
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(updated, f, ensure_ascii=False, indent=2)

def analyze_single_image(img: Image.Image, key: str, mode: str):
    client = genai.Client(api_key=key)
    
    if mode == "Tek Parça (Zemin/Askı)":
        prompt = """
        Görseldeki MERKEZDE yer alan ANA KIYAFETİ veya yatağa/zemine serilmiş tekil kıyafetleri analiz et.
        Arka plandaki zemin, mobilya, askılık gibi ilgisiz nesneleri KESİNLİKLE YOK SAY.
        Yanıtı STRICT şekilde bir JSON listesi olarak döndür:
        [
          {
            "category": "Üst Giyim" | "Alt Giyim" | "Dış Giyim" | "Ayakkabı" | "Aksesuar",
            "item_name": "Kıyafetin kısa adı (örn: Füme Kapüşonlu Sweatshirt)",
            "color": "Ana renk",
            "style": "Streetwear" | "Casual" | "Smart Casual" | "Spor",
            "season": "Yazlık" | "Kışlık" | "Mevsimlik",
            "fit": "Oversize" | "Regular" | "Slim Fit" | "Baggy"
          }
        ]
        """
    else:
        prompt = """
        Bu fotoğrafta kişinin ÜZERİNDE GİYİLİ olan kombindeki ana parçaları (Üst Giyim, Alt Giyim, Dış Giyim, Ayakkabı) tespit et.
        Arka plandaki oda eşyalarını, mobilyaları, kapıyı, aynayı ASLA kıyafet olarak ekleme. Sadece giyilen gerçek kıyafetleri al.
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
    Sen uzman bir stil danışmanısın. Kullanıcının gardırobundaki parçaları kullanarak uyumlu bir kombin yap.
    
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

# API Key Kontrolü (Önce Secrets, yoksa input)
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

if "batch_detected_items" not
