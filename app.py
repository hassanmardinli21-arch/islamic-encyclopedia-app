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

# بناء خريطة التفسير
tafsir_map = {}
surah_names_ar = [s['name'] for s in surahs_list]

if isinstance(tafsir_list, list) and tafsir_list and isinstance(tafsir_list[0], dict) and 'ayahs' in tafsir_list[0]:
    for surah_obj in tafsir_list:
        surah_name = surah_obj.get('surah_name', '').strip()
        surah_num = None
        for i, name in enumerate(surah_names_ar, start=1):
            if name == surah_name or surah_name in name:
                surah_num = i
                break
        if not surah_num:
            continue
        for ayah in surah_obj.get('ayahs', []):
            ayah_num = ayah.get('number', 0)
            tafsir_map[(surah_num, ayah_num)] = ayah.get('text', '')

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

def get_books_info():
    """إرجاع قائمة الكتب مع عدد الأحاديث"""
    info = {}
    for book_id in BOOKS.keys():
        hadiths = load_hadith_book(book_id)
        info[book_id] = {
            'name': BOOKS[book_id],
            'count': len(hadiths)
        }
    return info

# ==================== 3. المسارات ====================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, books=BOOKS, surahs=surahs_list)

@app.route('/api/book/<book_id>')
def get_book_info(book_id):
    """إرجاع معلومات كتاب كامل"""
    if book_id == 'quran':
        return jsonify({'name': 'القرآن الكريم', 'total': len(surahs_list), 'surahs': surahs_list})
    if book_id not in BOOKS:
        return jsonify({'error': 'كتاب غير موجود'}), 404
    hadiths = load_hadith_book(book_id)
    return jsonify({
        'name': BOOKS[book_id],
        'total': len(hadiths),
        'index': len(hadiths) - 1 if hadiths else 0
    })

@app.route('/api/hadith')
def get_hadith():
    """إرجاع حديث محدد"""
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
        'narrator': h.get('english', {}).get('narrator', ''),
        'english_text': h.get('english', {}).get('text', '')
    })

@app.route('/api/surah')
def get_surah():
    """إرجاع سورة كاملة"""
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
            padding: 0;
            margin: 0;
        }

        /* ============ الهيدر ============ */
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
            text-shadow: 0 1px 3px rgba(0,0,0,0.3);
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

        /* ============ صندوق البحث ============ */
        .search-area {
            display: flex;
            gap: 6px;
            max-width: 900px;
            margin: 0 auto;
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

        /* ============ أزرار التحكم بالنص ============ */
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
        .text-controls button:hover { background: #40916c; }
        .text-controls .size-display {
            background: white;
            padding: 6px 14px;
            border-radius: 6px;
            font-weight: bold;
            border: 1px solid #ccc;
            min-width: 40px;
            text-align: center;
        }

        /* ============ أزرار الكتب ============ */
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

        /* ============ منطقة العرض ============ */
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

        /* ============ أزرار التنقل ============ */
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

        /* ============ التنقل بالآيات للقرآن ============ */
        .ayah-nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 15px 0;
            padding: 10px;
            background: var(--light-green);
            border-radius: 8px;
            font-weight: bold;
            color: var(--main-green);
        }

        /* ============ نتائج البحث ============ */
        .search-results {
            max-height: 400px;
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

        .loading {
            text-align: center;
            padding: 40px;
            color: var(--main-green);
            font-size: 18px;
        }

        /* ============ وضع الجوال ============ */
        @media (max-width: 600px) {
            .header h1 { font-size: 20px; }
            .hadith-text { font-size: 19px; }
            .hadith-card { padding: 15px; }
            .nav-btn { padding: 10px 20px; font-size: 14px; min-width: 90px; }
            .book-btn { font-size: 12px; padding: 6px 12px; }
        }

        /* ============ الوضع الليلي ============ */
        body.dark-mode {
            --bg: #1a1a1a;
            --text-dark: #e0e0e0;
        }
        body.dark-mode .hadith-card {
            background: #2a2a2a;
            border-color: #444;
        }
        body.dark-mode .hadith-text {
            background: #333;
            color: #e0e0e0;
        }
        body.dark-mode .text-controls { background: #2a2a2a; border-color: #444; }
        body.dark-mode .text-controls .size-display { background: #333; color: white; border-color: #555; }
        body.dark-mode .narrator { background: #3a3a2a; color: #e0c060; }
        body.dark-mode .search-area input { background: #333; color: white; }
    </style>
</head>
<body>

<!-- ============ الهيدر ============ -->
<div class="header">
    <h1>🕌 الموسوعة الإسلامية الشاملة 📚</h1>

    <div class="top-actions">
        <button class="top-btn" onclick="toggleDark()">🌙 ليلي</button>
        <button class="top-btn" onclick="window.scrollTo(0,document.body.scrollHeight)">⬇ آخر الصفحة</button>
        <button class="top-btn" onclick="window.scrollTo(0,0)">⬆ أول الصفحة</button>
        <button class="top-btn" id="bookmarkBtn" onclick="toggleBookmark()">🔖 علامة</button>
    </div>

    <div class="search-area">
        <input type="text" id="searchInput" placeholder="اكتب كلمة للبحث..." onkeydown="if(event.key==='Enter') doSearch()">
        <button onclick="doSearch()">🔍</button>
    </div>
</div>

<!-- ============ التحكم بالنص ============ -->
<div class="text-controls">
    <button onclick="changeFontSize(1)">➕ تكبير النص</button>
    <span class="size-display" id="fontSizeDisplay">22</span>
    <button onclick="changeFontSize(-1)">➖ تصغير النص</button>
    <button onclick="resetFontSize()">↺ الافتراضي</button>
</div>

<!-- ============ أزرار الكتب ============ -->
<div class="books-bar" id="booksBar">
    <button class="book-btn" onclick="selectQuran()" id="quranBtn">📖 القرآن الكريم</button>
    {% for key, value in books.items() %}
    <button class="book-btn" data-book="{{ key }}" onclick="selectBook('{{ key }}')">{{ value }}</button>
    {% endfor %}
</div>

<!-- ============ منطقة العرض ============ -->
<div class="content-area">
    <div id="content">
        <div class="loading">اختر كتاباً من الأعلى للبدء 🕌</div>
    </div>
</div>

<script>
    let currentBook = null;
    let currentIndex = 0;
    let currentSurah = 1;
    let currentAyahIndex = 0;
    let currentSurahData = null;
    let fontSize = 22;
    let bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '{}');

    // ============ إدارة الخط ============
    function changeFontSize(delta) {
        fontSize = Math.max(14, Math.min(48, fontSize + delta));
        document.getElementById('fontSizeDisplay').innerText = fontSize;
        document.querySelectorAll('.hadith-text, .quran-ayah-text').forEach(el => {
            el.style.fontSize = fontSize + 'px';
        });
    }
    function resetFontSize() {
        fontSize = 22;
        document.getElementById('fontSizeDisplay').innerText = fontSize;
        document.querySelectorAll('.hadith-text, .quran-ayah-text').forEach(el => {
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

    // ============ العلامات المرجعية ============
    function toggleBookmark() {
        if (!currentBook) return;
        const key = currentBook + '_' + currentIndex;
        if (bookmarks[key]) {
            delete bookmarks[key];
        } else {
            bookmarks[key] = { book: currentBook, index: currentIndex, time: Date.now() };
        }
        localStorage.setItem('bookmarks', JSON.stringify(bookmarks));
        alert(bookmarks[key] ? '✅ تمت إضافة علامة' : '🗑️ تم حذف العلامة');
    }

    // ============ اختيار كتاب ============
    function setActiveBook(bookId) {
        document.querySelectorAll('.book-btn').forEach(b => b.classList.remove('active'));
        if (bookId === 'quran') {
            document.getElementById('quranBtn').classList.add('active');
        } else {
            document.querySelector(`[data-book="${bookId}"]`).classList.add('active');
        }
    }

    async function selectBook(bookId) {
        currentBook = bookId;
        currentIndex = 0;
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
                    <div class="hadith-text" id="hadithText" style="font-size:${fontSize}px;">${escapeHtml(data.text)}</div>
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
            content.innerHTML = '<div class="hadith-card" style="text-align:center;color:red;">حدث خطأ في التحميل</div>';
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
            currentAyahIndex = 0;

            renderSurah();
        } catch (e) {
            content.innerHTML = '<div class="hadith-card" style="text-align:center;color:red;">حدث خطأ</div>';
        }
    }

    function renderSurah() {
        const content = document.getElementById('content');
        const data = currentSurahData;

        if (!data.ayahs || data.ayahs.length === 0) {
            content.innerHTML = '<div class="hadith-card" style="text-align:center;">لا توجد آيات</div>';
            return;
        }

        const ayah = data.ayahs[currentAyahIndex];

        // قائمة السور
        const surahOptions = `{{ surahs|tojson }}`.replace(/'/g, "&#39;");
        const surahsArray = JSON.parse(`{{ surahs|tojson }}`);

        let surahSelectHtml = '<select onchange="showSurah(this.value)" style="width:100%;padding:10px;font-size:16px;border-radius:8px;border:1px solid #ccc;margin-bottom:15px;font-family:inherit;">';
        surahsArray.forEach(s => {
            surahSelectHtml += `<option value="${s.id}" ${s.id === currentSurah ? 'selected' : ''}>${s.id}. سورة ${s.name}</option>`;
        });
        surahSelectHtml += '</select>';

        content.innerHTML = `
            ${surahSelectHtml}
            <div class="hadith-card">
                <div class="hadith-header">
                    <span class="hadith-book-name">📖 سورة ${data.name}</span>
                    <span class="hadith-number">آية ${ayah.ayah} / ${data.ayahs.length}</span>
                </div>
                <div class="hadith-text quran-ayah-text" id="hadithText" style="font-size:${fontSize + 4}px;text-align:center;line-height:2.5;color:#1a5f3f;font-weight:bold;">
                    ${escapeHtml(ayah.text)}
                </div>
                ${ayah.tafsir ? `<div class="narrator" style="margin-top:15px;">📖 التفسير (السعدي)</div><div class="hadith-text" style="font-size:${fontSize - 4}px;background:#f0f9ff;border-right:4px solid #28a745;">${escapeHtml(ayah.tafsir)}</div>` : ''}
                <div class="copy-buttons">
                    <button class="copy-btn" onclick="copyHadith()">📋 نسخ الآية</button>
                </div>
            </div>
            <div class="nav-buttons">
                <button class="nav-btn" onclick="prevAyah()" ${currentAyahIndex === 0 ? 'disabled' : ''}>◀ السابقة</button>
                <button class="nav-btn" onclick="showSurah(${currentSurah})">🔄 السورة</button>
                <button class="nav-btn" onclick="nextAyah()" ${currentAyahIndex >= data.ayahs.length - 1 ? 'disabled' : ''}>التالية ▶</button>
            </div>
        `;
    }

    function nextAyah() {
        if (currentAyahIndex < currentSurahData.ayahs.length - 1) {
            currentAyahIndex++;
            renderSurah();
        } else if (currentSurah < 114) {
            showSurah(currentSurah + 1);
        }
    }

    function prevAyah() {
        if (currentAyahIndex > 0) {
            currentAyahIndex--;
            renderSurah();
        } else if (currentSurah > 1) {
            showSurah(currentSurah - 1).then(() => {
                currentAyahIndex = currentSurahData.ayahs.length - 1;
                renderSurah();
            });
        }
    }

    // ============ البحث ============
    async function doSearch() {
        const query = document.getElementById('searchInput').value.trim();
        if (!query) {
            alert('اكتب كلمة للبحث');
            return;
        }
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
                            <div class="res-text">${escapeHtml(item.text.substring(0, 200))}${item.text.length > 200 ? '...' : ''}</div>
                        </div>`;
            });
            html += '</div></div>';
            content.innerHTML = html;
        } catch (e) {
            content.innerHTML = '<div class="hadith-card" style="text-align:center;color:red;">حدث خطأ في البحث</div>';
        }
    }

    // ============ أدوات مساعدة ============
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
</script>
</body>
</html>
"""

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
