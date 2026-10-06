import os
import json
import re
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

def normalize_arabic(text):
    if not text:
        return ''
    text = str(text)
    text = re.sub(r'[\u064B-\u0652\u0670\u0640\u06D6-\u06DC\u06DF-\u06E8\u06EA-\u06ED]', '', text)
    text = re.sub(r'[أإآٱ]', 'ا', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'ة', 'ه', text)
    return text

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
quran_ayahs_normalized = {}

if isinstance(quran_data, list):
    for surah in quran_data:
        surah_num = surah.get('id')
        surah_name = surah.get('name', '')
        surahs_list.append({'id': surah_num, 'name': surah_name})
        for ayah in surah.get('verses', []):
            ayah_num = ayah.get('id')
            text = ayah.get('text', '')
            quran_ayahs_map[(surah_num, ayah_num)] = text
            quran_ayahs_normalized[(surah_num, ayah_num)] = normalize_arabic(text)

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
        files = sorted([f for f in files if f.endswith('.json')],
                       key=lambda x: int(x.split('.')[0]) if x.split('.')[0].isdigit() else 999)
        for filename in files:
            filepath = os.path.join(folder_path, filename)
            data = load_json(filepath)
            all_hadiths.extend(data.get('hadiths', []))
    loaded_books_cache[book_id] = all_hadiths
    return all_hadiths

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
        'index': index, 'total': len(hadiths),
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
            ayahs.append({'ayah': a, 'text': text, 'tafsir': tafsir_map.get((s, a), '')})
    surah_name = next((s['name'] for s in surahs_list if s['id'] == surah_num), '')
    return jsonify({'surah': surah_num, 'name': surah_name, 'ayahs': ayahs})

@app.route('/api/search')
def search():
    book_id = request.args.get('book', 'bukhari')
    query = request.args.get('query', '').strip()
    query_norm = normalize_arabic(query)
    if not query_norm or book_id not in BOOKS:
        return jsonify([])
    hadiths = load_hadith_book(book_id)
    results = []
    for i, h in enumerate(hadiths):
        arabic_text = h.get('arabic', '')
        if query_norm in normalize_arabic(arabic_text):
            results.append({
                'index': i, 'id': h.get('idInBook', i + 1),
                'text': arabic_text,
                'narrator': h.get('english', {}).get('narrator', '')
            })
    return jsonify(results)

@app.route('/api/search_surah')
def search_surah():
    surah_num = request.args.get('surah', 1, type=int)
    query = request.args.get('query', '').strip()
    query_norm = normalize_arabic(query)
    if not query_norm:
        return jsonify([])
    results = []
    for (s, a), norm_text in sorted(quran_ayahs_normalized.items()):
        if s == surah_num and query_norm in norm_text:
            results.append({
                'surah': s, 'surah_name': next((x['name'] for x in surahs_list if x['id'] == s), ''),
                'ayah': a, 'text': quran_ayahs_map[(s, a)]
            })
    return jsonify(results)

@app.route('/api/search_quran')
def search_quran():
    query = request.args.get('query', '').strip()
    query_norm = normalize_arabic(query)
    if not query_norm:
        return jsonify([])
    results = []
    for (s, a), norm_text in quran_ayahs_normalized.items():
        if query_norm in norm_text:
            surah_name = next((x['name'] for x in surahs_list if x['id'] == s), '')
            results.append({
                'surah': s, 'surah_name': surah_name, 'ayah': a,
                'text': quran_ayahs_map[(s, a)]
            })
    return jsonify(results)

@app.route('/api/search_advanced')
def search_advanced():
    query = request.args.get('query', '').strip()
    query_norm = normalize_arabic(query)
    books_param = request.args.get('books', '')
    include_quran = request.args.get('quran', '0') == '1'
    if not query_norm:
        return jsonify({'books': {}, 'quran': []})
    result = {'books': {}, 'quran': []}
    if include_quran:
        quran_results = []
        for (s, a), norm_text in quran_ayahs_normalized.items():
            if query_norm in norm_text:
                surah_name = next((x['name'] for x in surahs_list if x['id'] == s), '')
                quran_results.append({
                    'surah': s, 'surah_name': surah_name, 'ayah': a,
                    'text': quran_ayahs_map[(s, a)]
                })
        result['quran'] = quran_results
    selected_books = []
    if books_param == 'all':
        selected_books = list(BOOKS.keys())
    elif books_param:
        selected_books = [b.strip() for b in books_param.split(',') if b.strip() in BOOKS]
    for book_id in selected_books:
        hadiths = load_hadith_book(book_id)
        book_results = []
        for i, h in enumerate(hadiths):
            arabic_text = h.get('arabic', '')
            if query_norm in normalize_arabic(arabic_text):
                book_results.append({
                    'index': i, 'id': h.get('idInBook', i + 1),
                    'text': arabic_text,
                    'narrator': h.get('english', {}).get('narrator', '')
                })
        if book_results:
            result['books'][book_id] = {'name': BOOKS[book_id], 'results': book_results}
    return jsonify(result)

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>الموسوعة الإسلامية الشاملة</title>
    <script src="https://unpkg.com/adhan/lib/bundles/adhan.umd.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        :root { --main-green: #1a4d2e; --light-green: #e8f5e9; --gold: #c9a961; --bg: #f0f0e8; --text-dark: #1a1a1a; }
        body { font-family: 'Amiri', 'Segoe UI', Tahoma, sans-serif; background: var(--bg); min-height: 100vh; color: var(--text-dark); }
        .hadith-text, .ayah-line, .tafsir-panel, .search-result-item .res-text {
            font-family: 'Amiri', 'Traditional Arabic', serif; text-align: right; line-height: 2.2;
            word-spacing: 2px; letter-spacing: 0; word-wrap: break-word; overflow-wrap: break-word;
        }
        .header { background: var(--main-green); color: white; padding: 15px 20px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.2); position: sticky; top: 0; z-index: 100; }
        .header h1 { font-size: 26px; color: var(--gold); margin-bottom: 12px; }
        .top-actions { display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
        .top-btn { background: #2d6a4f; color: white; border: 1px solid rgba(255,255,255,0.2); padding: 8px 14px; border-radius: 6px; font-size: 13px; cursor: pointer; font-family: inherit; font-weight: bold; transition: all 0.2s; position: relative; }
        .top-btn:hover { background: #40916c; }
        .top-btn.active { background: var(--gold); color: #1a4d2e; }
        .badge { position: absolute; top: -5px; left: -5px; background: #e74c3c; color: white; font-size: 11px; padding: 2px 6px; border-radius: 10px; font-weight: bold; }
        .timer-badge { background: #27ae60; color: white; padding: 8px 14px; border-radius: 6px; font-size: 13px; font-weight: bold; display: inline-flex; align-items: center; gap: 5px; }

        .info-bar { background: #2d6a4f; color: white; padding: 12px 20px; border-bottom: 2px solid var(--gold); text-align: center; }
        .info-time { font-size: 28px; font-weight: bold; color: var(--gold); margin-bottom: 5px; font-family: 'Segoe UI', sans-serif; }
        .info-date { font-size: 15px; margin-bottom: 10px; line-height: 1.9; }
        .info-date .hijri-date { color: var(--gold); font-weight: bold; font-size: 17px; }
        .info-date .greg-date { color: #e0f2e9; font-size: 15px; }
        .info-date .day-name { color: #ffffff; font-weight: bold; font-size: 17px; }
        .prayer-times { display: flex; justify-content: center; gap: 15px; flex-wrap: wrap; font-size: 14px; }
        .prayer-item { background: rgba(255,255,255,0.1); padding: 5px 12px; border-radius: 20px; display: flex; align-items: center; gap: 5px; }
        .prayer-item .name { color: var(--gold); font-weight: bold; }
        .location-info { font-size: 13px; color: #c9e6d0; margin-top: 5px; }

        .search-area { display: flex; gap: 6px; max-width: 900px; margin: 12px auto 0; align-items: center; flex-wrap: wrap; }
        .search-area input { flex: 1; padding: 10px 15px; border-radius: 8px; border: none; font-size: 15px; font-family: inherit; min-width: 200px; }
        .search-area button { background: var(--gold); border: none; padding: 10px 18px; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: bold; color: white; font-family: inherit; white-space: nowrap; }
        .search-area button:hover { background: #b8935a; }
        .search-area button.adv-btn { background: #27ae60; }
        .search-area button.adv-btn:hover { background: #1e8449; }

        .text-controls { display: flex; justify-content: center; align-items: center; gap: 8px; padding: 10px; background: #f5f5f0; border-bottom: 2px solid #ddd; flex-wrap: wrap; }
        .text-controls button { background: var(--main-green); color: white; border: none; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 14px; font-family: inherit; }
        .text-controls .size-display { background: white; padding: 6px 14px; border-radius: 6px; font-weight: bold; border: 1px solid #ccc; min-width: 40px; text-align: center; }

        .books-bar { background: var(--main-green); padding: 10px; overflow-x: auto; white-space: nowrap; }
        .books-bar::-webkit-scrollbar { height: 8px; }
        .books-bar::-webkit-scrollbar-thumb { background: var(--gold); border-radius: 4px; }
        .book-btn { display: inline-block; background: white; color: var(--main-green); border: 2px solid white; padding: 8px 16px; margin: 0 4px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: bold; font-family: inherit; transition: all 0.2s; }
        .book-btn:hover { background: #e8f5e9; }
        .book-btn.active { background: var(--gold); color: white; border-color: var(--gold); }

        .main-layout { display: flex; gap: 15px; max-width: 1300px; margin: 20px auto; padding: 0 15px; align-items: flex-start; }
        .content-area { flex: 1; min-width: 0; }

        .side-index { width: 300px; background: white; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.15); position: sticky; top: 20px; max-height: calc(100vh - 40px); overflow-y: auto; display: none; flex-shrink: 0; }
        .side-index.show { display: block; }
        .side-index-header { background: var(--main-green); color: white; padding: 12px 15px; font-weight: bold; border-radius: 12px 12px 0 0; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 5; }
        .side-index-header .close-btn { background: transparent; color: white; border: none; font-size: 18px; cursor: pointer; }
        .side-index-list { padding: 8px; }
        .side-index-item { padding: 10px; border-bottom: 1px solid #eee; cursor: pointer; border-radius: 6px; transition: all 0.2s; font-size: 14px; margin-bottom: 4px; }
        .side-index-item:hover { background: var(--light-green); transform: translateX(-3px); }
        .side-index-item.active { background: var(--gold); color: white; }
        .side-index-item .side-num { font-weight: bold; color: var(--main-green); font-size: 12px; margin-bottom: 4px; }
        .side-index-item.active .side-num { color: white; }
        .side-index-item .side-text { color: #555; font-size: 13px; line-height: 1.6; word-wrap: break-word; }
        .side-index-item.active .side-text { color: white; }

        .hadith-card { background: white; border-radius: 12px; padding: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border: 2px solid #d4d4d0; margin-bottom: 20px; }
        .hadith-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--light-green); padding-bottom: 10px; margin-bottom: 15px; flex-wrap: wrap; gap: 10px; }
        .hadith-book-name { color: var(--main-green); font-size: 18px; font-weight: bold; }
        .hadith-number { background: var(--main-green); color: white; padding: 5px 15px; border-radius: 20px; font-size: 14px; font-weight: bold; }
        .narrator { color: #b8860b; font-size: 16px; font-weight: bold; margin-bottom: 15px; padding: 8px 12px; background: #fdf6e3; border-right: 4px solid var(--gold); border-radius: 4px; }
        .hadith-text { font-size: 24px; line-height: 2.2; color: var(--text-dark); padding: 15px; background: #fafaf5; border-radius: 8px; text-align: right; }

        .surah-container { background: #fdfaf3; border: 3px double var(--gold); border-radius: 15px; padding: 25px; }
        .surah-header-bar { text-align: center; padding: 20px; background: linear-gradient(135deg, #1a4d2e 0%, #2d6a4f 100%); color: white; border-radius: 10px; margin-bottom: 20px; }
        .surah-header-bar h2 { font-size: 32px; color: var(--gold); margin-bottom: 8px; }
        .basmala { text-align: center; font-size: 28px; color: var(--main-green); font-weight: bold; margin: 20px 0; padding: 15px; border-top: 1px dashed var(--gold); border-bottom: 1px dashed var(--gold); font-family: 'Amiri', serif; }
        .ayah-line { font-size: 28px; line-height: 2.4; text-align: right; color: #1a3d2e; padding: 12px 18px; margin: 8px 0; border-radius: 8px; transition: all 0.2s; position: relative; }
        .ayah-line:hover { background: #f0f8f0; }
        .ayah-line.highlight { background: #fff3cd; box-shadow: 0 0 0 2px var(--gold); }
        .ayah-line.target-ayah { background: #fff9e6; border-right: 5px solid var(--gold); box-shadow: 0 0 10px rgba(201, 169, 97, 0.4); }
        .ayah-num-badge { display: inline-block; background: var(--gold); color: white; font-size: 14px; font-weight: bold; padding: 2px 10px; border-radius: 15px; margin: 0 8px; vertical-align: middle; font-family: sans-serif; }
        .ayah-actions { display: none; margin-top: 8px; gap: 8px; }
        .ayah-line:hover .ayah-actions { display: flex; flex-wrap: wrap; }
        .ayah-action-btn { background: var(--main-green); color: white; border: none; padding: 4px 12px; border-radius: 5px; cursor: pointer; font-size: 12px; font-family: inherit; }
        .tafsir-panel { display: none; background: #f0f9ff; border-right: 4px solid #28a745; padding: 15px; margin: 10px 0; border-radius: 8px; font-size: 20px; line-height: 2.2; }
        .tafsir-panel.show { display: block; }
        .tafsir-title { color: #28a745; font-weight: bold; margin-bottom: 8px; font-size: 15px; }

        .view-toggle { display: flex; gap: 8px; margin-bottom: 15px; padding: 10px; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); flex-wrap: wrap; }
        .view-toggle button { padding: 10px 20px; background: white; color: var(--main-green); border: 2px solid var(--main-green); border-radius: 8px; cursor: pointer; font-family: inherit; font-size: 15px; font-weight: bold; transition: all 0.2s; }
        .view-toggle button.active { background: var(--main-green); color: white; }
        .view-toggle button:hover:not(.active) { background: #e8f5e9; }
        .context-info { background: #fff9e6; padding: 12px 15px; border-radius: 8px; margin-bottom: 15px; border-right: 4px solid var(--gold); font-weight: bold; color: var(--main-green); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }

        .quran-tools { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; padding: 15px; background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        .quran-tools select, .quran-tools input { padding: 10px 15px; font-size: 16px; border-radius: 8px; border: 2px solid #ddd; font-family: inherit; flex: 1; min-width: 150px; }
        .quran-tools input:focus, .quran-tools select:focus { outline: none; border-color: var(--main-green); }
        .quran-tools button { padding: 10px 20px; background: var(--main-green); color: white; border: none; border-radius: 8px; cursor: pointer; font-family: inherit; font-size: 15px; font-weight: bold; }
        .quran-tools button:hover { background: #40916c; }

        .nav-buttons { display: flex; justify-content: center; gap: 10px; margin: 20px 0; flex-wrap: wrap; }
        .nav-btn { background: var(--main-green); color: white; border: none; padding: 12px 30px; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: bold; font-family: inherit; min-width: 120px; transition: all 0.2s; }
        .nav-btn:hover:not(:disabled) { background: #40916c; transform: translateY(-2px); }
        .nav-btn:disabled { background: #ccc; cursor: not-allowed; }

        .copy-buttons { display: flex; justify-content: center; gap: 10px; margin-top: 20px; flex-wrap: wrap; }
        .copy-btn { background: var(--gold); color: white; border: none; padding: 10px 24px; border-radius: 8px; cursor: pointer; font-size: 15px; font-family: inherit; font-weight: bold; }
        .copy-btn:hover { background: #b8935a; }

        .search-results { max-height: 700px; overflow-y: auto; margin-top: 15px; }
        .search-result-item { padding: 12px; border-bottom: 1px solid #eee; cursor: pointer; transition: background 0.2s; }
        .search-result-item:hover { background: var(--light-green); }
        .search-result-item .res-num { color: var(--main-green); font-weight: bold; font-size: 13px; }
        .search-result-item .res-text { font-size: 19px; line-height: 2; margin-top: 5px; }

        mark { background: #ffeb3b; color: #000; padding: 2px 6px; border-radius: 4px; font-weight: bold; box-shadow: 0 0 3px rgba(255,235,59,0.6); }

        .loading { text-align: center; padding: 40px; color: var(--main-green); font-size: 18px; }

        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1000; justify-content: center; align-items: center; padding: 20px; overflow-y: auto; }
        .modal-overlay.show { display: flex; }
        .modal-content { background: white; border-radius: 15px; padding: 25px; max-width: 700px; width: 100%; max-height: 90vh; overflow-y: auto; position: relative; border: 3px solid var(--gold); }
        .modal-close { position: absolute; top: 15px; left: 15px; background: #c0392b; color: white; border: none; width: 35px; height: 35px; border-radius: 50%; cursor: pointer; font-size: 20px; font-weight: bold; z-index: 10; }
        .modal-content h2 { text-align: center; color: var(--main-green); font-size: 24px; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid var(--gold); }

        .adv-search-row { display: flex; gap: 8px; margin-bottom: 15px; }
        .adv-search-input { flex: 1; padding: 12px 15px; font-size: 16px; border-radius: 8px; border: 2px solid #ddd; font-family: inherit; }
        .adv-search-inline-btn { background: var(--gold); color: white; border: none; padding: 12px 20px; border-radius: 8px; cursor: pointer; font-size: 15px; font-weight: bold; font-family: inherit; white-space: nowrap; }

        .books-selection { background: #f8f9fa; padding: 15px; border-radius: 10px; margin-bottom: 15px; max-height: 400px; overflow-y: auto; }
        .quick-select { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
        .quick-select button { padding: 8px 14px; background: var(--main-green); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; font-family: inherit; font-weight: bold; }
        .book-checkbox { display: flex; align-items: center; padding: 10px 12px; border-bottom: 1px solid #eee; cursor: pointer; background: white; border-radius: 6px; margin-bottom: 4px; }
        .book-checkbox:hover { background: var(--light-green); }
        .book-checkbox input { margin-left: 12px; width: 20px; height: 20px; cursor: pointer; flex-shrink: 0; }
        .book-checkbox label { flex: 1; cursor: pointer; font-size: 16px; font-weight: 500; }
        .book-checkbox.quran-special { background: #fff9e6; font-weight: bold; border: 2px solid var(--gold); border-radius: 8px; margin-bottom: 8px; }
        .adv-search-btn { width: 100%; padding: 14px; background: var(--main-green); color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 17px; font-weight: bold; font-family: inherit; }

        .adv-results-section { margin-bottom: 25px; }
        .adv-book-title { background: var(--main-green); color: white; padding: 10px 15px; border-radius: 8px; font-size: 17px; font-weight: bold; margin-bottom: 10px; display: flex; justify-content: space-between; }
        .adv-book-title .count { background: var(--gold); color: white; padding: 2px 10px; border-radius: 15px; font-size: 13px; }

        .notes-toolbar { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 15px; }
        .notes-toolbar button { padding: 8px 14px; background: var(--main-green); color: white; border: none; border-radius: 6px; cursor: pointer; font-family: inherit; font-weight: bold; font-size: 14px; }
        .notes-toolbar button.gold { background: var(--gold); }
        .notes-list { max-height: 400px; overflow-y: auto; }
        .note-card { background: #f9f9f9; padding: 15px; border-radius: 10px; margin-bottom: 12px; border-right: 4px solid var(--gold); }
        .note-card.category-quran { border-right-color: #27ae60; }
        .note-card.category-hadith { border-right-color: #2980b9; }
        .note-meta { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: 13px; color: #666; }
        .note-category-badge { padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; color: white; }
        .note-category-badge.general { background: #95a5a6; }
        .note-category-badge.quran { background: #27ae60; }
        .note-category-badge.hadith { background: #2980b9; }
        .note-source { background: #fff9e6; padding: 8px 12px; border-radius: 6px; margin: 8px 0; font-size: 14px; border-right: 3px solid var(--gold); }
        .note-text { font-size: 16px; line-height: 1.8; margin: 8px 0; }
        .note-actions { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
        .note-actions button { padding: 5px 12px; font-size: 12px; border: none; border-radius: 5px; cursor: pointer; font-family: inherit; color: white; }
        .note-actions .edit { background: #3498db; }
        .note-actions .delete { background: #e74c3c; }
        .note-actions .copy { background: #95a5a6; }
        .note-actions .goto { background: var(--gold); }
        .note-form { background: #f0f8f0; padding: 15px; border-radius: 10px; margin-bottom: 15px; display: none; }
        .note-form.show { display: block; }
        .note-form textarea { width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 8px; font-family: inherit; font-size: 15px; min-height: 100px; resize: vertical; }
        .note-form select { padding: 8px 12px; border-radius: 6px; border: 2px solid #ddd; font-family: inherit; margin: 10px 0; }
        .note-form .btn-row { display: flex; gap: 8px; margin-top: 10px; }
        .note-form .btn-row button { padding: 8px 20px; border: none; border-radius: 6px; cursor: pointer; font-family: inherit; font-weight: bold; color: white; }
        .note-form .save-btn { background: var(--main-green); }
        .note-form .cancel-btn { background: #95a5a6; }
        .notes-search { width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 8px; margin-bottom: 12px; font-family: inherit; }
        .filter-buttons { display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }
        .filter-buttons button { padding: 6px 14px; border-radius: 6px; border: 2px solid var(--main-green); background: white; color: var(--main-green); cursor: pointer; font-family: inherit; font-size: 13px; font-weight: bold; }
        .filter-buttons button.active { background: var(--main-green); color: white; }
        .empty-msg { text-align: center; padding: 30px; color: #999; font-size: 16px; }

        .bookmark-list { max-height: 400px; overflow-y: auto; }
        .bookmark-item { padding: 12px; border-bottom: 1px solid #eee; cursor: pointer; transition: background 0.2s; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; gap: 10px; }
        .bookmark-item:hover { background: var(--light-green); }
        .bookmark-info { flex: 1; }
        .bookmark-title { font-weight: bold; color: var(--main-green); font-size: 15px; margin-bottom: 4px; }
        .bookmark-preview { font-size: 13px; color: #666; line-height: 1.5; }
        .bookmark-delete { background: #e74c3c; color: white; border: none; padding: 5px 10px; border-radius: 5px; cursor: pointer; font-size: 13px; }

        @media (max-width: 900px) {
            .main-layout { flex-direction: column; }
            .side-index { width: 100%; position: relative; max-height: 400px; }
        }
        @media (max-width: 600px) {
            .header h1 { font-size: 20px; }
            .hadith-text { font-size: 20px; }
            .hadith-card { padding: 15px; }
            .nav-btn { padding: 10px 20px; font-size: 14px; min-width: 90px; }
            .book-btn { font-size: 12px; padding: 6px 12px; }
            .info-time { font-size: 22px; }
            .prayer-times { gap: 8px; font-size: 12px; }
            .ayah-line { font-size: 24px; line-height: 2.2; }
            .top-btn { font-size: 12px; padding: 6px 10px; }
            .search-area button { padding: 10px 12px; font-size: 13px; }
        }

        body.dark-mode { --bg: #1a1a1a; --text-dark: #e0e0e0; }
        body.dark-mode .hadith-card, body.dark-mode .modal-content, body.dark-mode .quran-tools, body.dark-mode .side-index, body.dark-mode .view-toggle { background: #2a2a2a; border-color: #444; color: #e0e0e0; }
        body.dark-mode .hadith-text { background: #333; color: #e0e0e0; }
        body.dark-mode .surah-container { background: #222; border-color: var(--gold); }
        body.dark-mode .ayah-line { color: #e0e0e0; }
        body.dark-mode .text-controls { background: #2a2a2a; border-color: #444; }
        body.dark-mode .narrator { background: #3a3a2a; color: #e0c060; }
        body.dark-mode .search-area input { background: #333; color: white; }
        body.dark-mode .books-selection { background: #333; }
        body.dark-mode .book-checkbox { background: #2a2a2a; border-color: #444; color: #e0e0e0; }
        body.dark-mode .tafsir-panel { background: #1e3a2f; color: #ddd; }
        body.dark-mode .adv-search-input { background: #333; color: white; }
        body.dark-mode .note-card { background: #333; color: #e0e0e0; }
        body.dark-mode .note-form { background: #2a3a2a; }
        body.dark-mode .notes-search { background: #333; color: white; border-color: #555; }
        body.dark-mode .note-form textarea { background: #333; color: white; }
    </style>
</head>
<body>

<div class="header">
    <h1>🕌 الموسوعة الإسلامية الشاملة 📚</h1>
    <div class="top-actions">
        <button class="top-btn" onclick="toggleDark()">🌙 ليلي</button>
        <button class="top-btn" onclick="detectLocation()">📍 الموقع</button>
        <button class="top-btn" onclick="showBookmarksList()">📑 العلامات <span class="badge" id="bookmarkBadge" style="display:none;">0</span></button>
        <button class="top-btn" onclick="showNotesModal()">🗒️ ملاحظاتي <span class="badge" id="notesBadge" style="display:none;">0</span></button>
        <button class="top-btn" onclick="showAbout()">ℹ️ حول</button>
        <span class="timer-badge" id="readingTimer">⏱️ 00:00</span>
    </div>
    <div class="search-area">
        <input type="text" id="searchInput" placeholder="ابحث في الكتاب الحالي..." onkeydown="if(event.key==='Enter') doSearch()">
        <button onclick="doSearch()">🔍 بحث</button>
        <button class="adv-btn" onclick="showAdvancedSearch()">🔎 بحث متقدم</button>
    </div>
</div>

<div class="info-bar">
    <div class="info-time" id="currentTime">--:--:--</div>
    <div class="info-date">
        <div class="day-name" id="dayName">...</div>
        <div class="hijri-date" id="hijriDate">--</div>
        <div class="greg-date" id="gregorianDate">--</div>
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
    <button onclick="changeFontSize(1)">➕ تكبير</button>
    <span class="size-display" id="fontSizeDisplay">24</span>
    <button onclick="changeFontSize(-1)">➖ تصغير</button>
    <button onclick="resetFontSize()">↺ افتراضي</button>
</div>

<div class="books-bar">
    <button class="book-btn" onclick="selectQuran()" id="quranBtn">📖 القرآن الكريم</button>
    {% for key, value in books.items() %}
    <button class="book-btn" data-book="{{ key }}" onclick="selectBook('{{ key }}')">{{ value }}</button>
    {% endfor %}
</div>

<div class="main-layout">
    <div class="content-area">
        <div id="content">
            <div class="loading">اختر كتاباً من الأعلى للبدء 🕌</div>
        </div>
    </div>
    <div class="side-index" id="sideIndex">
        <div class="side-index-header">
            <span>📋 فهرس النتائج (<span id="sideIndexCount">0</span>)</span>
            <button class="close-btn" onclick="hideSideIndex()">✕</button>
        </div>
        <div class="side-index-list" id="sideIndexList"></div>
    </div>
</div>

<div class="modal-overlay" id="advSearchModal" onclick="if(event.target===this) hideAdvancedSearch()">
    <div class="modal-content">
        <button class="modal-close" onclick="hideAdvancedSearch()">✕</button>
        <h2>🔎 البحث المتقدم</h2>
        <div class="adv-search-row">
            <input type="text" class="adv-search-input" id="advSearchInput" placeholder="اكتب كلمة للبحث..." onkeydown="if(event.key==='Enter') doAdvancedSearch()">
            <button class="adv-search-inline-btn" onclick="doAdvancedSearch()">🔍</button>
        </div>
        <div class="books-selection">
            <div class="quick-select">
                <button onclick="selectAllBooks()">✅ كل الكتب</button>
                <button onclick="deselectAllBooks()">❌ مسح</button>
                <button onclick="selectOnlyQuran()">📖 القرآن</button>
                <button onclick="selectOnly9Books()">📚 التسعة</button>
            </div>
            <div class="book-checkbox quran-special">
                <input type="checkbox" id="chk_quran" value="quran">
                <label for="chk_quran">📖 القرآن الكريم كاملاً</label>
            </div>
            {% for key, value in books.items() %}
            <div class="book-checkbox">
                <input type="checkbox" id="chk_{{ key }}" class="book-chk" value="{{ key }}">
                <label for="chk_{{ key }}">{{ value }}</label>
            </div>
            {% endfor %}
        </div>
        <button class="adv-search-btn" onclick="doAdvancedSearch()">🔍 ابحث الآن</button>
    </div>
</div>

<div class="modal-overlay" id="notesModal" onclick="if(event.target===this) hideNotesModal()">
    <div class="modal-content">
        <button class="modal-close" onclick="hideNotesModal()">✕</button>
        <h2>🗒️ ملاحظاتي</h2>
        <div class="notes-toolbar">
            <button onclick="showNoteForm()">➕ ملاحظة جديدة</button>
            <button class="gold" onclick="exportNotes()">📥 تصدير</button>
            <button class="gold" onclick="copyAllNotes()">📋 نسخ الكل</button>
        </div>
        <div class="note-form" id="noteForm">
            <textarea id="noteText" placeholder="اكتب ملاحظتك هنا..."></textarea>
            <select id="noteCategory">
                <option value="general">📝 عام</option>
                <option value="quran">📖 قرآن</option>
                <option value="hadith">📚 حديث</option>
            </select>
            <div class="btn-row">
                <button class="save-btn" onclick="saveNote()">💾 حفظ</button>
                <button class="cancel-btn" onclick="hideNoteForm()">إلغاء</button>
            </div>
        </div>
        <input type="text" class="notes-search" id="notesSearch" placeholder="🔍 ابحث في الملاحظات..." oninput="renderNotes()">
        <div class="filter-buttons">
            <button class="active" onclick="filterNotes('all', this)">🔍 الكل</button>
            <button onclick="filterNotes('general', this)">📝 عام</button>
            <button onclick="filterNotes('quran', this)">📖 قرآن</button>
            <button onclick="filterNotes('hadith', this)">📚 حديث</button>
        </div>
        <div class="notes-list" id="notesList"></div>
    </div>
</div>

<div class="modal-overlay" id="bookmarksModal" onclick="if(event.target===this) hideBookmarksList()">
    <div class="modal-content">
        <button class="modal-close" onclick="hideBookmarksList()">✕</button>
        <h2>📑 العلامات المرجعية</h2>
        <div class="bookmark-list" id="bookmarksList"></div>
    </div>
</div>

<div class="modal-overlay" id="aboutModal" onclick="if(event.target===this) hideAbout()">
    <div class="modal-content">
        <button class="modal-close" onclick="hideAbout()">✕</button>
        <h2>🕌 حول التطبيق 📚</h2>
        <div style="background: linear-gradient(135deg, #1a4d2e 0%, #2d6a4f 100%); color:white; padding:20px; border-radius:12px; text-align:center; margin-bottom:20px;">
            <div style="font-size:24px; color:var(--gold); font-weight:bold; margin-bottom:15px;">👤 حسان مارديني</div>
            <div style="display:flex; flex-direction:column; gap:10px;">
                <a href="tel:+905060917640" style="display:flex; align-items:center; justify-content:center; gap:10px; background:rgba(255,255,255,0.15); color:white; padding:10px 20px; border-radius:8px; text-decoration:none;">📞 <span>+90 506 091 7640</span></a>
                <a href="mailto:hassanmardinli21@gmail.com" style="display:flex; align-items:center; justify-content:center; gap:10px; background:rgba(255,255,255,0.15); color:white; padding:10px 20px; border-radius:8px; text-decoration:none;">📧 <span>hassanmardinli21@gmail.com</span></a>
                <a href="https://wa.me/905060917640" target="_blank" style="display:flex; align-items:center; justify-content:center; gap:10px; background:rgba(255,255,255,0.15); color:white; padding:10px 20px; border-radius:8px; text-decoration:none;">💬 <span>واتساب</span></a>
            </div>
        </div>
        <div style="text-align:center; font-size:17px; line-height:2; color:#1a4d2e; padding:15px; background:#fff9e6; border-radius:10px; border-right:4px solid var(--gold); margin-bottom:12px;">🤲 اللَّهُمَّ اجْعَلْ هَذَا الْعَمَلَ خَالِصًا لِوَجْهِكَ الْكَرِيمِ</div>
        <div style="text-align:center; font-size:17px; line-height:2; color:#1a4d2e; padding:15px; background:#fff9e6; border-radius:10px; border-right:4px solid var(--gold);">🤲 اللَّهُمَّ اغْفِرْ لَنَا وَلِوَالِدِينَا وَلِوَالِدِي وَالِدِينَا</div>
    </div>
</div>

<script>
    let currentBook = null;
    let currentIndex = 0;
    let currentSurah = 1;
    let currentSurahData = null;
    let currentAyahIndex = 0;
    let fontSize = 24;
    let bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
    let notes = JSON.parse(localStorage.getItem('notes') || '[]');
    let currentSearchQuery = '';
    let notesFilter = 'all';
    let editingNoteId = null;
    let readingSeconds = 0;
    let readingTimerInterval = null;
    let surahSearchQuery = '';
    let quranViewMode = 'full';
    let contextAyahNum = null;

    function startReadingTimer() {
        if (readingTimerInterval) clearInterval(readingTimerInterval);
        readingTimerInterval = setInterval(() => { readingSeconds++; updateTimerDisplay(); }, 1000);
    }
    function updateTimerDisplay() {
        const h = Math.floor(readingSeconds / 3600);
        const m = Math.floor((readingSeconds % 3600) / 60);
        const s = readingSeconds % 60;
        const pad = (n) => String(n).padStart(2, '0');
        document.getElementById('readingTimer').innerText = `⏱️ ${h > 0 ? pad(h) + ':' : ''}${pad(m)}:${pad(s)}`;
    }

    const SYRIAN_MONTHS = ['كانون الثاني','شباط','آذار','نيسان','أيار','حزيران','تموز','آب','أيلول','تشرين الأول','تشرين الثاني','كانون الأول'];
    const ARABIC_DAYS = ['الأحد','الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت'];
    const HIJRI_MONTHS = ['محرّم','صفر','ربيع الأول','ربيع الآخر','جمادى الأولى','جمادى الآخرة','رجب','شعبان','رمضان','شوّال','ذو القعدة','ذو الحجة'];

    function toHijri(date) {
        let d = date.getDate(), m = date.getMonth() + 1, y = date.getFullYear();
        if (m < 3) { y -= 1; m += 12; }
        let a = Math.floor(y / 100), b = 2 - a + Math.floor(a / 4);
        if (y < 1583) b = 0;
        if (y === 1582) { if (m > 10) b = -10; if (m === 10) { b = 0; if (d > 4) b = -10; } }
        let jd = Math.floor(365.25 * (y + 4716)) + Math.floor(30.6001 * (m + 1)) + d + b - 1524;
        b = 0;
        if (jd > 2299160) { a = Math.floor((jd - 1867216.25) / 36524.25); b = 1 + a - Math.floor(a / 4); }
        let bb = jd + b + 1524, cc = Math.floor((bb - 122.1) / 365.25), dd = Math.floor(365.25 * cc);
        let ee = Math.floor((bb - dd) / 30.6001);
        d = bb - dd - Math.floor(30.6001 * ee);
        m = ee < 14 ? ee - 1 : ee - 13;
        y = m > 2 ? cc - 4716 : cc - 4715;
        let jdH = Math.floor((11 * y + 3) / 30) + 354 * y + Math.floor(30 * (m - 1)) - Math.floor((m - 1) / 2) + d + 1948440 - 385;
        let l = jdH - 1948440 + 10632, n = Math.floor((l - 1) / 10631);
        l = l - 10631 * n + 354;
        let j = Math.floor((10985 - l) / 5316) * Math.floor((50 * l) / 17719) + Math.floor(l / 5670) * Math.floor((43 * l) / 15238);
        l = l - Math.floor((30 - j) / 15) * Math.floor((17719 * j) / 50) - Math.floor(j / 16) * Math.floor((15238 * j) / 43) + 29;
        let hM = Math.floor((24 * l) / 709), hD = l - Math.floor((709 * hM) / 24), hY = 30 * n + j - 30;
        return { day: hD, month: hM, year: hY };
    }

    function updateTime() {
        const now = new Date();
        document.getElementById('currentTime').innerText = now.toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
        document.getElementById('dayName').innerText = '📆 ' + ARABIC_DAYS[now.getDay()];
        try {
            const h = toHijri(now);
            document.getElementById('hijriDate').innerText = `🌙 ${h.day} ${HIJRI_MONTHS[h.month - 1]} ${h.year} هـ`;
        } catch(e) {}
        document.getElementById('gregorianDate').innerText = `📅 ${now.getDate()} ${SYRIAN_MONTHS[now.getMonth()]} ${now.getFullYear()} م`;
    }
    setInterval(updateTime, 1000);
    updateTime();

    function detectLocation() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (p) => { calculatePrayerTimes(p.coords.latitude, p.coords.longitude); reverseGeocode(p.coords.latitude, p.coords.longitude); },
                () => { document.getElementById('locationInfo').innerText = '📍 مكة المكرمة'; calculatePrayerTimes(21.4225, 39.8262); }
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
        } catch(e) { document.getElementById('locationInfo').innerText = `📍 ${lat.toFixed(2)}, ${lng.toFixed(2)}`; }
    }
    function calculatePrayerTimes(lat, lng) {
        try {
            const c = new adhan.Coordinates(lat, lng);
            const p = adhan.CalculationMethod.MuslimWorldLeague();
            const pt = new adhan.PrayerTimes(c, new Date(), p);
            const fmt = (d) => d ? d.toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit', hour12: true }) : '--:--';
            document.getElementById('fajrTime').innerText = fmt(pt.fajr);
            document.getElementById('sunriseTime').innerText = fmt(pt.sunrise);
            document.getElementById('dhuhrTime').innerText = fmt(pt.dhuhr);
            document.getElementById('asrTime').innerText = fmt(pt.asr);
            document.getElementById('maghribTime').innerText = fmt(pt.maghrib);
            document.getElementById('ishaTime').innerText = fmt(pt.isha);
        } catch(e) {}
    }
    detectLocation();

    function escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }

    // ============ التمييز المتقدم (يحل مشكلة التشكيل والهمزات) ============
    function isDiacritic(ch) {
        if (!ch) return false;
        const code = ch.charCodeAt(0);
        return (code >= 0x064B && code <= 0x0655) || code === 0x0670 || code === 0x0640 ||
               (code >= 0x06D6 && code <= 0x06ED);
    }
    function charsMatch(textChar, queryChar) {
        if (textChar === queryChar) return true;
        if ('اأإآٱ'.indexOf(textChar) !== -1 && 'اأإآٱ'.indexOf(queryChar) !== -1) return true;
        if ('ىي'.indexOf(textChar) !== -1 && 'ىي'.indexOf(queryChar) !== -1) return true;
        if ('ةه'.indexOf(textChar) !== -1 && 'ةه'.indexOf(queryChar) !== -1) return true;
        if ('وؤ'.indexOf(textChar) !== -1 && 'وؤ'.indexOf(queryChar) !== -1) return true;
        return false;
    }
    function safeHighlight(text, query) {
        if (!text) return '';
        const escapedText = escapeHtml(text);
        if (!query) return escapedText;
        const safeQuery = String(query).trim();
        if (!safeQuery) return escapedText;
        const normQuery = safeQuery.split('').filter(ch => !isDiacritic(ch)).join('');
        if (!normQuery) return escapedText;
        let result = '';
        let i = 0;
        while (i < escapedText.length) {
            const matchStart = i;
            let ti = i;
            let qi = 0;
            while (qi < normQuery.length && ti < escapedText.length) {
                const tch = escapedText[ti];
                if (isDiacritic(tch)) { ti++; continue; }
                if (charsMatch(tch, normQuery[qi])) { ti++; qi++; }
                else break;
            }
            if (qi === normQuery.length) {
                while (ti < escapedText.length && isDiacritic(escapedText[ti])) ti++;
                result += '<mark>' + escapedText.substring(matchStart, ti) + '</mark>';
                i = ti;
            } else {
                result += escapedText[i];
                i++;
            }
        }
        return result;
    }

    function toggleDark() {
        document.body.classList.toggle('dark-mode');
        localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
    }
    if (localStorage.getItem('darkMode') === 'true') document.body.classList.add('dark-mode');

    function changeFontSize(d) {
        fontSize = Math.max(16, Math.min(48, fontSize + d));
        document.getElementById('fontSizeDisplay').innerText = fontSize;
        document.querySelectorAll('.hadith-text, .ayah-line').forEach(el => el.style.fontSize = fontSize + 'px');
    }
    function resetFontSize() {
        fontSize = 24;
        document.getElementById('fontSizeDisplay').innerText = fontSize;
        document.querySelectorAll('.hadith-text, .ayah-line').forEach(el => el.style.fontSize = fontSize + 'px');
    }

    // ===== العلامات =====
    function saveBookmarks() { localStorage.setItem('bookmarks', JSON.stringify(bookmarks)); updateBookmarkBadge(); }
    function updateBookmarkBadge() {
        const badge = document.getElementById('bookmarkBadge');
        if (bookmarks.length > 0) { badge.innerText = bookmarks.length; badge.style.display = 'inline-block'; }
        else badge.style.display = 'none';
    }
    function toggleBookmark() {
        if (!currentBook) { alert('افتح كتاباً أولاً'); return; }
        const isQuran = currentBook === 'quran';
        const key = isQuran ? `quran_${currentSurah}_${currentAyahIndex}` : `${currentBook}_${currentIndex}`;
        const existingIdx = bookmarks.findIndex(b => b.key === key);
        if (existingIdx >= 0) { bookmarks.splice(existingIdx, 1); alert('🗑️ تم حذف العلامة'); }
        else {
            const previewText = isQuran && currentSurahData
                ? (currentSurahData.ayahs[currentAyahIndex]?.text || '').substring(0, 100)
                : (document.getElementById('hadithText')?.innerText || '').substring(0, 100);
            bookmarks.push({
                key, book: currentBook, bookName: getBookName(currentBook),
                index: isQuran ? currentAyahIndex : currentIndex,
                surah: isQuran ? currentSurah : null,
                surahName: isQuran && currentSurahData ? currentSurahData.name : null,
                preview: previewText, time: Date.now()
            });
            alert('✅ تمت إضافة العلامة');
        }
        saveBookmarks();
        if (document.getElementById('bookmarksModal').classList.contains('show')) renderBookmarksList();
    }
    function showBookmarksList() { document.getElementById('bookmarksModal').classList.add('show'); renderBookmarksList(); }
    function hideBookmarksList() { document.getElementById('bookmarksModal').classList.remove('show'); }
    function renderBookmarksList() {
        const list = document.getElementById('bookmarksList');
        if (bookmarks.length === 0) { list.innerHTML = '<div class="empty-msg">لا توجد علامات بعد 📑</div>'; return; }
        bookmarks.sort((a, b) => b.time - a.time);
        let html = '';
        bookmarks.forEach((b, i) => {
            html += `<div class="bookmark-item">
                        <div class="bookmark-info" onclick="gotoBookmark(${i})" style="cursor:pointer;flex:1;">
                            <div class="bookmark-title">${b.book === 'quran' ? '📖' : '📚'} ${escapeHtml(b.bookName)}${b.surahName ? ' - سورة ' + escapeHtml(b.surahName) : ''}</div>
                            <div class="bookmark-preview">${escapeHtml(b.preview)}...</div>
                        </div>
                        <button class="bookmark-delete" onclick="event.stopPropagation(); deleteBookmark(${i})">🗑️</button>
                    </div>`;
        });
        list.innerHTML = html;
    }
    function gotoBookmark(i) {
        const b = bookmarks[i];
        hideBookmarksList();
        if (b.book === 'quran') {
            currentBook = 'quran'; setActiveBook('quran');
            surahSearchQuery = '';
            quranViewMode = 'context';
            contextAyahNum = currentSurahData?.ayahs?.[b.index]?.ayah || null;
            showSurah(b.surah).then(() => {
                if (currentSurahData && currentSurahData.ayahs[b.index]) {
                    contextAyahNum = currentSurahData.ayahs[b.index].ayah;
                    quranViewMode = 'context';
                    renderFullSurah();
                    setTimeout(() => scrollToAyah(contextAyahNum), 400);
                }
            });
        } else {
            currentBook = b.book; setActiveBook(b.book); currentSearchQuery = ''; showHadith(b.index);
        }
    }
    function deleteBookmark(i) { if (confirm('حذف هذه العلامة؟')) { bookmarks.splice(i, 1); saveBookmarks(); renderBookmarksList(); } }

    // ===== الملاحظات =====
    function saveNotes() { localStorage.setItem('notes', JSON.stringify(notes)); updateNotesBadge(); }
    function updateNotesBadge() {
        const badge = document.getElementById('notesBadge');
        if (notes.length > 0) { badge.innerText = notes.length; badge.style.display = 'inline-block'; }
        else badge.style.display = 'none';
    }
    function showNotesModal() { document.getElementById('notesModal').classList.add('show'); renderNotes(); }
    function hideNotesModal() { document.getElementById('notesModal').classList.remove('show'); hideNoteForm(); }
    function showNoteForm(note) {
        editingNoteId = note ? note.id : null;
        document.getElementById('noteText').value = note ? note.text : '';
        document.getElementById('noteCategory').value = note ? note.category : 'general';
        document.getElementById('noteForm').classList.add('show');
    }
    function hideNoteForm() {
        document.getElementById('noteForm').classList.remove('show');
        document.getElementById('noteText').value = '';
        editingNoteId = null;
    }
    function saveNote() {
        const text = document.getElementById('noteText').value.trim();
        const category = document.getElementById('noteCategory').value;
        if (!text) { alert('اكتب نص الملاحظة'); return; }
        if (editingNoteId) {
            const note = notes.find(n => n.id === editingNoteId);
            if (note) { note.text = text; note.category = category; note.updatedAt = Date.now(); }
        } else {
            notes.push({ id: 'note_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5), text, category, createdAt: Date.now(), source: getCurrentSource() });
        }
        saveNotes(); hideNoteForm(); renderNotes();
    }
    function getCurrentSource() {
        if (!currentBook) return null;
        if (currentBook === 'quran' && currentSurahData) {
            const ayah = currentSurahData.ayahs[currentAyahIndex];
            if (!ayah) return null;
            return { type: 'quran', surah: currentSurah, surahName: currentSurahData.name, ayah: ayah.ayah, ayahText: ayah.text.substring(0, 200) };
        }
        const hadithEl = document.getElementById('hadithText');
        if (hadithEl && currentBook) {
            return { type: 'hadith', book: currentBook, bookName: getBookName(currentBook), index: currentIndex, hadithText: hadithEl.innerText.substring(0, 200) };
        }
        return null;
    }
    function renderNotes() {
        const list = document.getElementById('notesList');
        const search = (document.getElementById('notesSearch').value || '').toLowerCase();
        let filtered = notes.filter(n => {
            if (notesFilter !== 'all' && n.category !== notesFilter) return false;
            if (search && !n.text.toLowerCase().includes(search) && !(n.source?.ayahText || '').toLowerCase().includes(search) && !(n.source?.hadithText || '').toLowerCase().includes(search)) return false;
            return true;
        });
        filtered.sort((a, b) => b.createdAt - a.createdAt);
        if (filtered.length === 0) { list.innerHTML = '<div class="empty-msg">لا توجد ملاحظات 🗒️</div>'; return; }
        let html = '';
        filtered.forEach(n => {
            const catLabel = { general: '📝 عام', quran: '📖 قرآن', hadith: '📚 حديث' }[n.category] || 'عام';
            const catClass = n.category;
            let sourceHtml = '';
            if (n.source) {
                if (n.source.type === 'quran') sourceHtml = `<div class="note-source">📖 سورة ${escapeHtml(n.source.surahName)} - آية ${n.source.ayah}: ${escapeHtml((n.source.ayahText || '').substring(0, 80))}...</div>`;
                else sourceHtml = `<div class="note-source">📚 ${escapeHtml(n.source.bookName)} - حديث ${n.source.index + 1}: ${escapeHtml((n.source.hadithText || '').substring(0, 80))}...</div>`;
            }
            html += `<div class="note-card category-${catClass}">
                        <div class="note-meta">
                            <span class="note-category-badge ${catClass}">${catLabel}</span>
                            <span>${new Date(n.createdAt).toLocaleDateString('ar-SA')}</span>
                        </div>
                        ${sourceHtml}
                        <div class="note-text">${escapeHtml(n.text)}</div>
                        <div class="note-actions">
                            <button class="edit" onclick="editNote('${n.id}')">✏️ تعديل</button>
                            <button class="copy" onclick="copyNote('${n.id}')">📋 نسخ</button>
                            ${n.source ? `<button class="goto" onclick="gotoNoteSource('${n.id}')">📍 المصدر</button>` : ''}
                            <button class="delete" onclick="deleteNote('${n.id}')">🗑️ حذف</button>
                        </div>
                    </div>`;
        });
        list.innerHTML = html;
    }
    function editNote(id) { const note = notes.find(n => n.id === id); if (note) showNoteForm(note); }
    function deleteNote(id) { if (confirm('حذف هذه الملاحظة؟')) { notes = notes.filter(n => n.id !== id); saveNotes(); renderNotes(); } }
    function copyNote(id) {
        const note = notes.find(n => n.id === id);
        if (!note) return;
        let text = note.text;
        if (note.source) {
            if (note.source.type === 'quran') text = `📖 سورة ${note.source.surahName} - آية ${note.source.ayah}\n${note.source.ayahText}\n\n📝 ملاحظتي:\n${note.text}`;
            else text = `📚 ${note.source.bookName} - حديث ${note.source.index + 1}\n${note.source.hadithText}\n\n📝 ملاحظتي:\n${note.text}`;
        }
        navigator.clipboard.writeText(text).then(() => alert('✅ تم نسخ الملاحظة'));
    }
    function copyAllNotes() {
        if (notes.length === 0) { alert('لا توجد ملاحظات'); return; }
        let text = '═══ ملاحظاتي - الموسوعة الإسلامية ═══\n\n';
        notes.forEach((n, i) => {
            text += `[${i + 1}] ${new Date(n.createdAt).toLocaleDateString('ar-SA')}\n`;
            if (n.source) {
                if (n.source.type === 'quran') text += `📖 سورة ${n.source.surahName} - آية ${n.source.ayah}\n`;
                else text += `📚 ${n.source.bookName} - حديث ${n.source.index + 1}\n`;
            }
            text += `────────────────\n${n.text}\n\n`;
        });
        navigator.clipboard.writeText(text).then(() => alert('✅ تم نسخ جميع الملاحظات'));
    }
    function exportNotes() {
        if (notes.length === 0) { alert('لا توجد ملاحظات'); return; }
        let text = '═══ ملاحظاتي - الموسوعة الإسلامية ═══\n';
        text += `التاريخ: ${new Date().toLocaleDateString('ar-SA')}\n`;
        text += `العدد: ${notes.length} ملاحظة\n\n`;
        notes.sort((a, b) => b.createdAt - a.createdAt);
        notes.forEach((n, i) => {
            const catLabel = { general: 'عام', quran: 'قرآن', hadith: 'حديث' }[n.category] || 'عام';
            text += `[${i + 1}] [${catLabel}] ${new Date(n.createdAt).toLocaleDateString('ar-SA')}\n`;
            if (n.source) {
                if (n.source.type === 'quran') text += `المصدر: 📖 سورة ${n.source.surahName} - آية ${n.source.ayah}\nالآية: ${n.source.ayahText}\n`;
                else text += `المصدر: 📚 ${n.source.bookName} - حديث ${n.source.index + 1}\nالحديث: ${n.source.hadithText}\n`;
                text += `────────────────\n`;
            }
            text += `📝 ملاحظتي:\n${n.text}\n\n`;
        });
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `ملاحظاتي_${new Date().toISOString().split('T')[0]}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    }
    function gotoNoteSource(id) {
        const note = notes.find(n => n.id === id);
        if (!note || !note.source) return;
        hideNotesModal();
        if (note.source.type === 'quran') {
            currentBook = 'quran'; setActiveBook('quran');
            surahSearchQuery = '';
            contextAyahNum = note.source.ayah;
            quranViewMode = 'context';
            showSurah(note.source.surah).then(() => {
                setTimeout(() => scrollToAyah(note.source.ayah), 400);
            });
        } else {
            currentBook = note.source.book; setActiveBook(note.source.book); showHadith(note.source.index);
        }
    }
    function filterNotes(filter, btn) {
        notesFilter = filter;
        document.querySelectorAll('.filter-buttons button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderNotes();
    }

    // ===== الفهرس الجانبي =====
    function showSideIndex(items, type) {
        const sideIndex = document.getElementById('sideIndex');
        const list = document.getElementById('sideIndexList');
        document.getElementById('sideIndexCount').innerText = items.length;
        let html = '';
        items.forEach((item, i) => {
            const title = type === 'quran'
                ? `سورة ${item.surah_name} - آية ${item.ayah}`
                : `📌 حديث رقم ${item.id}`;
            const preview = (item.text || '').substring(0, 120);
            html += `<div class="side-index-item" data-index="${i}" onclick="gotoSideIndexItem(${i}, '${type}')">
                        <div class="side-num">${title}</div>
                        <div class="side-text">${escapeHtml(preview)}...</div>
                    </div>`;
        });
        list.innerHTML = html;
        sideIndex.classList.add('show');
        window._sideIndexItems = items;
        window._sideIndexType = type;
    }
    function hideSideIndex() { document.getElementById('sideIndex').classList.remove('show'); }
    function gotoSideIndexItem(i, type) {
        const items = window._sideIndexItems;
        if (!items || !items[i]) return;
        const item = items[i];
        document.querySelectorAll('.side-index-item').forEach(el => el.classList.remove('active'));
        document.querySelector(`.side-index-item[data-index="${i}"]`)?.classList.add('active');
        if (type === 'quran') {
            currentBook = 'quran'; setActiveBook('quran');
            contextAyahNum = item.ayah;
            quranViewMode = 'context';
            renderFullSurah();
            setTimeout(() => scrollToAyah(item.ayah), 300);
        } else {
            showHadith(item.index);
        }
    }

    // ===== البحث العادي =====
    async function doSearch() {
        const query = document.getElementById('searchInput').value.trim();
        if (!query) { alert('اكتب كلمة للبحث'); return; }
        currentSearchQuery = query;
        surahSearchQuery = '';
        const content = document.getElementById('content');
        content.innerHTML = '<div class="loading">جاري البحث...</div>';
        hideSideIndex();

        if (currentBook === 'quran') {
            try {
                const res = await fetch(`/api/search_quran?query=${encodeURIComponent(query)}`);
                const data = await res.json();
                if (data.length === 0) {
                    content.innerHTML = `<div class="hadith-card" style="text-align:center;">لا توجد نتائج لـ "${escapeHtml(query)}" في القرآن الكريم</div>`;
                    return;
                }
                let html = `<div class="hadith-card">
                                <div class="hadith-header">
                                    <span class="hadith-book-name">🔍 نتائج البحث في القرآن الكريم</span>
                                    <span class="hadith-number">${data.length} نتيجة</span>
                                </div>
                                <div class="search-results">`;
                data.forEach(item => {
                    const preview = item.text.length > 250 ? item.text.substring(0, 250) + '...' : item.text;
                    html += `<div class="search-result-item" onclick="gotoQuranResult(${item.surah}, ${item.ayah}, '${query.replace(/'/g, "\\'")}')">
                                <div class="res-num">📖 سورة ${escapeHtml(item.surah_name)} - آية ${item.ayah}</div>
                                <div class="res-text">${safeHighlight(preview, query)}</div>
                            </div>`;
                });
                html += '</div></div>';
                content.innerHTML = html;
                showSideIndex(data, 'quran');
            } catch(e) {
                content.innerHTML = '<div class="hadith-card" style="text-align:center;color:red;">حدث خطأ في البحث</div>';
            }
            return;
        }

        if (!currentBook) { currentBook = 'bukhari'; setActiveBook('bukhari'); }
        try {
            const res = await fetch(`/api/search?book=${currentBook}&query=${encodeURIComponent(query)}`);
            const data = await res.json();
            if (!Array.isArray(data) || data.length === 0) {
                content.innerHTML = `<div class="hadith-card" style="text-align:center;">لا توجد نتائج لـ "${escapeHtml(query)}" في ${getBookName(currentBook)}</div>`;
                return;
            }
            let html = `<div class="hadith-card">
                            <div class="hadith-header">
                                <span class="hadith-book-name">🔍 نتائج البحث في ${getBookName(currentBook)}</span>
                                <span class="hadith-number">${data.length} نتيجة</span>
                            </div>
                            <div class="search-results">`;
            data.forEach(item => {
                const preview = item.text.length > 250 ? item.text.substring(0, 250) + '...' : item.text;
                html += `<div class="search-result-item" onclick="showHadith(${item.index})">
                            <div class="res-num">📌 حديث رقم ${item.id}</div>
                            ${item.narrator ? `<div style="color:#b8860b;font-size:13px;margin:5px 0;">🎙️ ${escapeHtml(item.narrator)}</div>` : ''}
                            <div class="res-text">${safeHighlight(preview, query)}</div>
                        </div>`;
            });
            html += '</div></div>';
            content.innerHTML = html;
            showSideIndex(data, 'hadith');
        } catch(e) { content.innerHTML = '<div class="hadith-card" style="text-align:center;color:red;">حدث خطأ في البحث</div>'; }
    }

    // ===== البحث المتقدم =====
    function showAdvancedSearch() { document.getElementById('advSearchModal').classList.add('show'); setTimeout(() => document.getElementById('advSearchInput').focus(), 300); }
    function hideAdvancedSearch() { document.getElementById('advSearchModal').classList.remove('show'); }
    function selectAllBooks() { document.querySelectorAll('.book-chk').forEach(chk => chk.checked = true); document.getElementById('chk_quran').checked = true; }
    function deselectAllBooks() { document.querySelectorAll('.book-chk').forEach(chk => chk.checked = false); document.getElementById('chk_quran').checked = false; }
    function selectOnlyQuran() { deselectAllBooks(); document.getElementById('chk_quran').checked = true; }
    function selectOnly9Books() {
        deselectAllBooks();
        const nine = ['bukhari','muslim','abudawud','tirmidhi','nasai','ibnmajah','malik','ahmed','darimi'];
        document.querySelectorAll('.book-chk').forEach(chk => { if (nine.includes(chk.value)) chk.checked = true; });
    }
    async function doAdvancedSearch() {
        const query = document.getElementById('advSearchInput').value.trim();
        if (!query) { alert('اكتب كلمة للبحث'); return; }
        const selectedBooks = [];
        document.querySelectorAll('.book-chk:checked').forEach(chk => selectedBooks.push(chk.value));
        const includeQuran = document.getElementById('chk_quran').checked;
        if (selectedBooks.length === 0 && !includeQuran) { alert('اختر كتاباً'); return; }
        hideAdvancedSearch();
        currentSearchQuery = query;
        const content = document.getElementById('content');
        content.innerHTML = '<div class="loading">جاري البحث...</div>';
        hideSideIndex();
        try {
            let url = `/api/search_advanced?query=${encodeURIComponent(query)}`;
            if (selectedBooks.length > 0) url += `&books=${selectedBooks.join(',')}`;
            if (includeQuran) url += `&quran=1`;
            const res = await fetch(url);
            const data = await res.json();
            let totalResults = 0;
            if (data.quran) totalResults += data.quran.length;
            if (data.books) for (const k in data.books) totalResults += data.books[k].results.length;
            if (totalResults === 0) { content.innerHTML = `<div class="hadith-card" style="text-align:center;">لا توجد نتائج لـ "${escapeHtml(query)}"</div>`; return; }
            let html = `<div class="hadith-card">
                            <div class="hadith-header">
                                <span class="hadith-book-name">🔎 نتائج البحث المتقدم</span>
                                <span class="hadith-number">${totalResults} نتيجة</span>
                            </div>
                            <div style="padding:10px;color:#666;font-size:14px;">كلمة البحث: <mark>${escapeHtml(query)}</mark></div>`;
            if (data.quran && data.quran.length > 0) {
                html += `<div class="adv-results-section">
                            <div class="adv-book-title"><span>📖 القرآن الكريم</span><span class="count">${data.quran.length}</span></div>`;
                data.quran.forEach(item => {
                    html += `<div class="search-result-item" onclick="gotoQuranResult(${item.surah}, ${item.ayah}, '${query.replace(/'/g, "\\'")}')">
                                <div class="res-num">سورة ${escapeHtml(item.surah_name)} - آية ${item.ayah}</div>
                                <div class="res-text">${safeHighlight(item.text, query)}</div>
                            </div>`;
                });
                html += `</div>`;
            }
            if (data.books) {
                for (const bookId in data.books) {
                    const bookData = data.books[bookId];
                    html += `<div class="adv-results-section">
                                <div class="adv-book-title"><span>📚 ${escapeHtml(bookData.name)}</span><span class="count">${bookData.results.length}</span></div>`;
                    bookData.results.forEach(item => {
                        const preview = item.text.length > 250 ? item.text.substring(0, 250) + '...' : item.text;
                        html += `<div class="search-result-item" onclick="hideAdvancedSearch(); currentBook='${bookId}'; setActiveBook('${bookId}'); currentSearchQuery='${query.replace(/'/g, "\\'")}'; showHadith(${item.index})">
                                    <div class="res-num">📌 حديث رقم ${item.id}</div>
                                    ${item.narrator ? `<div style="color:#b8860b;font-size:13px;">🎙️ ${escapeHtml(item.narrator)}</div>` : ''}
                                    <div class="res-text">${safeHighlight(preview, query)}</div>
                                </div>`;
                    });
                    html += `</div>`;
                }
            }
            html += `</div>`;
            content.innerHTML = html;
        } catch(e) { content.innerHTML = '<div class="hadith-card" style="text-align:center;color:red;">حدث خطأ</div>'; }
    }

    function gotoQuranResult(surah, ayah, query) {
        hideAdvancedSearch();
        currentBook = 'quran';
        setActiveBook('quran');
        surahSearchQuery = query;
        contextAyahNum = ayah;
        quranViewMode = 'context';
        showSurah(surah).then(() => {
            setTimeout(() => scrollToAyah(ayah), 500);
        });
    }

    // ===== الكتب =====
    function setActiveBook(bookId) {
        document.querySelectorAll('.book-btn').forEach(b => b.classList.remove('active'));
        if (bookId === 'quran') document.getElementById('quranBtn').classList.add('active');
        else document.querySelector(`[data-book="${bookId}"]`)?.classList.add('active');
    }
    async function selectBook(bookId) {
        currentBook = bookId; currentIndex = 0; currentSearchQuery = ''; surahSearchQuery = '';
        quranViewMode = 'full'; contextAyahNum = null;
        setActiveBook(bookId); hideSideIndex(); startReadingTimer();
        await showHadith(0);
    }
    async function showHadith(index) {
        const content = document.getElementById('content');
        content.innerHTML = '<div class="loading">جاري التحميل...</div>';
        try {
            const res = await fetch(`/api/hadith?book=${currentBook}&index=${index}`);
            const data = await res.json();
            if (data.error) { content.innerHTML = `<div class="hadith-card" style="text-align:center;color:red;">${data.error}</div>`; return; }
            currentIndex = data.index;
            const isBookmarked = bookmarks.some(b => b.key === `${currentBook}_${currentIndex}`);
            content.innerHTML = `
                <div class="hadith-card">
                    <div class="hadith-header">
                        <span class="hadith-book-name">📚 ${getBookName(currentBook)}</span>
                        <span class="hadith-number">حديث رقم ${data.id} / ${data.total}</span>
                    </div>
                    ${data.narrator ? `<div class="narrator">🎙️ ${escapeHtml(data.narrator)}</div>` : ''}
                    <div class="hadith-text" id="hadithText" style="font-size:${fontSize}px;">${safeHighlight(data.text, currentSearchQuery)}</div>
                    <div class="copy-buttons">
                        <button class="copy-btn" onclick="copyHadith()">📋 نسخ الحديث</button>
                        <button class="copy-btn" onclick="toggleBookmark()">${isBookmarked ? '🔖 إزالة' : '🔖 علامة'}</button>
                        <button class="copy-btn" onclick="openNoteForHadith()">🗒️ ملاحظة</button>
                    </div>
                </div>
                <div class="nav-buttons">
                    <button class="nav-btn" onclick="showHadith(${data.index - 1})" ${data.index === 0 ? 'disabled' : ''}>◀ السابق</button>
                    <button class="nav-btn" onclick="showHadith(0)">🏠 الأول</button>
                    <button class="nav-btn" onclick="showHadith(${data.index + 1})" ${data.index >= data.total - 1 ? 'disabled' : ''}>التالي ▶</button>
                </div>
            `;
        } catch (e) { content.innerHTML = '<div class="hadith-card" style="text-align:center;color:red;">حدث خطأ</div>'; }
    }
    function openNoteForHadith() {
        document.getElementById('noteCategory').value = 'hadith';
        showNotesModal();
        setTimeout(() => showNoteForm(), 100);
    }

    // ===== القرآن =====
    async function selectQuran() {
        currentBook = 'quran'; setActiveBook('quran'); hideSideIndex(); startReadingTimer();
        surahSearchQuery = ''; quranViewMode = 'full'; contextAyahNum = null;
        await showSurah(1);
    }
    async function showSurah(surahNum) {
        const content = document.getElementById('content');
        content.innerHTML = '<div class="loading">جاري تحميل السورة...</div>';
        try {
            const res = await fetch(`/api/surah?surah=${surahNum}`);
            const data = await res.json();
            currentSurah = surahNum; currentSurahData = data; currentAyahIndex = 0;
            renderFullSurah();
        } catch (e) { content.innerHTML = '<div class="hadith-card" style="text-align:center;color:red;">حدث خطأ</div>'; }
    }
    function renderFullSurah() {
        const content = document.getElementById('content');
        const data = currentSurahData;
        if (!data.ayahs || data.ayahs.length === 0) { content.innerHTML = '<div class="hadith-card" style="text-align:center;">لا توجد آيات</div>'; return; }
        
        const surahsArray = JSON.parse(`{{ surahs|tojson }}`);
        let surahSelectHtml = '<select id="surahSelect" onchange="changeSurah(this.value)">';
        surahsArray.forEach(s => { surahSelectHtml += `<option value="${s.id}" ${s.id === currentSurah ? 'selected' : ''}>${s.id}. سورة ${s.name}</option>`; });
        surahSelectHtml += '</select>';
        
        let ayahSelectHtml = '<select id="ayahSelect" onchange="scrollToAyah(this.value)">';
        ayahSelectHtml += '<option value="">📌 انتقل إلى آية...</option>';
        data.ayahs.forEach(a => { ayahSelectHtml += `<option value="${a.ayah}">آية ${a.ayah}</option>`; });
        ayahSelectHtml += '</select>';
        
        let displayAyahs = data.ayahs;
        let contextInfo = '';
        if (quranViewMode === 'context' && contextAyahNum) {
            const idx = data.ayahs.findIndex(a => a.ayah === contextAyahNum);
            if (idx !== -1) {
                const CONTEXT = 8;
                const start = Math.max(0, idx - CONTEXT);
                const end = Math.min(data.ayahs.length, idx + CONTEXT + 1);
                displayAyahs = data.ayahs.slice(start, end);
                contextInfo = `<div class="context-info">
                    <span>📄 عرض الصفحة: الآيات ${displayAyahs[0].ayah} - ${displayAyahs[displayAyahs.length - 1].ayah} (من أصل ${data.ayahs.length} في السورة)</span>
                    <button onclick="setQuranViewMode('full')" style="padding:6px 14px;background:var(--main-green);color:white;border:none;border-radius:6px;cursor:pointer;font-family:inherit;font-weight:bold;">📖 عرض السورة كاملة</button>
                </div>`;
            }
        }
        
        let ayahsHtml = '';
        if (currentSurah !== 1 && currentSurah !== 9 && displayAyahs[0].ayah === 1) {
            ayahsHtml += `<div class="basmala">بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ</div>`;
        }
        
        displayAyahs.forEach(a => {
            const isTarget = quranViewMode === 'context' && a.ayah === contextAyahNum;
            ayahsHtml += `
                <div class="ayah-line ${isTarget ? 'target-ayah' : ''}" id="ayah-${a.ayah}" data-ayah="${a.ayah}">
                    <span>${safeHighlight(a.text, surahSearchQuery || currentSearchQuery)}</span>
                    <span class="ayah-num-badge">${a.ayah}</span>
                    <div class="ayah-actions">
                        <button class="ayah-action-btn" onclick="copyAyah(${a.ayah})">📋 نسخ</button>
                        <button class="ayah-action-btn" onclick="bookmarkAyah(${a.ayah})">🔖 علامة</button>
                        <button class="ayah-action-btn" onclick="noteAyah(${a.ayah})">🗒️ ملاحظة</button>
                        <button class="ayah-action-btn" onclick="showContextAround(${a.ayah})">📄 السياق</button>
                        ${a.tafsir ? `<button class="ayah-action-btn" onclick="toggleTafsir(${a.ayah})">📖 التفسير</button>` : ''}
                    </div>
                    ${a.tafsir ? `<div class="tafsir-panel" id="tafsir-${a.ayah}"><div class="tafsir-title">📖 التفسير:</div>${safeHighlight(a.tafsir, surahSearchQuery || currentSearchQuery)}</div>` : ''}
                </div>
            `;
        });
        
        const searchSurahHtml = `<div style="display:flex;gap:8px;margin-bottom:15px;flex-wrap:wrap;">
            <input type="text" id="surahSearchInput" value="${escapeHtml(surahSearchQuery)}" placeholder="🔍 ابحث في هذه السورة فقط..." style="flex:1;min-width:200px;padding:10px 15px;border:2px solid #ddd;border-radius:8px;font-family:inherit;font-size:15px;" onkeydown="if(event.key==='Enter') searchInSurah()">
            <button onclick="searchInSurah()" style="padding:10px 20px;background:var(--gold);color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;">🔍 بحث في السورة</button>
            <button onclick="clearSurahSearch()" style="padding:10px 20px;background:#95a5a6;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;">✕ مسح</button>
        </div>`;
        
        const viewToggleHtml = `<div class="view-toggle">
            <button onclick="setQuranViewMode('full')" class="${quranViewMode === 'full' ? 'active' : ''}">📖 عرض السورة كاملة</button>
            <button onclick="setQuranViewMode('context')" class="${quranViewMode === 'context' ? 'active' : ''}">📄 عرض الصفحة (الآية والسياق)</button>
        </div>`;
        
        content.innerHTML = `
            ${searchSurahHtml}
            ${viewToggleHtml}
            ${contextInfo}
            <div class="quran-tools">
                ${surahSelectHtml}
                ${ayahSelectHtml}
                <button onclick="document.querySelectorAll('.tafsir-panel').forEach(t=>t.classList.toggle('show'))">📖 التفسير</button>
                <button onclick="copySurah()">📋 نسخ السورة</button>
            </div>
            <div class="surah-container">
                <div class="surah-header-bar">
                    <h2>سورة ${data.name}</h2>
                    <div>${data.ayahs.length} آية</div>
                </div>
                ${ayahsHtml}
            </div>
            <div class="nav-buttons">
                <button class="nav-btn" onclick="changeSurah(${currentSurah - 1})" ${currentSurah <= 1 ? 'disabled' : ''}>◀ السابقة</button>
                <button class="nav-btn" onclick="scrollToTop()">⬆ أعلى</button>
                <button class="nav-btn" onclick="changeSurah(${currentSurah + 1})" ${currentSurah >= 114 ? 'disabled' : ''}>التالية ▶</button>
            </div>
        `;
    }
    function setQuranViewMode(mode) {
        quranViewMode = mode;
        if (mode === 'context' && !contextAyahNum) {
            contextAyahNum = currentSurahData?.ayahs?.[0]?.ayah || 1;
        }
        renderFullSurah();
        if (mode === 'context' && contextAyahNum) {
            setTimeout(() => scrollToAyah(contextAyahNum), 300);
        }
    }
    function showContextAround(ayahNum) {
        contextAyahNum = ayahNum;
        quranViewMode = 'context';
        renderFullSurah();
        setTimeout(() => scrollToAyah(ayahNum), 300);
    }
    function changeSurah(surahNum) {
        surahSearchQuery = '';
        currentSearchQuery = '';
        quranViewMode = 'full';
        contextAyahNum = null;
        hideSideIndex();
        showSurah(surahNum);
    }
    async function searchInSurah() {
        const query = document.getElementById('surahSearchInput').value.trim();
        if (!query) { alert('اكتب كلمة للبحث'); return; }
        surahSearchQuery = query;
        const res = await fetch(`/api/search_surah?surah=${currentSurah}&query=${encodeURIComponent(query)}`);
        const data = await res.json();
        if (data.length === 0) {
            alert(`لا توجد نتائج لـ "${query}" في سورة ${currentSurahData.name}`);
            surahSearchQuery = '';
            renderFullSurah();
            return;
        }
        renderFullSurah();
        showSideIndex(data, 'quran');
    }
    function clearSurahSearch() {
        surahSearchQuery = '';
        currentSearchQuery = '';
        hideSideIndex();
        renderFullSurah();
    }
    function bookmarkAyah(ayahNum) {
        if (currentSurahData) currentAyahIndex = currentSurahData.ayahs.findIndex(a => a.ayah === ayahNum);
        toggleBookmark();
    }
    function noteAyah(ayahNum) {
        if (currentSurahData) currentAyahIndex = currentSurahData.ayahs.findIndex(a => a.ayah === ayahNum);
        document.getElementById('noteCategory').value = 'quran';
        showNotesModal();
        setTimeout(() => showNoteForm(), 100);
    }
    function scrollToAyah(ayahNum) {
        if (!ayahNum) return;
        setTimeout(() => {
            const el = document.getElementById('ayah-' + ayahNum);
            if (el) {
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                el.classList.add('highlight');
                setTimeout(() => el.classList.remove('highlight'), 4000);
            }
        }, 300);
    }
    function scrollToTop() { window.scrollTo({ top: 0, behavior: 'smooth' }); }
    function toggleTafsir(n) { const el = document.getElementById('tafsir-' + n); if (el) el.classList.toggle('show'); }
    function copyAyah(n) {
        const el = document.getElementById('ayah-' + n);
        if (!el) return;
        navigator.clipboard.writeText(el.querySelector('span').innerText).then(() => alert('✅ تم نسخ الآية'));
    }
    function copySurah() {
        const c = document.querySelector('.surah-container');
        if (!c) return;
        let text = c.querySelector('h2').innerText + '\n\n';
        c.querySelectorAll('.ayah-line').forEach(l => { text += l.querySelector('span').innerText + ' (' + l.dataset.ayah + ')\n'; });
        navigator.clipboard.writeText(text).then(() => alert('✅ تم نسخ السورة'));
    }

    function showAbout() { document.getElementById('aboutModal').classList.add('show'); }
    function hideAbout() { document.getElementById('aboutModal').classList.remove('show'); }

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
        navigator.clipboard.writeText(el.innerText).then(() => alert('✅ تم نسخ الحديث'));
    }

    updateBookmarkBadge();
    updateNotesBadge();
</script>
</body>
</html>
"""

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)