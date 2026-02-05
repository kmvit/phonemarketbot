import pandas as pd
import re
from db.models import get_db
from admin.discount import get_markup_amount, get_preorder_markup_amount

# Список всех поддерживаемых флагов стран
SUPPORTED_COUNTRY_FLAGS = [
    '🇨🇳', '🇺🇸', '🇮🇳', '🇹🇭', '🇦🇪', '🇵🇾', '🇨🇿', '🇩🇪',
    '🇯🇵', '🇻🇳', '🇸🇬', '🇨🇦', '🇧🇷', '🇦🇺', '🇸🇦', '🇭🇰',
    '🇶🇦', '🇰🇷', '🇬🇧', '🇮🇹', '🇿🇦', '🇮🇩', '🇷🇺', '🇪🇺',
    '🇲🇾', '🇰🇿', '🇨🇱'
]

# Маппинг инициалов стран к флагам и инициалам (ключ - инициалы, значение - флаг + инициалы)
COUNTRY_FLAG_MAPPING = {
    'CN': '🇨🇳 CN',
    'US': '🇺🇸 US',
    'AE': '🇦🇪 AE',
    'IN': '🇮🇳 IN',
    'TH': '🇹🇭 TH',
    'PY': '🇵🇾 PY',
    'CZ': '🇨🇿 CZ',
    'DE': '🇩🇪 DE',
    'JP': '🇯🇵 JP',
    'VN': '🇻🇳 VN',
    'SG': '🇸🇬 SG',
    'CA': '🇨🇦 CA',
    'BR': '🇧🇷 BR',
    'AU': '🇦🇺 AU',
    'SA': '🇸🇦 SA',
    'HK': '🇭🇰 HK',
    'QA': '🇶🇦 QA',
    'KR': '🇰🇷 KR',
    'GB': '🇬🇧 GB',
    'IT': '🇮🇹 IT',
    'ZA': '🇿🇦 ZA',
    'ID': '🇮🇩 ID',
}

def extract_memory(text):
    """Извлекает память из названия (64Gb, 128Gb, 256Gb, 512Gb, 1Tb, 2Tb, а также 4/128, 6/128, 8/128, или просто 128, 256, 512)"""
    if not text:
        return None
    
    # 1. Форматы типа 4/128, 6/128, 8/128 (RAM/Storage) - берем второе число (storage)
    pattern_ram_storage = re.search(r'(\d+)\s*/\s*(\d+)\s*(TB|Gb|GB|gb)?', text, re.IGNORECASE)
    if pattern_ram_storage:
        storage = pattern_ram_storage.group(2)
        unit = pattern_ram_storage.group(3) or 'Gb'
        # Нормализуем единицу измерения
        unit = 'TB' if unit.upper() == 'TB' else 'Gb'
        return f"{storage} {unit}"
    
    # 2. Форматы с единицами измерения (1TB, 2TB, 128Gb, 256Gb и т.д.)
    patterns = [
        r'(\d+)\s*TB',  # 1TB, 2TB, 4TB, 8TB
        r'(\d+)\s*Tb',  # 1Tb, 2Tb, 4Tb, 8Tb
        r'(\d+)\s*GB',  # 128GB, 256GB, 512GB
        r'(\d+)\s*Gb',  # 64Gb, 128Gb, 256Gb, 512Gb
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1)
            unit = 'TB' if 'TB' in pattern.upper() else 'Gb'
            return f"{value} {unit}"
    
    # 3. Просто цифры (128, 256, 512, 1024) - типичные значения памяти в ГБ
    # Ищем числа, которые обычно обозначают память (после названия модели, перед цветом)
    number_match = re.search(r'\b(128|256|512|1024|2048|4096)\b', text, re.IGNORECASE)
    if number_match:
        value = number_match.group(1)
        return f"{value} Gb"
    
    return None

def extract_color(text):
    """Извлекает цвет из названия (идет после памяти)"""
    if not text:
        return None
    
    # Список возможных цветов (добавлены цвета Google Pixel)
    # Важно: длинные названия должны быть первыми для правильного распознавания
    colors = [
        'Sorta Seafoam', 'Sorta Sage', 'Space Gray', 'Space Black', 'Rose Gold',
        'Jet Black', 'Light Gold', 'Cloud White', 'Sky Blue', 'Light Blush',
        'Pur Fog', 'Blue Ocean', 'Green Alpine', 'Black Ocean', 'Mil Lp',
        # Google Pixel цвета
        'Charcoal', 'Obsidian', 'Snow', 'Hazel', 'Porcelain', 'Porcelaine',
        'Peony', 'Lila',
        # Остальные цвета
        'Black', 'Blue', 'Red', 'Midnight', 'Starlight', 'Purple', 'Yellow', 
        'Green', 'Pink', 'White', 'Silver', 'Gold', 'Sp. Gray',
        'Teal', 'Ultramarine', 'Desert', 'Natural', 'Lavender', 'Sage', 'Mist Blue',
        'Orange', 'Star', 'Mid', 'Plum', 'Ink', 'Nat', 'Denim', 'Link'
    ]
    
    # Сортируем цвета по длине (от длинных к коротким), чтобы сначала находить составные цвета
    colors_sorted = sorted(colors, key=len, reverse=True)
    
    for color in colors_sorted:
        # Ищем цвет с учетом границ слов (чтобы не находить части других слов)
        pattern = r'\b' + re.escape(color) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            return color
    
    return None

def extract_category(product_name):
    """Определяет детальную категорию по названию товара (для сохранения в БД)"""
    if not product_name:
        return None
    
    # Убираем эмодзи
    clean_name = re.sub(r'[📱⌚🔳💻🖥🎧⌨️🖊]', '', product_name).strip()
    
    # iPhone
    if 'iPhone' in clean_name:
        if 'iPhone SE' in clean_name:
            return 'iPhone SE'
        elif re.search(r'iPhone\s+11\b', clean_name):
            return 'iPhone 11'
        elif re.search(r'iPhone\s+12\b', clean_name):
            return 'iPhone 12'
        elif re.search(r'iPhone\s+13\b', clean_name):
            return 'iPhone 13'
        elif re.search(r'iPhone\s+14\b', clean_name):
            return 'iPhone 14'
        elif re.search(r'iPhone\s+15\b', clean_name):
            return 'iPhone 15'
        elif re.search(r'iPhone\s+16\b', clean_name):
            return 'iPhone 16'
        # iPhone 17 модели - проверяем специфичные модели ПЕРЕД общим iPhone 17
        elif 'iPhone 17 Pro Max' in clean_name:
            return 'iPhone 17 Pro Max'
        elif 'iPhone 17 Pro' in clean_name:
            return 'iPhone 17 Pro'
        elif 'iPhone 17 Air' in clean_name:
            return 'iPhone 17 Air'
        elif re.search(r'iPhone\s+17\b', clean_name):
            return 'iPhone 17'
        elif 'iPhone Air' in clean_name:
            return 'iPhone Air'
        return 'iPhone SE'  # По умолчанию
    
    # iPad
    elif 'iPad' in clean_name:
        if 'iPad mini' in clean_name:
            return 'iPad mini'
        elif 'iPad Air' in clean_name:
            return 'iPad Air'
        elif 'iPad Pro' in clean_name:
            return 'iPad Pro'
        return 'iPad'
    
    # MacBook
    elif 'MacBook' in clean_name:
        if 'MacBook Air' in clean_name:
            return 'MacBook Air'
        elif 'MacBook Pro' in clean_name:
            return 'MacBook Pro'
        return 'MacBook Air'
    
    # Mac mini
    elif 'Mac mini' in clean_name or 'Mac Mini' in clean_name:
        return 'Mac mini'
    
    # Apple Watch (но не Samsung Galaxy Watch)
    elif ('Watch' in clean_name or 'Series' in clean_name) and 'Samsung' not in clean_name:
        return 'Apple Watch'
    
    # AirPods
    elif 'AirPods' in clean_name or 'Airpods' in clean_name:
        return 'AirPods'
    
    # Magic Keyboard
    elif 'Magic Keyboard' in clean_name:
        return 'Magic Keyboard'
    
    # Apple Pencil
    elif 'Pencil' in clean_name and 'Samsung' not in clean_name:
        return 'Apple Pencil'
    
    # Xiaomi
    elif 'Xiaomi' in clean_name:
        return 'Xiaomi'
    
    # Google Pixel
    elif 'Google Pixel' in clean_name or ('Pixel' in clean_name and 'Pixel' not in ['Pixelate', 'Pixelated']):
        # Определяем модель Pixel (проверяем от более специфичных к общим)
        if 'Pixel 10 Pro Fold' in clean_name:
            return 'Google Pixel 10 Pro Fold'
        elif 'Pixel 10 Pro XL' in clean_name:
            return 'Google Pixel 10 Pro XL'
        elif 'Pixel 10 Pro' in clean_name:
            return 'Google Pixel 10 Pro'
        elif re.search(r'Pixel\s+10\b', clean_name):
            return 'Google Pixel 10'
        elif 'Pixel 9 Pro Fold' in clean_name:
            return 'Google Pixel 9 Pro Fold'
        elif 'Pixel 9 Pro XL' in clean_name or 'Pixel 9 ProXL' in clean_name:
            return 'Google Pixel 9 Pro XL'
        elif 'Pixel 9 Pro' in clean_name:
            return 'Google Pixel 9 Pro'
        elif 'Pixel 9a' in clean_name or 'Pixel 9 a' in clean_name:
            return 'Google Pixel 9a'
        elif re.search(r'Pixel\s+9\b', clean_name):
            return 'Google Pixel 9'
        elif 'Pixel 8a' in clean_name or 'Pixel 8 a' in clean_name:
            return 'Google Pixel 8a'
        elif 'Pixel 8 Pro' in clean_name:
            return 'Google Pixel 8 Pro'
        elif re.search(r'Pixel\s+8\b', clean_name):
            return 'Google Pixel 8'
        elif 'Pixel 7 Pro' in clean_name:
            return 'Google Pixel 7 Pro'
        elif 'Pixel 7a' in clean_name or 'Pixel 7 a' in clean_name:
            return 'Google Pixel 7a'
        elif re.search(r'Pixel\s+7\b', clean_name):
            return 'Google Pixel 7'
        elif 'Pixel 6 Pro' in clean_name:
            return 'Google Pixel 6 Pro'
        elif 'Pixel 6a' in clean_name or 'Pixel 6 a' in clean_name:
            return 'Google Pixel 6a'
        elif re.search(r'Pixel\s+6\b', clean_name):
            return 'Google Pixel 6'
        elif re.search(r'Pixel\s+5\b', clean_name):
            return 'Google Pixel 5'
        elif re.search(r'Pixel\s+4\b', clean_name):
            return 'Google Pixel 4'
        return 'Google Pixel'  # По умолчанию
    
    # Yandex (Яндекс станции)
    elif 'Яндекс станция' in clean_name or 'Яндекс Станция' in clean_name:
        if 'Мини 3 Про' in clean_name or 'Мини 3 Про' in clean_name:
            return 'Yandex Станция Мини 3 Про'
        elif 'Стрит' in clean_name:
            return 'Yandex Станция Стрит'
        elif 'Лайт 2' in clean_name:
            return 'Yandex Станция Лайт 2'
        return 'Yandex Станция'
    
    # Meta Quest
    elif 'Meta Quest' in clean_name:
        if 'Quest 3S' in clean_name:
            return 'Meta Quest 3S'
        elif 'Quest 3' in clean_name:
            return 'Meta Quest 3'
        elif 'Quest 2' in clean_name:
            return 'Meta Quest 2'
        return 'Meta Quest'
    
    # Nintendo
    elif 'Nintendo Switch' in clean_name:
        if 'Switch Lite' in clean_name:
            return 'Nintendo Switch Lite'
        elif 'Switch OLED' in clean_name:
            return 'Nintendo Switch OLED'
        return 'Nintendo Switch'
    
    # Valve Steam Deck
    elif 'Steam Deck' in clean_name or 'Valve Steam Deck' in clean_name:
        if 'OLED' in clean_name:
            return 'Valve Steam Deck OLED'
        return 'Valve Steam Deck'
    
    # Sony
    elif 'Sony' in clean_name:
        if 'PlayStation 5' in clean_name or 'PS5' in clean_name:
            return 'Sony PlayStation 5'
        elif 'PlayStation 4' in clean_name or 'PS4' in clean_name:
            return 'Sony PlayStation 4'
        elif 'WH-1000XM' in clean_name:
            if 'WH-1000XM6' in clean_name:
                return 'Sony WH-1000XM6'
            elif 'WH-1000XM5' in clean_name:
                return 'Sony WH-1000XM5'
            elif 'WH-1000XM4' in clean_name:
                return 'Sony WH-1000XM4'
            return 'Sony WH-1000XM'
        return 'Sony'
    
    # GoPro
    elif 'GoPro' in clean_name:
        if re.search(r'GoPro\s+(\d+)', clean_name):
            match = re.search(r'GoPro\s+(\d+)', clean_name)
            return f'GoPro {match.group(1)}'
        return 'GoPro'
    
    # Insta360
    elif 'Insta360' in clean_name:
        if 'X5' in clean_name:
            return 'Insta360 X5'
        elif 'X4' in clean_name:
            return 'Insta360 X4'
        elif 'X3' in clean_name:
            return 'Insta360 X3'
        return 'Insta360'
    
    # Honor
    elif 'Honor' in clean_name:
        if 'X8b' in clean_name:
            return 'Honor X8b'
        elif 'X8' in clean_name:
            return 'Honor X8'
        return 'Honor'
    
    # Huawei
    elif 'Huawei' in clean_name:
        if 'Watch Fit' in clean_name:
            return 'Huawei Watch Fit'
        elif 'Watch' in clean_name:
            return 'Huawei Watch'
        return 'Huawei'
    
    # Apple (дополнительные товары)
    elif 'Apple' in clean_name:
        if 'iMac' in clean_name or 'imac' in clean_name:
            return 'Apple iMac'
        elif 'Power Adapter' in clean_name or 'USB-C' in clean_name:
            return 'Apple Аксессуары'
        return 'Apple'
    
    # Samsung (более детальная категоризация)
    elif 'Samsung' in clean_name:
        if 'Galaxy S25 Ultra' in clean_name:
            return 'Samsung Galaxy S25 Ultra'
        elif 'Galaxy S25+' in clean_name or 'Galaxy S25 +' in clean_name:
            return 'Samsung Galaxy S25+'
        elif 'Galaxy S25 Edge' in clean_name:
            return 'Samsung Galaxy S25 Edge'
        elif 'Galaxy S25' in clean_name:
            return 'Samsung Galaxy S25'
        elif 'Galaxy S24 Ultra' in clean_name:
            return 'Samsung Galaxy S24 Ultra'
        elif 'Galaxy S24+' in clean_name or 'Galaxy S24 +' in clean_name:
            return 'Samsung Galaxy S24+'
        elif 'Galaxy S24 FE' in clean_name:
            return 'Samsung Galaxy S24 FE'
        elif 'Galaxy S24' in clean_name:
            return 'Samsung Galaxy S24'
        elif 'Galaxy S23+' in clean_name or 'Galaxy S23 +' in clean_name:
            return 'Samsung Galaxy S23+'
        elif 'Galaxy S23' in clean_name:
            return 'Samsung Galaxy S23'
        elif 'Galaxy Z Fold7' in clean_name:
            return 'Samsung Galaxy Z Fold7'
        elif 'Galaxy Z Fold6' in clean_name:
            return 'Samsung Galaxy Z Fold6'
        elif 'Galaxy Z Fold' in clean_name:
            return 'Samsung Galaxy Z Fold'
        elif 'Galaxy Z Flip7' in clean_name:
            return 'Samsung Galaxy Z Flip7'
        elif 'Galaxy Z Flip6' in clean_name:
            return 'Samsung Galaxy Z Flip6'
        elif 'Galaxy Z Flip' in clean_name:
            return 'Samsung Galaxy Z Flip'
        elif 'Galaxy Tab' in clean_name:
            # Все планшеты Tab группируем в одну категорию
            return 'Samsung Galaxy Tab'
        elif 'Galaxy A' in clean_name:
            # Все модели A-серии группируем в одну категорию
            return 'Samsung Galaxy A'
        elif 'Galaxy Buds' in clean_name:
            return 'Samsung Galaxy Buds'
        elif 'Galaxy Watch' in clean_name:
            if 'Watch8 Classic' in clean_name:
                return 'Samsung Galaxy Watch8 Classic'
            elif 'Watch8' in clean_name:
                return 'Samsung Galaxy Watch8'
            return 'Samsung Galaxy Watch'
        elif 'Galaxy Fit' in clean_name:
            return 'Samsung Galaxy Fit'
        elif 'Galaxy Ring' in clean_name:
            return 'Samsung Galaxy Ring'
        elif 'Power Adapter' in clean_name:
            return 'Samsung Аксессуары'
        return 'Samsung'
    
    # Xiaomi / Redmi / POCO (расширенная категоризация)
    elif 'Xiaomi' in clean_name or 'Redmi' in clean_name or 'POCO' in clean_name or 'Xioami' in clean_name:
        if 'Xiaomi 15 Ultra' in clean_name:
            return 'Xiaomi 15 Ultra'
        elif 'Xiaomi 15T Pro' in clean_name:
            return 'Xiaomi 15T Pro'
        elif 'Xiaomi 15T' in clean_name:
            return 'Xiaomi 15T'
        elif 'Xiaomi 14T Pro' in clean_name:
            return 'Xiaomi 14T Pro'
        elif 'Xiaomi 14T' in clean_name:
            return 'Xiaomi 14T'
        elif 'POCO F7' in clean_name:
            return 'POCO F7'
        elif 'POCO F6 Pro' in clean_name:
            return 'POCO F6 Pro'
        elif 'POCO F6' in clean_name:
            return 'POCO F6'
        elif 'POCO X7 Pro' in clean_name:
            return 'POCO X7 Pro'
        elif 'POCO X7' in clean_name:
            return 'POCO X7'
        elif 'POCO M7 Pro' in clean_name:
            return 'POCO M7 Pro'
        elif 'POCO M7' in clean_name:
            return 'POCO M7'
        elif 'POCO M6' in clean_name:
            return 'POCO M6'
        elif 'POCO C85' in clean_name:
            return 'POCO C85'
        elif 'POCO C61' in clean_name:
            return 'POCO C61'
        elif 'POCO Pad' in clean_name:
            return 'POCO Pad'
        elif 'Redmi Note 14 Pro+' in clean_name or 'Redmi Note 14 Pro +' in clean_name:
            return 'Redmi Note 14 Pro+'
        elif 'Redmi Note 14 Pro' in clean_name:
            return 'Redmi Note 14 Pro'
        elif 'Redmi Note 14S' in clean_name:
            return 'Redmi Note 14S'
        elif 'Redmi Note 14' in clean_name:
            return 'Redmi Note 14'
        elif 'Redmi Note 13' in clean_name:
            return 'Redmi Note 13'
        elif 'Redmi 15' in clean_name:
            return 'Redmi 15'
        elif 'Redmi 13' in clean_name:
            return 'Redmi 13'
        elif 'Redmi Pad 7 Pro' in clean_name:
            return 'Redmi Pad 7 Pro'
        elif 'Redmi Pad Pro' in clean_name:
            return 'Redmi Pad Pro'
        elif 'Redmi Pad' in clean_name:
            return 'Redmi Pad'
        elif 'Xiaomi Pad 7 Pro' in clean_name or 'Xioami Pad 7 Pro' in clean_name:
            return 'Xiaomi Pad 7 Pro'
        elif 'Xiaomi Pad' in clean_name:
            return 'Xiaomi Pad'
        return 'Xiaomi'
    
    # Vivo
    elif 'Vivo' in clean_name:
        if 'Y29' in clean_name:
            return 'Vivo Y29'
        elif 'Y04' in clean_name:
            return 'Vivo Y04'
        elif 'Buds' in clean_name:
            return 'Vivo Buds'
        return 'Vivo'
    
    # Realme
    elif 'Realme' in clean_name or 'Realme' in clean_name:
        if 'C75' in clean_name:
            return 'Realme C75'
        elif re.search(r'Realme\s+(\d+)', clean_name):
            match = re.search(r'Realme\s+(\d+)', clean_name)
            return f'Realme {match.group(1)}'
        return 'Realme'
    
    # Garmin
    elif 'GARMIN' in clean_name or 'Garmin' in clean_name:
        if 'MARQ' in clean_name:
            return 'Garmin MARQ'
        return 'Garmin'
    
    # Dyson
    elif 'Dyson' in clean_name or 'DYSON' in clean_name:
        # Определяем модель Dyson
        if 'V15' in clean_name:
            return 'Dyson V15'
        elif 'V12' in clean_name:
            return 'Dyson V12'
        elif 'V11' in clean_name:
            return 'Dyson V11'
        elif 'V10' in clean_name:
            return 'Dyson V10'
        elif 'V8' in clean_name:
            return 'Dyson V8'
        elif 'Airwrap' in clean_name:
            return 'Dyson Airwrap'
        elif 'Supersonic' in clean_name:
            return 'Dyson Supersonic'
        elif 'Purifier' in clean_name:
            return 'Dyson Purifier'
        return 'Dyson'
    
    return 'Аксессуары'  # По умолчанию

def extract_country_flag_from_name(text):
    """Извлекает флаг страны из названия товара (флаг идет в конце после цвета)"""
    if not text:
        return None
    
    # Ищем флаг в тексте
    for flag in SUPPORTED_COUNTRY_FLAGS:
        if flag in text:
            return flag
    
    return None

def parse_country(country_str):
    """Парсит страну: извлекает инициалы и возвращает флаг + инициалы по маппингу"""
    if not country_str or pd.isna(country_str):
        return None
    
    country_str = str(country_str).strip()
    
    # Если уже есть флаг в правильном формате, возвращаем как есть
    if any(flag in country_str for flag in SUPPORTED_COUNTRY_FLAGS):
        return country_str
    
    # Извлекаем инициалы из строки (последние 2-3 символа после пробела или просто код)
    # Паттерны: "CN", "US", "🇨🇳 CN", "CN" и т.д.
    # Ищем код страны (2-3 заглавные буквы)
    code_match = re.search(r'\b([A-Z]{2,3})\b', country_str)
    if code_match:
        code = code_match.group(1)
        # Проверяем маппинг
        if code in COUNTRY_FLAG_MAPPING:
            return COUNTRY_FLAG_MAPPING[code]
    
    # Если не нашли код, возвращаем как есть или глобус
    if '🎧' in country_str or '🖊' in country_str:
        return country_str
    
    return None

def parse_price(price_str):
    """Парсит цену (убирает пробелы, конвертирует в число)"""
    if pd.isna(price_str):
        return None
    try:
        # Убираем пробелы и конвертируем
        price_clean = str(price_str).replace(' ', '').replace(',', '')
        return int(float(price_clean))
    except:
        return None

def load_price_from_excel(file_path, markup_amount=None, source='standard'):
    """Загружает прайс из Excel файла в базу данных"""
    if markup_amount is None:
        markup_amount = get_markup_amount()
    
    try:
        df = pd.read_excel(file_path)
        
        current_category = None
        current_product_name = None
        products_loaded = 0
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Очищаем старые данные только этого типа прайса перед загрузкой нового
            cur.execute("DELETE FROM products WHERE source = ?", (source,))
            
            for idx, row in df.iterrows():
                # Проверяем количество колонок в строке
                num_cols = len(row)
                if num_cols == 0:
                    continue
                
                # Первая колонка - название товара
                col1 = row.iloc[0] if num_cols > 0 else None
                
                if pd.notna(col1):
                    col1_str = str(col1)
                    # Проверяем, является ли это заголовком товара (с эмодзи)
                    if any(emoji in col1_str for emoji in ['📱', '⌚', '🔳', '💻', '🖥', '🎧', '⌨️', '🖊']):
                        # Это новый товар
                        current_product_name = col1_str
                        current_category = extract_category(col1_str)
                        continue
                
                # Если есть категория и название товара, обрабатываем строку с данными
                if current_category and current_product_name:
                    # Безопасно извлекаем данные из строки с проверкой индексов
                    model_code = None
                    country_flag = None
                    stock = None
                    price_str = None
                    quantity = None
                    
                    if num_cols > 0:
                        model_code = str(row.iloc[0]) if pd.notna(row.iloc[0]) else None
                    if num_cols > 1:
                        # Колонка B (индекс 1) - страна с флагом
                        country_flag_raw = row.iloc[1]
                        if pd.notna(country_flag_raw):
                            country_flag = str(country_flag_raw).strip()
                        else:
                            country_flag = None
                    if num_cols > 2:
                        stock = str(row.iloc[2]) if pd.notna(row.iloc[2]) else None
                    if num_cols > 3:
                        # Колонка D (индекс 3) - цена
                        price_str = row.iloc[3] if pd.notna(row.iloc[3]) else None
                    if num_cols > 4:
                        # Колонка E (индекс 4) - количество
                        quantity = row.iloc[4] if pd.notna(row.iloc[4]) else None
                    
                    # Проверяем, что это не пустая строка и есть модель
                    if not model_code or model_code == 'nan' or model_code == 'None':
                        continue
                    
                    # Извлекаем данные
                    memory = extract_memory(current_product_name)
                    color = extract_color(current_product_name)
                    country = parse_country(country_flag)
                    price = parse_price(price_str)
                    
                    if price is None:
                        continue
                    
                    # Сохраняем базовую цену БЕЗ наценки (наценка будет применяться при отображении)
                    # Формируем полное название товара
                    full_name = re.sub(r'[📱⌚🔳💻🖥🎧⌨️🖊]', '', current_product_name).strip()
                    
                    # Сохраняем в БД
                    try:
                        cur.execute("""
                            INSERT INTO products (category, name, memory, color, country, price, source)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (current_category, full_name, memory, color, country, price, source))
                        
                        products_loaded += 1
                    except Exception as e:
                        # Пропускаем проблемные записи, но продолжаем обработку
                        continue
            
            conn.commit()
        
        return products_loaded
    
    except Exception as e:
        # Упрощенное сообщение об ошибке
        error_msg = str(e)
        if "out-of-bounds" in error_msg:
            error_msg = "Ошибка: файл имеет неожиданную структуру. Проверьте, что файл содержит все необходимые колонки."
        raise Exception(f"Ошибка при загрузке прайса: {error_msg}")

def detect_file_format(file_path):
    """
    Определяет формат файла Excel.
    Возвращает 'simple' если 2 столбца, 'standard' если больше столбцов.
    """
    try:
        df = pd.read_excel(file_path, nrows=10)  # Читаем первые 10 строк для анализа
        num_cols = len(df.columns)
        
        # Если 2 столбца - простой формат (название, цена)
        if num_cols == 2:
            return 'simple'
        # Иначе - стандартный формат
        return 'standard'
    except Exception:
        # По умолчанию пытаемся стандартный формат
        return 'standard'

def extract_categories_from_excel(file_path):
    """
    Извлекает категории из Excel файла.
    Категории - это строки без цены, заканчивающиеся двоеточием или просто заголовки.
    Возвращает словарь: {номер_строки_категории: название_категории_без_двоеточия}
    """
    try:
        df = pd.read_excel(file_path)
        categories = {}
        
        for idx, row in df.iterrows():
            col1 = row.iloc[0] if pd.notna(row.iloc[0]) else None
            col2 = row.iloc[1] if len(row) > 1 and pd.notna(row.iloc[1]) else None
            
            if not col1:
                continue
            
            col1_str = str(col1).strip()
            
            # Проверяем: есть название, нет цены (или цена пустая/NaN)
            price_is_empty = True
            if col2 is not None:
                try:
                    # Пытаемся преобразовать в число
                    float(str(col2).replace(' ', '').replace(',', ''))
                    price_is_empty = False
                except (ValueError, AttributeError):
                    price_is_empty = True
            
            # Категория может быть:
            # 1. С двоеточием в конце (например, "Honor:")
            # 2. Просто заголовок без двоеточия, но без цены
            # 3. Заголовок в верхнем регистре (например, "HONOR", "DYSON")
            # 4. Любая строка без цены, которая не является товаром (например, "Apple iPhone 17 256GB")
            is_category = False
            
            if ':' in col1_str:
                # Есть двоеточие - это категория
                is_category = True
                category_name = col1_str.replace(':', '').strip()
            elif price_is_empty and col1_str:
                # Нет цены и есть текст - проверяем, не является ли это категорией
                col1_upper = col1_str.upper()
                
                # Проверяем, является ли это известным брендом (в верхнем регистре или смешанном)
                known_brands = ['HONOR', 'DYSON', 'HUAWEI', 'VIVO', 'REALME', 'XIAOMI', 
                               'SAMSUNG', 'APPLE', 'GOOGLE', 'META', 'NINTENDO', 'VALVE',
                               'SONY', 'GOPRO', 'INSTA360', 'GARMIN', 'YANDEX', 'REDMI', 'POCO']
                
                # Если это известный бренд - точно категория
                if col1_upper in known_brands or any(brand in col1_upper for brand in known_brands):
                    is_category = True
                    category_name = col1_str.strip()
                # Если строка без цены и не содержит признаков товара (нет типичных паттернов товара),
                # то это может быть подкатегория
                elif not _looks_like_product(col1_str):
                    # Строка без цены и не похожа на товар - это категория/подкатегория
                    is_category = True
                    category_name = col1_str.strip()
            
            if is_category and category_name:
                # Нормализуем название категории (приводим к правильному регистру)
                category_name = normalize_category_name(category_name)
                categories[idx] = category_name
                
        return categories
    except Exception as e:
        print(f"Ошибка при извлечении категорий: {e}")
        return {}

def _looks_like_product(text):
    """
    Проверяет, похожа ли строка на товар (а не на категорию).
    Товары обычно содержат конкретные характеристики: цвет, память, флаги стран и т.д.
    """
    if not text:
        return False
    
    text_upper = text.upper()
    
    # Признаки товара:
    # 1. Содержит флаги стран
    country_flags = ['🇨🇳', '🇺🇸', '🇮🇳', '🇹🇭', '🇦🇪', '🇵🇾', '🇨🇿', '🇩🇪',
                     '🇯🇵', '🇻🇳', '🇸🇬', '🇨🇦', '🇧🇷', '🇦🇺', '🇸🇦', '🇭🇰']
    if any(flag in text for flag in country_flags):
        return True
    
    # 2. Содержит типичные цвета товаров (после названия модели)
    # Но только если это не просто название модели с цветом как категория
    # Проверяем, есть ли цвет в конце строки (признак товара)
    colors = ['BLACK', 'BLUE', 'RED', 'MIDNIGHT', 'STARLIGHT', 'PURPLE', 'YELLOW', 
              'GREEN', 'PINK', 'WHITE', 'SILVER', 'GOLD', 'ORANGE', 'LAVENDER', 'SAGE']
    # Если цвет в конце и есть другие признаки товара - это товар
    for color in colors:
        if text_upper.endswith(color) or text_upper.endswith(' ' + color):
            # Проверяем, есть ли еще признаки товара (память, eSim и т.д.)
            if re.search(r'\d+\s*(GB|TB)', text_upper) or 'ESIM' in text_upper or 'SIM' in text_upper:
                return True
    
    # 3. Содержит типы SIM (eSim, Sim + eSIM) - признак товара
    if re.search(r'\b(ESIM|SIM\s*\+\s*ESIM)\b', text_upper):
        return True
    
    # 4. Содержит конкретную память с цветом в конце - признак товара
    # Например: "Apple iPhone 17 256GB Black" - товар
    # А "Apple iPhone 17 256GB" - может быть категорией
    if re.search(r'\d+\s*(GB|TB)\s+[A-Z]+\s*$', text_upper):
        return True
    
    # Если не похоже на товар - это категория
    return False

def normalize_category_name(category_name):
    """Нормализует название категории (приводит к правильному регистру)"""
    if not category_name:
        return category_name
    
    category_upper = category_name.upper()
    
    # Маппинг известных брендов к правильному написанию
    brand_mapping = {
        'HONOR': 'Honor',
        'DYSON': 'Dyson',
        'HUAWEI': 'Huawei',
        'VIVO': 'Vivo',
        'REALME': 'Realme',
        'XIAOMI': 'Xiaomi',
        'SAMSUNG': 'Samsung',
        'APPLE': 'Apple',
        'GOOGLE': 'Google Pixel',
        'META': 'Meta Quest',
        'NINTENDO': 'Nintendo',
        'VALVE': 'Valve',
        'SONY': 'Sony',
        'GOPRO': 'GoPro',
        'INSTA360': 'Insta360',
        'GARMIN': 'Garmin',
        'YANDEX': 'Yandex',
        'REDMI': 'Redmi',
        'POCO': 'POCO'
    }
    
    # Проверяем точное совпадение
    if category_upper in brand_mapping:
        return brand_mapping[category_upper]
    
    # Проверяем частичное совпадение
    for brand_upper, brand_normalized in brand_mapping.items():
        if brand_upper in category_upper:
            # Заменяем бренд на нормализованный вариант
            return category_upper.replace(brand_upper, brand_normalized).title()
    
    # Если не нашли, возвращаем с правильным регистром (первая буква заглавная)
    return category_name.strip().title()

def get_category_for_product_row(row_idx, categories_map):
    """
    Определяет категорию для товара на основе его позиции в файле.
    Ищет ближайший заголовок категории выше текущей строки.
    Возвращает самую ближайшую категорию (подкатегорию), если есть иерархия.
    """
    current_category = None
    
    # Ищем ближайшую категорию выше текущей строки
    # Берем самую последнюю (ближайшую) категорию перед товаром
    for cat_row_idx in sorted(categories_map.keys(), reverse=True):
        if cat_row_idx < row_idx:
            current_category = categories_map[cat_row_idx]
            break  # Берем самую ближайшую категорию
            
    return current_category

def load_price_from_excel_simple_format(file_path, markup_amount=None, source='simple'):
    """
    Загружает прайс из Excel файла с простым форматом: два столбца (название, цена).
    Теперь поддерживает динамическое извлечение категорий из заголовков в файле.
    """
    if markup_amount is None:
        markup_amount = get_markup_amount()
    
    try:
        df = pd.read_excel(file_path)
        
        # Сначала извлекаем все категории из файла
        categories_map = extract_categories_from_excel(file_path)
        print(f"Найдено категорий в файле: {len(categories_map)}")
        for row_idx, cat_name in categories_map.items():
            print(f"  Строка {row_idx}: {cat_name}")
        
        products_loaded = 0
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Очищаем старые данные только этого типа прайса перед загрузкой нового
            cur.execute("DELETE FROM products WHERE source = ?", (source,))
            
            for idx, row in df.iterrows():
                # Проверяем количество колонок в строке
                num_cols = len(row)
                if num_cols < 2:
                    continue
                
                # Первая колонка - название товара
                product_name = row.iloc[0] if pd.notna(row.iloc[0]) else None
                
                # Вторая колонка - цена
                price_str = row.iloc[1] if pd.notna(row.iloc[1]) else None
                
                if not product_name or pd.isna(product_name):
                    continue
                
                product_name_str = str(product_name).strip()
                
                # Пропускаем пустые строки и строки с "None" или "nan"
                if not product_name_str or product_name_str.lower() in ('nan', 'none'):
                    continue
                
                # Пропускаем заголовки категорий (строки с двоеточием без цены)
                price_is_none = pd.isna(price_str) if price_str is not None else True
                if price_str is not None and str(price_str).strip().lower() in ('nan', 'none'):
                    price_is_none = True
                if ':' in product_name_str and price_is_none:
                    continue  # Это заголовок категории, пропускаем
                
                # Определяем категорию для этого товара на основе позиции в файле
                category = get_category_for_product_row(idx, categories_map)
                
                if not category:
                    # Если категория не найдена, используем старый метод как fallback
                    category = extract_category(product_name_str)
                else:
                    # Если категория найдена из заголовка, но она не распознается extract_category,
                    # попытаемся нормализовать её или использовать как есть
                    # Проверяем, что категория из заголовка корректна
                    normalized_category = extract_category(category)
                    # Если extract_category вернул другую категорию, используем её (она более точная)
                    # Но если вернул None или 'Аксессуары', используем категорию из заголовка
                    if normalized_category and normalized_category != 'Аксессуары':
                        category = normalized_category
                    # Иначе оставляем категорию из заголовка как есть
                
                # Извлекаем данные из названия
                memory = extract_memory(product_name_str)
                color = extract_color(product_name_str)
                country_flag = extract_country_flag_from_name(product_name_str)
                
                # Если флаг не найден, используем None
                if not country_flag:
                    country = None
                else:
                    country = country_flag
                
                # Парсим цену
                price = parse_price(price_str)
                
                if price is None:
                    continue
                
                # Сохраняем базовую цену БЕЗ наценки (наценка будет применяться при отображении)
                # Убираем флаг и лишние пробелы из названия для сохранения
                # Оставляем только название модели с памятью и цветом (без флага)
                clean_name = product_name_str
                # Убираем флаги
                for flag in SUPPORTED_COUNTRY_FLAGS:
                    clean_name = clean_name.replace(flag, '')
                clean_name = re.sub(r'\s+', ' ', clean_name).strip()
                
                # Сохраняем в БД
                try:
                    cur.execute("""
                        INSERT INTO products (category, name, memory, color, country, price, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (category, clean_name, memory, color, country, price, source))
                    
                    products_loaded += 1
                except Exception as e:
                    # Пропускаем проблемные записи, но продолжаем обработку
                    continue
            
            conn.commit()
        
        return products_loaded
    
    except Exception as e:
        error_msg = str(e)
        raise Exception(f"Ошибка при загрузке прайса: {error_msg}")

def load_price_from_excel_auto(file_path, markup_amount=None, source='standard'):
    """
    Автоматически определяет формат файла и загружает прайс.
    Поддерживает два формата:
    1. Стандартный (много столбцов с заголовками)
    2. Простой (2 столбца: название с памятью/цветом/флагом, цена)
    """
    file_format = detect_file_format(file_path)
    
    if file_format == 'simple':
        # Для простого формата используем source как есть (может быть 'preorder' или 'simple')
        return load_price_from_excel_simple_format(file_path, markup_amount, source)
    else:
        # Для стандартного формата используем source как есть (может быть 'preorder' или 'standard')
        return load_price_from_excel(file_path, markup_amount, source)

def load_preorder_price_from_excel(file_path, markup_amount=None):
    """Загружает прайс предзаказа из Excel файла в таблицу preorder_products"""
    if markup_amount is None:
        markup_amount = get_preorder_markup_amount()
    
    try:
        df = pd.read_excel(file_path)
        
        current_category = None
        current_product_name = None
        products_loaded = 0
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Очищаем старые данные предзаказа перед загрузкой нового
            cur.execute("DELETE FROM preorder_products")
            
            for idx, row in df.iterrows():
                # Проверяем количество колонок в строке
                num_cols = len(row)
                if num_cols == 0:
                    continue
                
                # Первая колонка - название товара
                col1 = row.iloc[0] if num_cols > 0 else None
                
                if pd.notna(col1):
                    col1_str = str(col1)
                    # Проверяем, является ли это заголовком товара (с эмодзи)
                    if any(emoji in col1_str for emoji in ['📱', '⌚', '🔳', '💻', '🖥', '🎧', '⌨️', '🖊']):
                        # Это новый товар
                        current_product_name = col1_str
                        current_category = extract_category(col1_str)
                        continue
                
                # Если есть категория и название товара, обрабатываем строку с данными
                if current_category and current_product_name:
                    # Безопасно извлекаем данные из строки с проверкой индексов
                    model_code = None
                    country_flag = None
                    stock = None
                    price_str = None
                    quantity = None
                    
                    if num_cols > 0:
                        model_code = str(row.iloc[0]) if pd.notna(row.iloc[0]) else None
                    if num_cols > 1:
                        # Колонка B (индекс 1) - страна с флагом
                        country_flag_raw = row.iloc[1]
                        if pd.notna(country_flag_raw):
                            country_flag = str(country_flag_raw).strip()
                        else:
                            country_flag = None
                    if num_cols > 2:
                        stock = str(row.iloc[2]) if pd.notna(row.iloc[2]) else None
                    if num_cols > 3:
                        # Колонка D (индекс 3) - цена
                        price_str = row.iloc[3] if pd.notna(row.iloc[3]) else None
                    if num_cols > 4:
                        # Колонка E (индекс 4) - количество
                        quantity = row.iloc[4] if pd.notna(row.iloc[4]) else None
                    
                    # Проверяем, что это не пустая строка и есть модель
                    if not model_code or model_code == 'nan' or model_code == 'None':
                        continue
                    
                    # Извлекаем данные
                    memory = extract_memory(current_product_name)
                    color = extract_color(current_product_name)
                    country = parse_country(country_flag)
                    price = parse_price(price_str)
                    
                    if price is None:
                        continue
                    
                    # Сохраняем базовую цену БЕЗ наценки (наценка будет применяться при отображении)
                    # Формируем полное название товара
                    full_name = re.sub(r'[📱⌚🔳💻🖥🎧⌨️🖊]', '', current_product_name).strip()
                    
                    # Сохраняем в БД предзаказа
                    try:
                        cur.execute("""
                            INSERT INTO preorder_products (category, name, memory, color, country, price)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (current_category, full_name, memory, color, country, price))
                        
                        products_loaded += 1
                    except Exception as e:
                        # Пропускаем проблемные записи, но продолжаем обработку
                        continue
            
            conn.commit()
        
        return products_loaded
    
    except Exception as e:
        # Упрощенное сообщение об ошибке
        error_msg = str(e)
        if "out-of-bounds" in error_msg:
            error_msg = "Ошибка: файл имеет неожиданную структуру. Проверьте, что файл содержит все необходимые колонки."
        raise Exception(f"Ошибка при загрузке прайса предзаказа: {error_msg}")

def load_preorder_price_from_excel_simple_format(file_path, markup_amount=None):
    """
    Загружает прайс предзаказа из Excel файла с простым форматом: два столбца (название, цена).
    В названии заложены: память, цвет и страна (флаг).
    """
    if markup_amount is None:
        markup_amount = get_preorder_markup_amount()
    
    try:
        df = pd.read_excel(file_path)
        
        products_loaded = 0
        
        # Список заголовков категорий, которые нужно пропускать
        category_headers = ['YANDEX', 'META', 'NINTENDO', 'VALVE', 'SONY', 'GOOGLE', 
                           'GOPRO', 'INSTA360', 'HONOR', 'HUAWEI', 'APPLE', 'SAMSUNG',
                           'XIAOMI', 'VIVO', 'REALME', 'GARMIN']
        
        with get_db() as conn:
            cur = conn.cursor()
            
            # Очищаем старые данные предзаказа перед загрузкой нового
            cur.execute("DELETE FROM preorder_products")
            
            for idx, row in df.iterrows():
                # Проверяем количество колонок в строке
                num_cols = len(row)
                if num_cols < 2:
                    continue
                
                # Первая колонка - название товара (с памятью, цветом и флагом страны)
                product_name = row.iloc[0] if pd.notna(row.iloc[0]) else None
                
                # Вторая колонка - цена
                price_str = row.iloc[1] if pd.notna(row.iloc[1]) else None
                
                if not product_name or pd.isna(product_name):
                    continue
                
                product_name_str = str(product_name).strip()
                
                # Пропускаем пустые строки и строки с "None" или "nan"
                if not product_name_str or product_name_str.lower() in ('nan', 'none'):
                    continue
                
                # Пропускаем заголовки категорий (все заглавные буквы, без цены)
                price_is_none = pd.isna(price_str) if price_str is not None else True
                if price_str is not None and str(price_str).strip().lower() in ('nan', 'none'):
                    price_is_none = True
                if product_name_str.upper() in category_headers and price_is_none:
                    continue
                
                # Извлекаем данные из названия
                memory = extract_memory(product_name_str)
                color = extract_color(product_name_str)
                country_flag = extract_country_flag_from_name(product_name_str)
                
                # Если флаг не найден, используем None
                if not country_flag:
                    country = None
                else:
                    country = country_flag
                
                # Определяем категорию
                category = extract_category(product_name_str)
                
                # Парсим цену
                price = parse_price(price_str)
                
                if price is None:
                    continue
                
                # Сохраняем базовую цену БЕЗ наценки (наценка будет применяться при отображении)
                # Убираем флаг и лишние пробелы из названия для сохранения
                # Оставляем только название модели с памятью и цветом (без флага)
                clean_name = product_name_str
                # Убираем флаги
                for flag in SUPPORTED_COUNTRY_FLAGS:
                    clean_name = clean_name.replace(flag, '')
                clean_name = re.sub(r'\s+', ' ', clean_name).strip()
                
                # Сохраняем в БД предзаказа
                try:
                    cur.execute("""
                        INSERT INTO preorder_products (category, name, memory, color, country, price)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (category, clean_name, memory, color, country, price))
                    
                    products_loaded += 1
                except Exception as e:
                    # Пропускаем проблемные записи, но продолжаем обработку
                    continue
            
            conn.commit()
        
        return products_loaded
    
    except Exception as e:
        error_msg = str(e)
        raise Exception(f"Ошибка при загрузке прайса предзаказа: {error_msg}")

def load_preorder_price_from_excel_auto(file_path, markup_amount=None):
    """
    Автоматически определяет формат файла и загружает прайс предзаказа.
    Поддерживает два формата:
    1. Стандартный (много столбцов с заголовками)
    2. Простой (2 столбца: название с памятью/цветом/флагом, цена)
    """
    file_format = detect_file_format(file_path)
    
    if file_format == 'simple':
        return load_preorder_price_from_excel_simple_format(file_path, markup_amount)
    else:
        return load_preorder_price_from_excel(file_path, markup_amount)

