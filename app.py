import os
import json
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

# ==================== 1. تحميل القرآن والتفسير ====================
QURAN_PATH = 'quran.json'
TAFSIR_PATH = 'tafsir_saadi.json'

def load_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return []

quran_data = load_json(QURAN_PATH)
tafsir_list = load_json(TAFSIR_PATH)

surahs_list = []
quran_ayahs_map = {}

if isinstance(quran_data, list):
    for surah in quran_data:
        surah_num = surah.get('id')
        surah_name = surah.get('name', '')
        surahs_list.append({'id': surah_num, 'name': surah_name})
        for ayah in surah.get('verses', []):
            ayah_num = ayah.get('id')
            quran_ayahs_map[(surah_num, ayah_num)] = ayah.get('text', '')

print(f"تم تحميل {len(surahs_list)} سورة و {len(quran_ayahs_map)} آية.")

tafsir_map = {}
surah_names_ar = [s['name'] for s in surahs_list]

if isinstance(tafsir_list, list) and tafsir_list and isinstance(tafsir_list[0], dict) and 'ayahs' in tafsir_list[0]:
    for surah_obj in tafsir_list:
        surah_name = surah_obj.get('surah_name', '').strip()
        surah_num = None
        for i, name in enumerate(surah_names_ar, start=1):
            if name == surah_name or surah_name in name or name in surah_name:
                surah_num = i
                break
        if not surah_num:
            continue
        for ayah in surah_obj.get('ayahs', []):
            ayah_num = ayah.get('number', 0)
            tafsir_map[(surah_num, ayah_num)] = ayah.get('text', '')

print(f"تم تحميل {len(tafsir_map)} تفسير.")

# ==================== 2. الكتب ====================
BOOKS = {
    'bukhari': 'صحيح البخاري',
    'muslim': 'صحيح مسلم',
    'abudawud': 'سنن أبي داود',
    'tirmidhi': 'جامع الترمذي',
    'nasai': 'سنن النسائي',
    'ibnmajah': 'سنن ابن ماجه',
    'malik': 'موطأ مالك',
    'ahmed': 'مسند أحمد',
    'darimi': 'سنن الدارمي',
    'riyad_assalihin': 'رياض الصالحين',
    'aladab_almufrad': 'الأدب المفرد',
    'bulugh_almaram': 'بلوغ المرام',
    'mishkat_almasabih': 'مشكاة المصابيح',
    'shamail_muhammadiyah': 'الشمائل المحمدية'
}

loaded_books_cache = {}

def load_hadith_book(book_id):
    if book_id in loaded_books_cache:
        return loaded_books_cache[book_id]

    all_hadiths = []
    single_file_path = f'{book_id}.json'
    if os.path.exists(single_file_path):
        data = load_json(single_file_path)
        all_hadiths = data.get('hadiths', [])
    elif os.path.isdir(book_id):
        folder_path = book_id
        files = os.listdir(folder_path)
        files = sorted(
            [f for f in files if f.endswith('.json')],
            key=lambda x: int(x.split('.')[0]) if x.split('.')[0].isdigit() else 999
        )
        for filename in files:
            filepath = os.path.join(folder_path, filename)
            data = load_json(filepath)
            all_hadiths.extend(data.get('hadiths', []))

    loaded_books_cache[book_id] = all_hadiths
    return all_hadiths

# ==================== 3. المسارات ====================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, books=BOOKS, surahs=surahs_list)

@app.route('/api/hadith')
def get_hadith():
    book_id = request.args.get('book', 'bukhari')
    index = request.args.get('index', 0, type=int)

    if book_id not in BOOKS:
        return jsonify({'error': 'كتاب غير موجود'})

    hadiths = load_hadith_book(book_id)
    if not hadiths or index < 0 or index >= len(hadiths):
        return jsonify({'error': 'حديث غير موجود'})

    h = hadiths[index]
    return jsonify({
        'index': index,
        'total': len(hadiths),
        'id': h.get('idInBook', index + 1),
        'text': h.get('arabic', ''),
        'narrator': h.get('english', {}).get('narrator', '')
    })

@app.route('/api/surah')
def get_surah():
    surah_num = request.args.get('surah', 1, type=int)
    ayahs = []
    for (s, a), text in sorted(quran_ayahs_map.items()):
        if s == surah_num:
            ayahs.append({
                'ayah': a,
                'text': text,
                'tafsir': tafsir_map.get((s, a), '')
            })
    surah_name = next((s['name'] for s in surahs_list if s['id'] == surah_num), '')
    return jsonify({
        'surah': surah_num,
        'name': surah_name,
        'ayahs': ayahs
    })

@app.route('/api/search')
def search():
    book_id = request.args.get('book', 'bukhari')
    query = request.args.get('query', '').strip()

    if not query:
        return jsonify([])

    if book_id not in BOOKS:
        return jsonify([])

    hadiths = load_hadith_book(book_id)
    results = []
    for i, h in enumerate(hadiths):
        arabic_text = h.get('arabic', '')
        if query in arabic_text:
            results.append({
                'index': i,
                'id': h.get('idInBook', i + 1),
                'text': arabic_text,
                'narrator': h.get('english', {}).get('narrator', '')
            })
            if len(results) >= 100:
                break

    return jsonify(results)

# ==================== 4. HTML ====================
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>الموسوعة الإسلامية الشاملة</title>
    <script src="https://unpkg.com/adhan/lib/bundles/adhan.umd.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        :root {
            --main-green: #1a4d2e;
            --light-green: #e8f5e9;
            --gold: #c9a961;
            --bg: #f0f0e8;
            --text-dark: #1a1a1a;
        }
        body {
            font-family: 'Traditional Arabic', 'Segoe UI', Tahoma, sans-serif;
            background: var(--bg);
            min-height: 100vh;
            color: var(--text-dark);
        }
        .header {
            background: var(--main-green);
            color: white;
            padding: 15px 20px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .header h1 {
            font-size: 26px;
            color: var(--gold);
            margin-bottom: 12px;
        }
        .top-actions {
            display: flex;
            justify-content: center;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 12px;
        }
        .top-btn {
            background: #2d6a4f;
            color: white;
            border: 1px solid rgba(255,255,255,0.2);
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 13px;
            cursor: pointer;
            font-family: inherit;
            transition: all 0.2s;
        }
        .top-btn:hover { background: #40916c; }

        .info-bar {
            background: #2d6a4f;
            color: white;
            padding: 12px 20px;
            border-bottom: 2px solid var(--gold);
            text-align: center;
        }
        .info-time {
            font-size: 28px;
            font-weight: bold;
            color: var(--gold);
            margin-bottom: 5px;
        }
        .info-date {
            font-size: 14px;
            margin-bottom: 10px;
            line-height: 1.6;
        }
        .prayer-times {
            display: flex;
            justify-content: center;
            gap: 15px;
            flex-wrap: wrap;
            font-size: 14px;
        }
        .prayer-item {
            background: rgba(255,255,255,0.1);
            padding: 5px 12px;
            border-radius: 20px;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .prayer-item .name { color: var(--gold); font-weight: bold; }
        .prayer-item .time { font-weight: bold; }
        .location-info {
            font-size: 13px;
            color: #c9e6d0;
            margin-top: 5px;
        }

        .search-area {
            display: flex;
            gap: 6px;
            max-width: 900px;
            margin: 12px auto 0;
            align-items: center;
        }
        .search-area input {
            flex: 1;
            padding: 10px 15px;
            border-radius: 8px;
            border: none;
            font-size: 15px;
            font-family: inherit;
        }
        .search-area button {
            background: var(--gold);
            border: none;
            padding: 10px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
        }
        .search-area button:hover { background: #b8935a; }

        .text-controls {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            padding: 10px;
            background: #f5f5f0;
            border-bottom: 2px solid #ddd;
            flex-wrap: wrap;
        }
        .text-controls button {
            background: var(--main-green);
            color: white;
            border: none;
            padding: 6px 14px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-family: inherit;
        }
        .text-controls .size-display {
            background: white;
            padding: 6px 14px;
            border-radius: 6px;
            font-weight: bold;
            border: 1px solid #ccc;
            min-width: 40px;
            text-align: center;
        }

        .books-bar {
            background: var(--main-green);
            padding: 10px;
            overflow-x: auto;
            white-space: nowrap;
            scrollbar-width: thin;
        }
        .books-bar::-webkit-scrollbar { height: 8px; }
        .books-bar::-webkit-scrollbar-thumb { background: var(--gold); border-radius: 4px; }
        .book-btn {
            display: inline-block;
            background: white;
            color: var(--main-green);
            border: 2px solid white;
            padding: 8px 16px;
            margin: 0 4px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            font-family: inherit;
            transition: all 0.2s;
        }
        .book-btn:hover { background: #e8f5e9; }
        .book-btn.active {
            background: var(--gold);
            color: white;
            border-color: var(--gold);
        }

        .content-area {
            max-width: 1000px;
            margin: 20px auto;
            padding: 0 15px;
        }
        .hadith-card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            border: 2px solid #d4d4d0;
            margin-bottom: 20px;
        }
        .hadith-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--light-green);
            padding-bottom: 10px;
            margin-bottom: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }
        .hadith-book-name {
            color: var(--main-green);
            font-size: 18px;
            font-weight: bold;
        }
        .hadith-number {
            background: var(--main-green);
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: bold;
        }
        .narrator {
            color: #b8860b;
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 15px;
            padding: 8px 12px;
            background: #fdf6e3;
            border-right: 4px solid var(--gold);
            border-radius: 4px;
        }
        .hadith-text {
            font-size: 22px;
            line-height: 2;
            color: var(--text-dark);
            white-space: pre-wrap;
            padding: 15px;
            background: #fafaf5;
            border-radius: 8px;
            text-align: justify;
        }

        .surah-container {
            background: #fdfaf3;
            border: 3px double var(--gold);
            border-radius: 15px;
            padding: 25px;
        }
        .surah-header-bar {
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #1a4d2e 0%, #2d6a4f 100%);
            color: white;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .surah-header-bar h2 {
            font-size: 32px;
            color: var(--gold);
            margin-bottom: 8px;
        }
        .surah-header-bar .surah-info {
            font-size: 14px;
            opacity: 0.9;
        }
        .basmala {
            text-align: center;
            font-size: 26px;
            color: var(--main-green);
            font-weight: bold;
            margin: 20px 0;
            padding: 15px;
            border-top: 1px dashed var(--gold);
            border-bottom: 1px dashed var(--gold);
        }
        .ayah-line {
            font-size: 26px;
            line-height: 2.8;
            text-align: justify;
            color: #1a3d2e;
            padding: 8px 15px;
            margin: 5px 0;
            border-radius: 8px;
            transition: background 0.2s;
            position: relative;
        }
        .ayah-line:hover { background: #f0f8f0; }
        .ayah-line.highlight {
            background: #fff3cd;
            box-shadow: 0 0 0 2px var(--gold);
        }
        .ayah-num-badge {
            display: inline-block;
            background: var(--gold);
            color: white;
            font-size: 14px;
            font-weight: bold;
            padding: 2px 10px;
            border-radius: 15px;
            margin: 0 8px;
            vertical-align: middle;
            font-family: sans-serif;
        }
        .ayah-actions {
            display: none;
            margin-top: 8px;
            gap: 8px;
        }
        .ayah-line:hover .ayah-actions { display: flex; }
        .ayah-action-btn {
            background: var(--main-green);
            color: white;
            border: none;
            padding: 4px 12px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 12px;
            font-family: inherit;
        }
        .ayah-action-btn:hover { background: #40916c; }
        .tafsir-panel {
            display: none;
            background: #f0f9ff;
            border-right: 4px solid #28a745;
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            font-size: 18px;
            line-height: 2;
            text-align: justify;
        }
        .tafsir-panel.show { display: block; }
        .tafsir-title {
            color: #28a745;
            font-weight: bold;
            margin-bottom: 8px;
            font-size: 15px;
        }

        .quran-tools {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 20px;
            padding: 15px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .quran-tools select {
            padding: 10px 15px;
            font-size: 16px;
            border-radius: 8px;
            border: 2px solid #ddd;
            font-family: inherit;
            flex: 1;
            min-width: 200px;
            cursor: pointer;
        }
        .quran-tools select:focus {
            outline: none;
            border-color: var(--main-green);
        }
        .quran-tools button {
            padding: 10px 20px;
            background: var(--main-green);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-family: inherit;
            font-size: 15px;
            font-weight: bold;
        }
        .quran-tools button:hover { background: #40916c; }

        .nav-buttons {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin: 20px 0;
            flex-wrap: wrap;
        }
        .nav-btn {
            background: var(--main-green);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            font-family: inherit;
            min-width: 120px;
            transition: all 0.2s;
        }
        .nav-btn:hover:not(:disabled) { background: #40916c; transform: translateY(-2px); }
        .nav-btn:disabled { background: #ccc; cursor: not-allowed; }

        .copy-buttons {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-top: 20px;
            flex-wrap: wrap;
        }
        .copy-btn {
            background: var(--gold);
            color: white;
            border: none;
            padding: 10px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 15px;
            font-family: inherit;
            font-weight: bold;
        }
        .copy-btn:hover { background: #b8935a; }

        .search-results {
            max-height: 600px;
            overflow-y: auto;
            margin-top: 15px;
        }
        .search-result-item {
            padding: 12px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
            transition: background 0.2s;
        }
        .search-result-item:hover { background: var(--light-green); }
        .search-result-item .res-num {
            color: var(--main-green);
            font-weight: bold;
            font-size: 13px;
        }
        .search-result-item .res-text {
            font-size: 16px;
            line-height: 1.8;
            margin-top: 5px;
        }

        mark {
            background: #ffeb3b;
            color: #000;
            padding: 2px 4px;
            border-radius: 3px;
            font-weight: bold;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: var(--main-green);
            font-size: 18px;
        }

        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .modal-overlay.show { display: flex; }
        .modal-content {
            background: white;
            border-radius: 15px;
            padding: 30px;
            max-width: 600px;
            width: 100%;
            max-height: 90vh;
            overflow-y: auto;
            position: relative;
            border: 3px solid var(--gold);
        }
        .modal-close {
            position: absolute;
            top: 15px;
            left: 15px;
            background: #c0392b;
            color: white;
            border: none;
            width: 35px;
            height: 35px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 20px;
            font-weight: bold;
        }
        .modal-content h2 {
            text-align: center;
            color: var(--main-green);
            font-size: 26px;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid var(--gold);
        }
        .dev-card {
            background: linear-gradient(135deg, #1a4d2e 0%, #2d6a4f 100%);
            color: white;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            margin-bottom: 20px;
        }
        .dev-card .dev-name {
            font-size: 24px;
            color: var(--gold);
            font-weight: bold;
            margin-bottom: 15px;
        }
        .dev-contact {
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-top: 15px;
        }
        .contact-link {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            background: rgba(255,255,255,0.15);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            transition: background 0.2s;
            font-size: 15px;
        }
        .contact-link:hover { background: rgba(255,255,255,0.25); }

        /* أزرار المشاركة */
        .share-buttons {
            display: flex;
            justify-content: center;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 15px;
        }
        .share-btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 10px 20px;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            font-family: inherit;
            font-size: 14px;
            font-weight: bold;
            color: white;
            text-decoration: none;
            transition: transform 0.2s, opacity 0.2s;
        }
        .share-btn:hover { transform: translateY(-2px); opacity: 0.9; }
        .share-btn.whatsapp { background: #25d366; }
        .share-btn.telegram { background: #0088cc; }
        .share-btn.twitter { background: #1da1f2; }
        .share-btn.facebook { background: #1877f2; }
        .share-btn.copy { background: #6c757d; }
        .share-btn.email { background: #c0392b; }

        .share-link-box {
            display: flex;
            gap: 8px;
            margin-top: 15px;
            background: #f5f5f5;
            padding: 10px;
            border-radius: 8px;
            align-items: center;
        }
        .share-link-box input {
            flex: 1;
            padding: 8px;
            border: 1px solid #ccc;
            border-radius: 5px;
            font-size: 13px;
            direction: ltr;
            background: white;
        }
        .share-link-box button {
            padding: 8px 15px;
            background: var(--main-green);
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-family: inherit;
            font-weight: bold;
        }

        .section-box {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
            border-right: 4px solid var(--gold);
        }
        .section-box h3 {
            color: var(--main-green);
            margin-bottom: 10px;
            font-size: 18px;
        }
        .section-box p, .section-box li {
            font-size: 15px;
            line-height: 1.9;
            color: #333;
        }
        .section-box ul { padding-right: 20px; }
        .dua-box {
            background: #fff9e6;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 12px;
            border-right: 4px solid var(--gold);
            text-align: center;
        }
        .dua-box p {
            font-size: 17px;
            line-height: 2;
            color: #1a4d2e;
            font-weight: 500;
        }

        @media (max-width: 600px) {
            .header h1 { font-size: 20px; }
            .hadith-text { font-size: 19px; }
            .hadith-card { padding: 15px; }
            .nav-btn { padding: 10px 20px; font-size: 14px; min-width: 90px; }
            .book-btn { font-size: 12px; padding: 6px 12px; }
            .info-time { font-size: 22px; }
            .prayer-times { gap: 8px; font-size: 12px; }
            .ayah-line { font-size: 22px; line-height: 2.5; }
            .surah-header-bar h2 { font-size: 24px; }
            .share-btn { padding: 8px 14px; font-size: 13px; }
        }

        body.dark-mode {
            --bg: #1a1a1a;
            --text-dark: #e0e0e0;
        }
        body.dark-mode .hadith-card, body.dark-mode .modal-content, body.dark-mode .quran-tools { background: #2a2a2a; border-color: #444; color: #e0e0e0; }
        body.dark-mode .hadith-text { background: #333; color: #e0e0e0; }
        body.dark-mode .surah-container { background: #222; border-color: var(--gold); }
        body.dark-mode .ayah-line { color: #e0e0e0; }
        body.dark-mode .ayah-line:hover { background: #2f2f2f; }
        body.dark-mode .text-controls { background: #2a2a2a; border-color: #444; }
        body.dark-mode .text-controls .size-display { background: #333; color: white; border-color: #555; }
        body.dark-mode .narrator { background: #3a3a2a; color: #e0c060; }
        body.dark-mode .search-area input { background: #333; color: white; }
        body.dark-mode .section-box { background: #333; }
        body.dark-mode .section-box p, body.dark-mode .section-box li { color: #ddd; }
        body.dark-mode .dua-box { background: #3a3520; }
        body.dark-mode .dua-box p { color: #e0e0e0; }
        body.dark-mode .tafsir-panel { background: #1e3a2f; color: #ddd; }
        body.dark-mode .share-link-box { background: #333; }
        body.dark-mode .share-link-box input { background: #222; color: white; border-color: #555; }
    </style>
</head>
<body>

<div class="header">
    <h1>🕌 الموسوعة الإسلامية الشاملة 📚</h1>

    <div class="top-actions">
        <button class="top-btn" onclick="toggleDark()">🌙 ليلي</button>
        <button class="top-btn" onclick="detectLocation()">📍 تحديد الموقع</button>
        <button class="top-btn" onclick="toggleBookmark()">🔖 علامة</button>
        <button class="top-btn" onclick="showAbout()">ℹ️ حول التطبيق</button>
    </div>

    <div class="search-area">
        <input type="text" id="searchInput" placeholder="اكتب كلمة للبحث..." onkeydown="if(event.key==='Enter') doSearch()">
        <button onclick="doSearch()">🔍</button>
    </div>
</div>

<div class="info-bar">
    <div class="info-time" id="currentTime">--:--:--</div>
    <div class="info-date">
        <span id="gregorianDate">جاري تحميل التاريخ...</span><br>
        <span id="hijriDate" style="color:var(--gold);">جاري تحميل التاريخ الهجري...</span>
    </div>
    <div class="prayer-times">
        <div class="prayer-item"><span class="name">الفجر</span><span class="time" id="fajrTime">--:--</span></div>
        <div class="prayer-item"><span class="name">الشروق</span><span class="time" id="sunriseTime">--:--</span></div>
        <div class="prayer-item"><span class="name">الظهر</span><span class="time" id="dhuhrTime">--:--</span></div>
        <div class="prayer-item"><span class="name">العصر</span><span class="time" id="asrTime">--:--</span></div>
        <div class="prayer-item"><span class="name">المغرب</span><span class="time" id="maghribTime">--:--</span></div>
        <div class="prayer-item"><span class="name">العشاء</span><span class="time" id="ishaTime">--:--</span></div>
    </div>
    <div class="location-info" id="locationInfo">📍 جاري تحديد الموقع...</div>
</div>

<div class="text-controls">
    <button onclick="changeFontSize(1)">➕ تكبير النص</button>
    <span class="size-display" id="fontSizeDisplay">22</span>
    <button onclick="changeFontSize(-1)">➖ تصغير النص</button>
    <button onclick="resetFontSize()">↺ الافتراضي</button>
</div>

<div class="books-bar">
    <button class="book-btn" onclick="selectQuran()" id="quranBtn">📖 القرآن الكريم</button>
    {% for key, value in books.items() %}
    <button class="book-btn" data-book="{{ key }}" onclick="selectBook('{{ key }}')">{{ value }}</button>
    {% endfor %}
</div>

<div class="content-area">
    <div id="content">
        <div class="loading">اختر كتاباً من الأعلى للبدء 🕌</div>
    </div>
</div>

<!-- ============ نافذة حول التطبيق ============ -->
<div class="modal-overlay" id="aboutModal" onclick="if(event.target===this) hideAbout()">
    <div class="modal-content">
        <button class="modal-close" onclick="hideAbout()">✕</button>
        <h2>🕌 حول التطبيق 📚</h2>

        <div class="dev-card">
            <div class="dev-name">👤 حسان مارديني</div>
            <div style="font-size:14px;opacity:0.9;margin-bottom:10px;">مطوّر وصاحب التطبيق</div>
            <div class="dev-contact">
                <a href="tel:+905060917640" class="contact-link">
                    📞 <span>+90 506 091 7640</span>
                </a>
                <a href="mailto:hassanmardinli21@gmail.com" class="contact-link">
                    📧 <span>hassanmardinli21@gmail.com</span>
                </a>
                <a href="https://wa.me/905060917640" target="_blank" class="contact-link">
                    💬 <span>تواصل عبر واتساب</span>
                </a>
            </div>
        </div>

        <!-- ============ قسم مشاركة التطبيق ============ -->
        <div class="section-box" style="background:#e8f5e9;border-right-color:#25d366;">
            <h3>📢 شارك التطبيق مع أصدقائك</h3>
            <p style="text-align:center;margin-bottom:10px;">الدال على الخير كفاعله 🤲</p>

            <div class="share-buttons">
                <a href="#" id="shareWhatsapp" class="share-btn whatsapp" target="_blank">💬 واتساب</a>
                <a href="#" id="shareTelegram" class="share-btn telegram" target="_blank">✈️ تيليجرام</a>
                <a href="#" id="shareTwitter" class="share-btn twitter" target="_blank">🐦 تويتر</a>
                <a href="#" id="shareFacebook" class="share-btn facebook" target="_blank">📘 فيسبوك</a>
                <a href="#" id="shareEmail" class="share-btn email">📧 إيميل</a>
                <button class="share-btn copy" onclick="copyShareLink()">📋 نسخ الرابط</button>
            </div>

            <div class="share-link-box">
                <input type="text" id="shareLinkInput" readonly onclick="this.select()">
                <button onclick="copyShareLink()">نسخ</button>
            </div>

            <p style="text-align:center;font-size:13px;color:#666;margin-top:10px;">
                ✨ كل شخص يفتح التطبيق بسببك = أجر لك في ميزان حسناتك ✨
            </p>
        </div>

        <div class="section-box">
            <h3>📖 محتوى التطبيق</h3>
            <ul>
                <li>القرآن الكريم كاملاً (114 سورة)</li>
                <li>تفسير السعدي للآيات</li>
                <li>14 كتاباً من كتب الحديث النبوي الشريف</li>
                <li>مواقيت الصلاة حسب موقعك</li>
                <li>التاريخ الهجري والميلادي</li>
            </ul>
        </div>

        <div class="section-box">
            <h3>🤲 دعاء للمستخدمين</h3>
        </div>
        <div class="dua-box">
            <p>اللَّهُمَّ اجْعَلْ هَذَا الْعَمَلَ خَالِصًا لِوَجْهِكَ الْكَرِيمِ، وَانْفَعْ بِهِ الْمُسْلِمِينَ</p>
        </div>
        <div class="dua-box">
            <p>اللَّهُمَّ اجْعَلِ الْقُرْآنَ الْعَظِيمَ رَبِيعَ قُلُوبِنَا، وَنُورَ صُدُورِنَا، وَجَلَاءَ هُمُومِنَا وَأَحْزَانِنَا</p>
        </div>
        <div class="dua-box">
            <p>اللَّهُمَّ اغْفِرْ لَنَا وَلِوَالِدِينَا وَلِوَالِدِي وَالِدِينَا، وَارْحَمْهُمْ كَمَا رَبَّوْنَا صِغَارًا</p>
        </div>
        <div class="dua-box">
            <p>اللَّهُمَّ اجْعَلْ هَذَا الْعَمَلَ صَدَقَةً جَارِيَةً لِوَالِدَيَّ وَلِوَالِدِي وَالِدَيَّ، وَلِجَمِيعِ الْمُسْلِمِينَ</p>
        </div>
        <div class="dua-box">
            <p>اللَّهُمَّ ارْحَمْ وَالِدَيَّ وَوَالِدِي وَالِدَيَّ، وَأَسْكِنْهُمْ فَسِيحَ جَنَّاتِكَ، وَاجْمَعْنَا بِهِمْ فِي مُسْتَقَرِّ رَحْمَتِكَ</p>
        </div>
        <div class="dua-box">
            <p>اللَّهُمَّ اجْزِ خَيْرًا كُلَّ مَنْ سَاهَمَ فِي نَشْرِ هَذَا الْعِلْمِ النَّافِعِ</p>
        </div>

        <div class="section-box">
            <h3>💝 شكر وتقدير</h3>
            <p>نتقدم بالشكر الجزيل لكل من ساهم في إثراء هذا التطبيق، ونسأل الله أن يجعله في ميزان حسناتهم أجمعين.</p>
        </div>

        <div class="section-box">
            <h3>📜 إخلاء مسؤولية</h3>
            <p>هذا التطبيق مجاني ولا يهدف للربح. البيانات الموجودة من مصادر موثوقة، ويُرجع للعلماء في المسائل الفقهية الدقيقة.</p>
        </div>

        <div style="text-align:center;color:#888;font-size:13px;margin-top:20px;">
            الإصدار 1.0 | © 2025
        </div>
    </div>
</div>

<script>
    let currentBook = null;
    let currentIndex = 0;
    let currentSurah = 1;
    let currentSurahData = null;
    let fontSize = 22;
    let bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '{}');
    let currentSearchQuery = '';

    // ============ الوقت والتاريخ ============
    function updateTime() {
        const now = new Date();
        document.getElementById('currentTime').innerText = now.toLocaleTimeString('ar-SA', {
            hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true
        });
        document.getElementById('gregorianDate').innerText = now.toLocaleDateString('ar-SA', {
            weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
        });
        try {
            const hijriFormatter = new Intl.DateTimeFormat('ar-SA-u-ca-islamic-umalqura', {
                year: 'numeric', month: 'long', day: 'numeric', weekday: 'long'
            });
            document.getElementById('hijriDate').innerText = hijriFormatter.format(now) + ' هـ';
        } catch(e) {}
    }
    setInterval(updateTime, 1000);
    updateTime();

    // ============ الموقع ============
    function detectLocation() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    calculatePrayerTimes(position.coords.latitude, position.coords.longitude);
                    reverseGeocode(position.coords.latitude, position.coords.longitude);
                },
                (error) => {
                    document.getElementById('locationInfo').innerText = '⚠️ لم يتم السماح بالوصول إلى الموقع - استخدام مكة';
                    calculatePrayerTimes(21.4225, 39.8262);
                }
            );
        }
    }

    async function reverseGeocode(lat, lng) {
        try {
            const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&accept-language=ar`);
            const data = await res.json();
            const city = data.address?.city || data.address?.town || data.address?.village || data.address?.state || '';
            const country = data.address?.country || '';
            document.getElementById('locationInfo').innerText = `📍 ${city}${city && country ? '، ' : ''}${country}`;
        } catch(e) {
            document.getElementById('locationInfo').innerText = `📍 ${lat.toFixed(2)}°N, ${lng.toFixed(2)}°E`;
        }
    }

    function calculatePrayerTimes(lat, lng) {
        try {
            const coordinates = new adhan.Coordinates(lat, lng);
            const params = adhan.CalculationMethod.MuslimWorldLeague();
            const date = new Date();
            const prayerTimes = new adhan.PrayerTimes(coordinates, date, params);
            const formatTime = (d) => d ? d.toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit', hour12: true }) : '--:--';
            document.getElementById('fajrTime').innerText = formatTime(prayerTimes.fajr);
            document.getElementById('sunriseTime').innerText = formatTime(prayerTimes.sunrise);
            document.getElementById('dhuhrTime').innerText = formatTime(prayerTimes.dhuhr);
            document.getElementById('asrTime').innerText = formatTime(prayerTimes.asr);
            document.getElementById('maghribTime').innerText = formatTime(prayerTimes.maghrib);
            document.getElementById('ishaTime').innerText = formatTime(prayerTimes.isha);
        } catch(e) { console.error(e); }
    }

    detectLocation();

    // ============ الخط ============
    function changeFontSize(delta) {
        fontSize = Math.max(14, Math.min(48, fontSize + delta));
        document.getElementById('fontSizeDisplay').innerText = fontSize;
        document.querySelectorAll('.hadith-text, .ayah-line').forEach(el => {
            el.style.fontSize = fontSize + 'px';
        });
    }
    function resetFontSize() {
        fontSize = 22;
        document.getElementById('fontSizeDisplay').innerText = fontSize;
        document.querySelectorAll('.hadith-text, .ayah-line').forEach(el => {
            el.style.fontSize = fontSize + 'px';
        });
    }

    // ============ الوضع الليلي ============
    function toggleDark() {
        document.body.classList.toggle('dark-mode');
        localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
    }
    if (localStorage.getItem('darkMode') === 'true') {
        document.body.classList.add('dark-mode');
    }

    // ============ العلامات ============
    function toggleBookmark() {
        if (!currentBook) return;
        const key = currentBook + '_' + currentIndex;
        if (bookmarks[key]) delete bookmarks[key];
        else bookmarks[key] = { book: currentBook, index: currentIndex, time: Date.now() };
        localStorage.setItem('bookmarks', JSON.stringify(bookmarks));
        alert(bookmarks[key] ? '✅ تمت إضافة علامة' : '🗑️ تم حذف العلامة');
    }

    // ============ حول التطبيق ============
    function showAbout() {
        document.getElementById('aboutModal').classList.add('show');
        setupShareLinks();
    }
    function hideAbout() { document.getElementById('aboutModal').classList.remove('show'); }

    // ============ المشاركة ============
    function getShareMessage() {
        return '🕌 الموسوعة الإسلامية الشاملة 📚\n\n' +
               '📖 القرآن الكريم كاملاً مع التفسير\n' +
               '📚 14 كتاباً من كتب الحديث النبوي\n' +
               '🕌 مواقيت الصلاة والتاريخ الهجري\n\n' +
               '✨ تطبيق مجاني يخدم الإسلام والمسلمين ✨\n\n' +
               '🔗 رابط التطبيق:';
    }

    function setupShareLinks() {
        const url = window.location.origin;
        const message = getShareMessage();
        const fullMessage = message + '\n' + url;

        document.getElementById('shareLinkInput').value = url;

        document.getElementById('shareWhatsapp').href =
            'https://wa.me/?text=' + encodeURIComponent(fullMessage);
        document.getElementById('shareTelegram').href =
            'https://t.me/share/url?url=' + encodeURIComponent(url) + '&text=' + encodeURIComponent(message);
        document.getElementById('shareTwitter').href =
            'https://twitter.com/intent/tweet?text=' + encodeURIComponent(message) + '&url=' + encodeURIComponent(url);
        document.getElementById('shareFacebook').href =
            'https://www.facebook.com/sharer/sharer.php?u=' + encodeURIComponent(url);
        document.getElementById('shareEmail').href =
            'mailto:?subject=' + encodeURIComponent('الموسوعة الإسلامية الشاملة') + '&body=' + encodeURIComponent(fullMessage);
    }

    function copyShareLink() {
        const url = window.location.origin;
        const text = getShareMessage() + '\n' + url;
        navigator.clipboard.writeText(text).then(() => {
            alert('✅ تم نسخ الرابط والرسالة\nيمكنك لصقها في أي مكان للمشاركة');
        }).catch(() => {
            const input = document.getElementById('shareLinkInput');
            input.select();
            document.execCommand('copy');
            alert('✅ تم نسخ الرابط');
        });
    }

    // ============ الكتب ============
    function setActiveBook(bookId) {
        document.querySelectorAll('.book-btn').forEach(b => b.classList.remove('active'));
        if (bookId === 'quran') document.getElementById('quranBtn').classList.add('active');
        else document.querySelector(`[data-book="${bookId}"]`).classList.add('active');
    }

    async function selectBook(bookId) {
        currentBook = bookId;
        currentIndex = 0;
        currentSearchQuery = '';
        setActiveBook(bookId);
        await showHadith(0);
    }

    async function showHadith(index) {
        const content = document.getElementById('content');
        content.innerHTML = '<div class="loading">جاري التحميل...</div>';

        try {
            const res = await fetch(`/api/hadith?book=${currentBook}&index=${index}`);
            const data = await res.json();

            if (data.error) {
                content.innerHTML = `<div class="hadith-card" style="text-align:center;color:red;">${data.error}</div>`;
                return;
            }

            currentIndex = data.index;
            const isBookmarked = bookmarks[currentBook + '_' + currentIndex];

            content.innerHTML = `
                <div class="hadith-card">
                    <div class="hadith-header">
                        <span class="hadith-book-name">📚 ${getBookName(currentBook)}</span>
                        <span class="hadith-number">حديث رقم ${data.id} / ${data.total}</span>
                    </div>
                    ${data.narrator ? `<div class="narrator">🎙️ ${data.narrator}</div>` : ''}
                    <div class="hadith-text" id="hadithText" style="font-size:${fontSize}px;">${highlightText(data.text, currentSearchQuery)}</div>
                    <div class="copy-buttons">
                        <button class="copy-btn" onclick="copyHadith()">📋 نسخ الحديث</button>
                        <button class="copy-btn" onclick="toggleBookmark()">${isBookmarked ? '🔖 إزالة العلامة' : '🔖 علامة'}</button>
                    </div>
                </div>
                <div class="nav-buttons">
                    <button class="nav-btn" onclick="showHadith(${data.index - 1})" ${data.index === 0 ? 'disabled' : ''}>◀ السابق</button>
                    <button class="nav-btn" onclick="showHadith(0)">🏠 الأول</button>
                    <button class="nav-btn" onclick="showHadith(${data.index + 1})" ${data.index >= data.total - 1 ? 'disabled' : ''}>التالي ▶</button>
                </div>
            `;
        } catch (e) {
            content.innerHTML = '<div class="hadith-card" style="text-align:center;color:red;">حدث خطأ</div>';
        }
    }

    // ============ القرآن ============
    async function selectQuran() {
        currentBook = 'quran';
        setActiveBook('quran');
        await showSurah(1);
    }

    async function showSurah(surahNum) {
        const content = document.getElementById('content');
        content.innerHTML = '<div class="loading">جاري تحميل السورة...</div>';

        try {
            const res = await fetch(`/api/surah?surah=${surahNum}`);
            const data = await res.json();
            currentSurah = surahNum;
            currentSurahData = data;
            renderFullSurah();
        } catch (e) {
            content.innerHTML = '<div class="hadith-card" style="text-align:center;color:red;">حدث خطأ</div>';
        }
    }

    function renderFullSurah() {
        const content = document.getElementById('content');
        const data = currentSurahData;

        if (!data.ayahs || data.ayahs.length === 0) {
            content.innerHTML = '<div class="hadith-card" style="text-align:center;">لا توجد آيات لهذه السورة</div>';
            return;
        }

        const surahsArray = JSON.parse(`{{ surahs|tojson }}`);

        let surahSelectHtml = '<select id="surahSelect" onchange="showSurah(this.value)">';
        surahsArray.forEach(s => {
            surahSelectHtml += `<option value="${s.id}" ${s.id === currentSurah ? 'selected' : ''}>${s.id}. سورة ${s.name}</option>`;
        });
        surahSelectHtml += '</select>';

        let ayahSelectHtml = '<select id="ayahSelect" onchange="scrollToAyah(this.value)">';
        ayahSelectHtml += '<option value="">📌 انتقل إلى آية...</option>';
        data.ayahs.forEach(a => {
            ayahSelectHtml += `<option value="${a.ayah}">آية ${a.ayah}</option>`;
        });
        ayahSelectHtml += '</select>';

        let ayahsHtml = '';
        if (currentSurah !== 1 && currentSurah !== 9) {
            ayahsHtml += `<div class="basmala">بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ</div>`;
        }

        data.ayahs.forEach(a => {
            ayahsHtml += `
                <div class="ayah-line" id="ayah-${a.ayah}" data-ayah="${a.ayah}">
                    <span>${highlightText(a.text, currentSearchQuery)}</span>
                    <span class="ayah-num-badge">${a.ayah}</span>
                    <div class="ayah-actions">
                        <button class="ayah-action-btn" onclick="copyAyah(${a.ayah})">📋 نسخ</button>
                        ${a.tafsir ? `<button class="ayah-action-btn" onclick="toggleTafsir(${a.ayah})">📖 التفسير</button>` : ''}
                    </div>
                    ${a.tafsir ? `<div class="tafsir-panel" id="tafsir-${a.ayah}"><div class="tafsir-title">📖 التفسير (السعدي):</div>${highlightText(a.tafsir, currentSearchQuery)}</div>` : ''}
                </div>
            `;
        });

        content.innerHTML = `
            <div class="quran-tools">
                ${surahSelectHtml}
                ${ayahSelectHtml}
                <button onclick="document.querySelectorAll('.tafsir-panel').forEach(t=>t.classList.toggle('show'))">📖 إظهار/إخفاء التفسير</button>
                <button onclick="copySurah()">📋 نسخ السورة</button>
            </div>
            <div class="surah-container">
                <div class="surah-header-bar">
                    <h2>سورة ${data.name}</h2>
                    <div class="surah-info">${data.ayahs.length} آية</div>
                </div>
                ${ayahsHtml}
            </div>
            <div class="nav-buttons">
                <button class="nav-btn" onclick="showSurah(${currentSurah - 1})" ${currentSurah <= 1 ? 'disabled' : ''}>◀ السورة السابقة</button>
                <button class="nav-btn" onclick="scrollToTop()">⬆ أعلى</button>
                <button class="nav-btn" onclick="showSurah(${currentSurah + 1})" ${currentSurah >= 114 ? 'disabled' : ''}>السورة التالية ▶</button>
            </div>
        `;
    }

    function scrollToAyah(ayahNum) {
        if (!ayahNum) return;
        const el = document.getElementById('ayah-' + ayahNum);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.classList.add('highlight');
            setTimeout(() => el.classList.remove('highlight'), 3000);
        }
    }

    function scrollToTop() {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function toggleTafsir(ayahNum) {
        const el = document.getElementById('tafsir-' + ayahNum);
        if (el) el.classList.toggle('show');
    }

    function copyAyah(ayahNum) {
        const el = document.getElementById('ayah-' + ayahNum);
        if (!el) return;
        const text = el.querySelector('span').innerText;
        navigator.clipboard.writeText(text).then(() => alert('✅ تم نسخ الآية'));
    }

    function copySurah() {
        const container = document.querySelector('.surah-container');
        if (!container) return;
        let text = container.querySelector('h2').innerText + '\n\n';
        container.querySelectorAll('.ayah-line').forEach(line => {
            text += line.querySelector('span').innerText + ' (' + line.dataset.ayah + ')\n';
        });
        navigator.clipboard.writeText(text).then(() => alert('✅ تم نسخ السورة كاملة'));
    }

    // ============ البحث ============
    async function doSearch() {
        const query = document.getElementById('searchInput').value.trim();
        if (!query) { alert('اكتب كلمة للبحث'); return; }
        currentSearchQuery = query;

        if (!currentBook || currentBook === 'quran') {
            currentBook = 'bukhari';
            setActiveBook('bukhari');
        }

        const content = document.getElementById('content');
        content.innerHTML = '<div class="loading">جاري البحث...</div>';

        try {
            const res = await fetch(`/api/search?book=${currentBook}&query=${encodeURIComponent(query)}`);
            const data = await res.json();

            if (data.length === 0) {
                content.innerHTML = '<div class="hadith-card" style="text-align:center;">لا توجد نتائج مطابقة</div>';
                return;
            }

            let html = `<div class="hadith-card">
                            <div class="hadith-header">
                                <span class="hadith-book-name">🔍 نتائج البحث في ${getBookName(currentBook)}</span>
                                <span class="hadith-number">${data.length} نتيجة</span>
                            </div>
                            <div class="search-results">`;
            data.forEach(item => {
                html += `<div class="search-result-item" onclick="showHadith(${item.index})">
                            <div class="res-num">📌 حديث رقم ${item.id}</div>
                            ${item.narrator ? `<div style="color:#b8860b;font-size:13px;margin:5px 0;">🎙️ ${item.narrator}</div>` : ''}
                            <div class="res-text">${highlightText(item.text.substring(0, 250), query)}${item.text.length > 250 ? '...' : ''}</div>
                        </div>`;
            });
            html += '</div></div>';
            content.innerHTML = html;
        } catch (e) {
            content.innerHTML = '<div class="hadith-card" style="text-align:center;color:red;">حدث خطأ</div>';
        }
    }

    // ============ أدوات ============
    function getBookName(bookId) {
        const names = {
            'quran': 'القرآن الكريم',
            {% for key, value in books.items() %}
            '{{ key }}': '{{ value }}',
            {% endfor %}
        };
        return names[bookId] || bookId;
    }

    function copyHadith() {
        const el = document.getElementById('hadithText');
        if (!el) return;
        navigator.clipboard.writeText(el.innerText).then(() => {
            const btns = document.querySelectorAll('.copy-btn');
            btns.forEach(b => {
                if (b.innerText.includes('نسخ')) {
                    const orig = b.innerText;
                    b.innerText = '✅ تم النسخ';
                    setTimeout(() => b.innerText = orig, 1500);
                }
            });
        });
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    function highlightText(text, query) {
        const escaped = escapeHtml(text);
        if (!query) return escaped;
        try {
            const regex = new RegExp('(' + query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
            return escaped.replace(regex, '<mark>$1</mark>');
        } catch(e) {
            return escaped;
        }
    }
</script>
</body>
</html>
"""

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
